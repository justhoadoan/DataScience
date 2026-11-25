"""Fresh, resumable public listing crawls with immutable retrieval evidence."""

import copy
import fcntl
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd
from curl_cffi import requests

from hanoi_rentals.features.dates import HOLDOUT_START, TARGET_END, ZONE

from .http import FetchError, fetch
from .normalization import (
    COMMON_COLUMNS,
    adapt_alonhadat,
    adapt_nhatot,
    drop_implausible,
)
from .observations import coverage_report, record_response
from .pagination import parse_page
from .sources import ALONHADAT_PATHS, NHATOT_CATEGORIES
from .temporal_policy import ensure_protocol

CATEGORIES = tuple(NHATOT_CATEGORIES)
SOURCES = ("nhatot", "alonhadat")
BLOCKED = {"verification_required", "access_denied", "rate_limited"}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


class Progress:
    """Serialize checkpoints and commit new canonical IDs after each successful page."""

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.lock = threading.Lock()
        self.path = root / "data/processed/listings.csv"
        old = (
            pd.read_csv(self.path)
            if self.path.exists()
            else pd.DataFrame(columns=COMMON_COLUMNS)
        )
        if old.listing_id.duplicated().any() or not old.category.isin(CATEGORIES).all():
            raise ValueError("Snapshot must have unique IDs and supported categories.")
        self.ids = set(old.listing_id)
        self.previous_rows = len(old)
        self.added = {source: 0 for source in SOURCES}
        self.coverage = {}
        self.checkpoint = (
            root / "data/processed/crawl_runs" / (config["run_id"] + ".json")
        )

    def save(self, info):
        with self.lock:
            self.coverage[(info["source"], info["category"])] = copy.deepcopy(info)
            write_json(
                self.checkpoint,
                {
                    **self.config,
                    "updated_at": datetime.now(ZONE).isoformat(),
                    "coverage": list(self.coverage.values()),
                    "total_snapshot_rows": len(self.ids),
                },
            )

    def append(self, rows, source):
        if not rows:
            return 0, 0, 0
        frame = pd.DataFrame(rows)
        frame = adapt_nhatot(frame) if source == "nhatot" else adapt_alonhadat(frame)
        before = len(frame)
        frame = drop_implausible(frame)[COMMON_COLUMNS]
        posted = frame.posted_date.dt.strftime("%Y-%m-%d")
        observed = frame.scraped_at.astype(str).str[:10]
        reserved = posted.between(
            str(HOLDOUT_START), str(TARGET_END)
        ) | observed.between(str(HOLDOUT_START), str(TARGET_END))
        with self.lock:
            new = frame.loc[
                ~frame.listing_id.isin(self.ids) & ~reserved
            ].drop_duplicates("listing_id")
            if len(new):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                existing = self.path.read_bytes() if self.path.exists() else b""
                # Preserve original CSV bytes/review contexts; atomic append survives termination.
                additional = new.to_csv(index=False, header=not existing).encode(
                    "utf-8"
                )
                temporary = self.path.with_suffix(".csv.tmp")
                temporary.write_bytes(existing + additional)
                temporary.replace(self.path)
                self.ids.update(new.listing_id)
                self.added[source] += len(new)
        return len(new), before - len(frame), int(reserved.sum())


def raw_manifest(root, run_id):
    directory = root / "data/raw" / run_id
    files = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "_manifest.json"
    ]
    manifest = {
        "run_id": run_id,
        "crawl_date": run_id[:10],
        "scope": CATEGORIES,
        "files": files,
    }
    write_json(directory / "_manifest.json", manifest)
    destination = root / "reports/raw_manifest_latest.json"
    write_json(destination, manifest)
    return sha256(destination.read_bytes()).hexdigest()


def page_response(session, path, url, params, resume):
    metadata = path.with_suffix(path.suffix + ".meta.json")
    if resume and path.exists() and metadata.exists():
        raw = path.read_bytes().decode("utf-8")
        evidence = json.loads(metadata.read_text())
        if sha256(raw.encode()).hexdigest() != evidence["sha256"]:
            raise ValueError(f"Cached response checksum mismatch: {path}")
        if (
            evidence.get("request_params") != params
            or evidence.get("requested_url") != url
        ):
            raise ValueError(f"Cached response belongs to a different request: {path}")
        return raw, evidence, True
    if path.exists():
        # Incomplete retrieval (e.g. process killed before metadata commit). Keep it for audit.
        path.replace(path.with_suffix(path.suffix + ".unverified"))
    raw, details = fetch(session, url, params)
    collected = datetime.fromisoformat(details["collected_at"])
    evidence = {
        **details,
        "requested_url": url,
        "request_params": params,
        "sha256": sha256(raw.encode()).hexdigest(),
        "price_observed_date": collected.date().isoformat(),
        "date_origin": "live_collection",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw.encode("utf-8"))
    temporary.replace(path)
    write_json(metadata, evidence)
    return raw, evidence, False


