"""Transactional observation history; replaying a cached response is idempotent."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd

from hanoi_rentals.features.dates import (
    EPOCH,
    HOLDOUT_START,
    TARGET_END,
    ZONE,
    today_hanoi,
)

from .normalization import SOURCE_ADAPTERS, drop_implausible
from .phongtro123 import parse_phongtro123
from .sources import parse_alonhadat, parse_nhatot


@contextmanager
def database(root):
    path = Path(root) / "data/processed/observations.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY, listing_id TEXT NOT NULL,
            price_observed_date TEXT, payload TEXT NOT NULL)""")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS observations_date ON observations(price_observed_date)"
        )
        yield connection
        connection.commit()
    finally:
        connection.close()


def record_response(root, path, raw, records, source, evidence):
    if not records:
        return 0
    frame = pd.DataFrame(records)
    source_records = {str(row["listing_id"]): row for row in records}
    adapted = SOURCE_ADAPTERS[source](frame)
    adapted = drop_implausible(adapted)
    adapted["posted_date"] = adapted.posted_date.dt.strftime("%Y-%m-%d")
    digest = sha256(raw.encode()).hexdigest()
    if evidence and evidence.get("sha256") != digest:
        raise ValueError(
            f"Raw response checksum differs from collection evidence: {path}"
        )
    observed = (evidence or {}).get("price_observed_date")
    relative = str(Path(path).relative_to(root))
    additions = 0
    with database(root) as connection:
        for row in json.loads(adapted.to_json(orient="records")):
            original = source_records[row["listing_id"].split("_", 1)[1]]
            # Same response + retrieval identity gives the same observation on every replay.
            key = json.dumps(
                [source, row["listing_id"], relative, digest, evidence], sort_keys=True
            )
            observation_id = sha256(key.encode()).hexdigest()
            row.update(
                observation_id=observation_id,
                price_observed_date=observed,
                date_origin=(evidence or {}).get("date_origin", "unverified_archive"),
                collected_at=(evidence or {}).get("collected_at"),
                parsed_at=datetime.now(ZONE).isoformat(),
                raw_path=relative,
                raw_sha256=digest,
                source_posted_raw=original.get("posted_raw"),
                source_posted_timestamp_ms=original.get("source_posted_timestamp_ms"),
                source_original_timestamp_ms=original.get(
                    "source_original_timestamp_ms"
                ),
            )
            attributes = {
                field: original.get(field)
                for field in (
                    "body",
                    "source_project_id",
                    "source_project_name",
                    "source_latitude",
                    "source_longitude",
                    "source_subtype",
                )
            }
            if "source_posted_label" in original:
                attributes["source_posted_label"] = original["source_posted_label"]
            row.update(attributes)
            if observed:
                row["scraped_at"] = observed
            cursor = connection.execute(
                "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?)",
                (
                    observation_id,
                    row["listing_id"],
                    observed,
                    json.dumps(row, ensure_ascii=False),
                ),
            )
            additions += cursor.rowcount
            if cursor.rowcount == 0:
                # Upgrade older observations using the exact receipt and raw checksum.
                connection.execute(
                    "UPDATE observations SET payload=json_patch(payload, ?) "
                    "WHERE observation_id=? AND json_extract(payload, '$.body') IS NULL",
                    (json.dumps(attributes, ensure_ascii=False), observation_id),
                )
    return additions


def load_observations(root, before=None):
    with database(root) as connection:
        query = "SELECT payload FROM observations"
        params = ()
        if before:
            query += " WHERE price_observed_date < ?"
            params = (str(before),)
        rows = [json.loads(row[0]) for row in connection.execute(query, params)]
    return pd.DataFrame(rows)