def crawl_source(source, root, since, until, max_pages, run_id, progress, resume=False, categories=CATEGORIES):
    session = requests.Session(impersonate="chrome")
    coverage = []
    blocked = None
    last_request = 0.0
    interval = 1.5 if source == "nhatot" else 15.0
    try:
        for category in categories:
            info = {
                "source": source,
                "category": category,
                "pages": 0,
                "downloaded_pages": 0,
                "cached_pages": 0,
                "http_attempts": 0,
                "parsed_rows": 0,
                "in_window_rows": 0,
                "new_listing_ids_seen": 0,
                "added_rows": 0,
                "added_observations": 0,
                "invalid_date_rows": 0,
                "dropped_implausible_rows": 0,
                "reserved_observations": 0,
                "stop_reason": "running",
                "source_exhausted": False,
                "window_boundary_reached": False,
            }
            if blocked:
                info.update(
                    stop_reason="source_deferred",
                    error=f"Source stopped after {blocked}; no further requests sent.",
                )
                progress.save(info)
                coverage.append(info)
                continue
            seen, fingerprints, repeated_pages = set(), set(), 0
            offset, page = 0, 1
            url = (
                "https://gateway.chotot.com/v1/public/ad-listing"
                if source == "nhatot"
                else "https://alonhadat.com.vn" + ALONHADAT_PATHS[category]
            )
            while not max_pages or page <= max_pages:
                info["next_page"] = page
                progress.save(info)
                suffix = "json" if source == "nhatot" else "html"
                path = (
                    root / "data/raw" / run_id / source / category / f"p{page}.{suffix}"
                )
                params = (
                    {
                        "cg": NHATOT_CATEGORIES[category],
                        "region_v2": 12000,
                        "st": "u,h",
                        "o": offset,
                        "limit": 50,
                    }
                    if source == "nhatot"
                    else None
                )
                try:
                    cache_ready = (
                        resume
                        and path.exists()
                        and path.with_suffix(path.suffix + ".meta.json").exists()
                    )
                    if not cache_ready:
                        time.sleep(
                            max(0.0, interval - (time.monotonic() - last_request))
                        )
                    try:
                        raw, evidence, cached = page_response(
                            session, path, url, params, resume
                        )
                    finally:
                        if not cache_ready:
                            last_request = time.monotonic()
                    info["cached_pages" if cached else "downloaded_pages"] += 1
                    if not cached:
                        info["http_attempts"] += evidence["http_attempts"]
                    rows, paging = parse_page(
                        raw, source, category, page, offset, info.get("reported_pages")
                    )
                    info["pages"] = page
                    info["parsed_rows"] += len(rows)
                    for key in ("reported_total", "reported_pages"):
                        if paging.get(key) is not None:
                            info[key] = paging[key]
                    digest = sha256(raw.encode()).hexdigest()
                    repeated_response = digest in fingerprints
                    fingerprints.add(digest)
                    fresh_ids = {str(row["listing_id"]) for row in rows} - seen
                    seen.update(str(row["listing_id"]) for row in rows)
                    repeated_pages = repeated_pages + 1 if rows and not fresh_ids else 0
                    info["new_listing_ids_seen"] += len(fresh_ids)
                    selected = []
                    for row in rows:
                        posted = pd.to_datetime(row.get("posted_raw"), errors="coerce")
                        if pd.isna(posted):
                            info["invalid_date_rows"] += 1
                            continue
                        day = posted.date()
                        info["oldest_seen"] = min(
                            info.get("oldest_seen", str(day)), str(day)
                        )
                        info["newest_seen"] = max(
                            info.get("newest_seen", str(day)), str(day)
                        )
                        info["window_boundary_reached"] |= day <= since
                        if since <= day <= until:
                            row["scraped_at"] = evidence["price_observed_date"]
                            selected.append(row)
                    info["in_window_rows"] += len(selected)
                    info["added_observations"] += record_response(
                        root, path, raw, selected, source, evidence
                    )
                    added, dropped, reserved = progress.append(selected, source)
                    info["added_rows"] += added
                    info["dropped_implausible_rows"] += dropped
                    info["reserved_observations"] += reserved
                    print(
                        f"{run_id} {source}/{category} p{page}: {'cache' if cached else 'HTTP'}; {len(rows)} parsed; {len(fresh_ids)} unique IDs; oldest={info.get('oldest_seen')}",
                        flush=True,
                    )
                    if paging["exhausted"]:
                        info.update(
                            stop_reason="end_of_results",
                            source_exhausted=True,
                            next_page=None,
                        )
                        break
                    if repeated_response or repeated_pages >= 3:
                        info.update(
                            stop_reason="pagination_stalled",
                            error="Repeated pages without reliable end-of-results evidence.",
                        )
                        break
                    # Never stop on a reported total or a few old/pinned listings.
                    if source == "nhatot":
                        offset = paging["next_offset"]
                    else:
                        url = paging["next_url"]
                    page += 1
                    info["next_page"] = page
                    progress.save(info)
                except FetchError as exc:
                    info.update(
                        stop_reason=exc.kind,
                        error=str(exc),
                        failed_page=page,
                        http_status=exc.status,
                        retry_after_seconds=exc.retry_after,
                    )
                    info["http_attempts"] += exc.attempts
                    if exc.body:
                        evidence_path = path.parent / "errors" / f"p{page}.html"
                        evidence_path.parent.mkdir(parents=True, exist_ok=True)
                        evidence_path.write_text(exc.body)
                        info["failure_response"] = str(evidence_path.relative_to(root))
                    if exc.kind in BLOCKED:
                        blocked = exc.kind
                    print(f"{source}/{category} p{page}: {exc}", flush=True)
                    break
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    info.update(
                        stop_reason="invalid_response", error=str(exc), failed_page=page
                    )
                    print(
                        f"{source}/{category} p{page}: invalid_response: {exc}",
                        flush=True,
                    )
                    break
            else:
                info["stop_reason"] = "page_limit"
            progress.save(info)
            coverage.append(info)
    finally:
        session.close()
    return coverage