def replay_archives(root):
    """Recover exact archived versions, trusting only matching recorded checksums."""
    root = Path(root)
    manifest_path = root / "reports/raw_manifest_latest.json"
    manifests = list((root / "data/raw").glob("*/_manifest.json"))
    if manifest_path.exists():
        manifests.append(manifest_path)
    evidence_by_path = {}
    for path in manifests:
        manifest = json.loads(path.read_text())
        # Timestamped runs require their per-response receipt; a run may span midnight.
        if manifest.get("run_id"):
            continue
        for entry in manifest["files"]:
            evidence_by_path[entry["path"]] = {
                "sha256": entry["sha256"],
                "price_observed_date": manifest["crawl_date"],
                "date_origin": "verified_manifest_day",
                "collected_at": None,
            }
    added, errors = 0, []
    windows = {}
    for check in (root / "data/processed/crawl_runs").glob("*.json"):
        config = json.loads(check.read_text())
        windows[config["run_id"]] = config["since"], config["until"]
    for path in sorted((root / "data/raw").glob("*/*/*/p*.*")):
        if path.suffix not in (".json", ".html") or path.name.endswith(".meta.json"):
            continue
        source, category = path.parts[-3:-1]
        if source not in SOURCE_ADAPTERS:
            continue
        try:
            page = int(path.stem[1:])
            raw = path.read_bytes().decode("utf-8")
            if source == "nhatot":
                records = parse_nhatot(raw, category, (page - 1) * 50)
            elif source == "alonhadat":
                records = parse_alonhadat(raw, category, page)
            else:
                records, _ = parse_phongtro123(raw, category, page)
            metadata = path.with_suffix(path.suffix + ".meta.json")
            evidence = (
                json.loads(metadata.read_text())
                if metadata.exists()
                else evidence_by_path.get(str(path.relative_to(root)))
            )
            if source == "phongtro123" and not evidence:
                raise ValueError("Missing Phongtro123 collection receipt.")
            since, until = windows.get(path.parts[-4], (str(EPOCH), str(TARGET_END)))
            records = [
                row
                for row in records
                if since <= str(row.get("posted_raw", ""))[:10] <= until
            ]
            if source == "phongtro123":
                for row in records:
                    row["scraped_at"] = evidence["price_observed_date"]
            added += record_response(root, path, raw, records, source, evidence)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(path.relative_to(root)), "error": str(exc)})
    return {
        "added_observations": added,
        "errors": errors,
        "coverage": coverage_report(root),
    }


def coverage_report(root):
    frame = load_observations(root)
    rows = []
    snapshot = Path(root) / "data/processed/listings.csv"
    fields = ["listing_id", "source", "category", "posted_date"]
    stored = (
        pd.read_csv(snapshot, usecols=fields)
        if snapshot.exists()
        else pd.DataFrame(columns=fields)
    )
    postings = pd.concat(
        [stored, frame.reindex(columns=fields)], ignore_index=True
    ).drop_duplicates()
    # Retain both posting versions when the source refreshes the date of an ID.
    originals = pd.to_datetime(
        frame.get("source_original_timestamp_ms", pd.Series(dtype=float)),
        unit="ms",
        utc=True,
        errors="coerce",
    ).dt.tz_convert(ZONE)
    today = today_hanoi()
    for period in pd.period_range(EPOCH, TARGET_END, freq="M"):
        start, end = period.start_time.date(), period.end_time.date()
        posted = postings.loc[
            postings.posted_date.astype(str).str.startswith(str(period))
        ]
        if frame.empty:
            observed = frame
        else:
            observed = frame[
                frame.price_observed_date.fillna("").str.startswith(str(period))
            ]
        rows.append(
            {
                "month": str(period),
                "unique_listings_posted": int(posted.listing_id.nunique())
                if len(posted)
                else 0,
                "posting_source_category_counts": posted.groupby(["source", "category"])
                .listing_id.nunique()
                .rename("n")
                .reset_index()
                .to_dict("records"),
                "source_original_month_unique_listings": int(
                    frame.loc[
                        originals.dt.strftime("%Y-%m").eq(str(period)), "listing_id"
                    ].nunique()
                )
                if len(originals)
                else 0,
                "dated_observations": len(observed),
                "unique_observed_listings": int(observed.listing_id.nunique())
                if len(observed)
                else 0,
                "oldest_posted_date": str(posted.posted_date.min())
                if len(posted)
                else None,
                "newest_posted_date": str(posted.posted_date.max())
                if len(posted)
                else None,
                "source_category_counts": observed.groupby(["source", "category"])
                .size()
                .rename("n")
                .reset_index()
                .to_dict("records")
                if len(observed)
                else [],
                "status": "future"
                if start > today
                else "observed_incomplete"
                if len(observed)
                else "missing",
                "future_collection_pending": end > today,
            }
        )
    report = {
        "target_since": str(EPOCH),
        "target_until": str(TARGET_END),
        "as_of": str(today),
        "holdout_start": str(HOLDOUT_START),
        "observations": len(frame),
        "undated_observations": int(frame.price_observed_date.isna().sum())
        if len(frame)
        else 0,
        "months": rows,
        "note": "Posting-month coverage does not establish historical-price coverage. Counts do not imply complete source coverage.",
    }
    crawl_path = Path(root) / "reports/crawl_latest.json"
    if crawl_path.exists():
        crawl = json.loads(crawl_path.read_text())
        report["latest_collection"] = {
            key: crawl.get(key)
            for key in [
                "collected_at",
                "since",
                "until",
                "coverage",
                "all_boundaries_reached",
            ]
        }
    path = Path(root) / "reports/temporal_coverage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