def crawl(root, since, until, max_pages=0, *, resume=None, sources=None, categories=None):
    root = Path(root).resolve()
    lock = root / ".work/crawl.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _crawl(root, since, until, max_pages, resume, sources, categories)


def _crawl(root, since, until, max_pages, resume, sources, categories):
    since, requested_until = (
        date.fromisoformat(str(since)),
        date.fromisoformat(str(until)),
    )
    today = datetime.now(ZONE).date()
    if since > requested_until or since > today or max_pages < 0:
        raise ValueError(
            "Invalid crawl window or page limit (0 means no artificial page cap)."
        )
    sources = list(dict.fromkeys(sources or SOURCES))
    if not set(sources).issubset(SOURCES):
        raise ValueError("Unknown crawl source.")
    categories = list(dict.fromkeys(categories or CATEGORIES))
    if not set(categories).issubset(CATEGORIES):
        raise ValueError("Unknown crawl category.")
    until = min(requested_until, today)
    if resume:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}\d{6}", resume):
            raise ValueError("Use the run_id from a new crawler checkpoint to resume.")
        checkpoint = root / "data/processed/crawl_runs" / (resume + ".json")
        config = json.loads(checkpoint.read_text())
        if (
            config["since"] != str(since)
            or config["requested_until"] != str(requested_until)
            or config["sources"] != sources
            or config.get("categories", list(CATEGORIES)) != categories
        ):
            raise ValueError(
                "Resume parameters differ from the saved run; start a new crawl instead."
            )
        if not (root / "data/raw" / resume).exists():
            raise ValueError(
                "Raw responses for this run are missing; restore them or start a fresh run."
            )
        until = date.fromisoformat(config["until"])
        run_id = resume
    else:
        run_id = datetime.now(ZONE).strftime("%Y-%m-%dT%H%M%S%f")
    ensure_protocol(root)
    previous_manifest = root / "reports/raw_manifest_latest.json"
    if previous_manifest.exists():
        previous = json.loads(previous_manifest.read_text())
        archive = (
            root
            / "data/raw"
            / previous.get("run_id", previous["crawl_date"])
            / "_manifest.json"
        )
        if not archive.exists():
            write_json(archive, previous)
    config = {
        "run_id": run_id,
        "since": str(since),
        "until": str(until),
        "requested_until": str(requested_until),
        "sources": sources,
        "categories": categories,
    }
    progress = Progress(root, config)
    print(
        f"Crawl run {run_id}: {'resume verified cache' if resume else 'fresh network retrieval'}; {since} through {until}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        jobs = [
            pool.submit(
                crawl_source,
                source,
                root,
                since,
                until,
                max_pages,
                run_id,
                progress,
                bool(resume),
                categories,
            )
            for source in sources
        ]
        coverage = [entry for job in jobs for entry in job.result()]
    exhausted = all(c["source_exhausted"] for c in coverage)
    summary = {
        **config,
        "collected_at": datetime.now(ZONE).isoformat(),
        "mode": "resume" if resume else "fresh",
        "status": "complete" if exhausted else "partial",
        "future_collection_pending": requested_until > today,
        "previous_rows": progress.previous_rows,
        "added_rows": sum(progress.added.values()),
        "total_rows": len(progress.ids),
        "added_by_source": progress.added,
        **{
            key: sum(c[key] for c in coverage)
            for key in (
                "downloaded_pages",
                "cached_pages",
                "http_attempts",
                "added_observations",
                "dropped_implausible_rows",
                "reserved_observations",
            )
        },
        "coverage": coverage,
        "all_sources_exhausted": exhausted,
        "all_boundaries_reached": all(c["window_boundary_reached"] for c in coverage),
        "historical_completeness_verified": False,
        "limit": "Date bounds filter retrieved listings; they do not request archived historical prices. Exhausting live feeds does not establish historical completeness.",
        "checkpoint": str(progress.checkpoint.relative_to(root)),
        "raw_manifest": "reports/raw_manifest_latest.json",
        "raw_manifest_sha256": raw_manifest(root, run_id),
    }
    write_json(root / "reports/crawl_latest.json", summary)
    write_json(root / "reports/crawl_runs" / (run_id + ".json"), summary)
    coverage_report(root)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary
