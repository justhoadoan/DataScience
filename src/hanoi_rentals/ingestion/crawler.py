"""Date-bounded, cached public listing crawl with append-only snapshot updates."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import time

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

from .sources import NHATOT_CATEGORIES, ALONHADAT_PATHS, parse_nhatot, parse_alonhadat
from .normalization import (
    COMMON_COLUMNS,
    adapt_nhatot,
    adapt_alonhadat,
    drop_implausible,
)

CATEGORIES = tuple(NHATOT_CATEGORIES)
ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def raw_manifest(root, run_date):
    files = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted((root / "data/raw" / run_date).rglob("*"))
        if path.is_file()
    ]
    destination = root / "reports/raw_manifest_latest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"crawl_date": run_date, "scope": CATEGORIES, "files": files}, indent=2
        )
        + "\n"
    )
    return sha256(destination.read_bytes()).hexdigest()


def fetch(session, url, params=None):
    for attempt in range(3):
        response = session.get(url, params=params, timeout=35)
        if response.status_code == 200:
            return response.text
        if response.status_code not in (429, 500, 502, 503, 504):
            raise RuntimeError(f"HTTP {response.status_code}: {url}")
        time.sleep((60 if response.status_code == 429 else 10) * (attempt + 1))
    raise RuntimeError(f"Fetch failed after retry: {url}")


def crawl_source(source, root, since, until, max_pages, run_date):
    session = requests.Session(impersonate="chrome")
    records, coverage = [], []
    for category in CATEGORIES:
        seen, fingerprints, old_pages, repeated_pages = set(), set(), 0, 0
        info = {
            "source": source,
            "category": category,
            "pages": 0,
            "stop_reason": "page_limit",
            "window_boundary_reached": False,
        }
        for page in range(1, max_pages + 1):
            suffix = "json" if source == "nhatot" else "html"
            path = (
                root / "data/raw" / run_date / source / category / f"p{page}.{suffix}"
            )
            try:
                if path.exists():
                    raw = path.read_text(encoding="utf-8")
                else:
                    if source == "nhatot":
                        raw = fetch(
                            session,
                            "https://gateway.chotot.com/v1/public/ad-listing",
                            {
                                "cg": NHATOT_CATEGORIES[category],
                                "region_v2": 12000,
                                "st": "u,h",
                                "o": (page - 1) * 50,
                                "limit": 50,
                            },
                        )
                    else:
                        url = "https://alonhadat.com.vn" + ALONHADAT_PATHS[category]
                        raw = fetch(
                            session, url + (f"/trang-{page}" if page > 1 else "")
                        )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(raw, encoding="utf-8")
                    time.sleep(1.5 if source == "nhatot" else 15)
                fingerprint = sha256(raw.encode()).hexdigest()
                if fingerprint in fingerprints:
                    info["stop_reason"] = "repeated_response"
                    break
                fingerprints.add(fingerprint)
                parsed = (
                    parse_nhatot(raw, category, (page - 1) * 50)
                    if source == "nhatot"
                    else parse_alonhadat(raw, category, page)
                )
                info["pages"] = page
                if not parsed:
                    info.update(
                        stop_reason="end_of_results", window_boundary_reached=True
                    )
                    break
                fresh = [r for r in parsed if str(r["listing_id"]) not in seen]
                seen.update(str(r["listing_id"]) for r in parsed)
                repeated_pages = repeated_pages + 1 if not fresh else 0
                dates = pd.to_datetime(
                    pd.Series([r["posted_raw"] for r in fresh]), errors="coerce"
                )
                if dates.notna().any():
                    oldest = dates.min().date().isoformat()
                    info["oldest_seen"] = min(info.get("oldest_seen", oldest), oldest)
                old_pages = (
                    old_pages + 1
                    if len(dates)
                    and dates.notna().all()
                    and (dates.dt.date < since).all()
                    else 0
                )
                for row in fresh:
                    posted = pd.to_datetime(row.get("posted_raw"), errors="coerce")
                    if pd.notna(posted) and since <= posted.date() <= until:
                        row["scraped_at"] = run_date
                        records.append(row)
                print(
                    f"{source}/{category} p{page}: {len(fresh)} new IDs; oldest={info.get('oldest_seen')}",
                    flush=True,
                )
                if old_pages >= 3:
                    info.update(
                        stop_reason="three_pages_before_start",
                        window_boundary_reached=True,
                    )
                    break
                if repeated_pages >= 3:
                    info["stop_reason"] = "repeated_listing_pages"
                    break
                if source == "nhatot" and page * 50 >= (
                    json.loads(raw).get("total") or 0
                ):
                    info.update(
                        stop_reason="end_of_results", window_boundary_reached=True
                    )
                    break
                if source == "alonhadat":
                    soup = BeautifulSoup(raw, "lxml")
                    import re

                    if not soup.find(
                        "a", href=re.compile(rf"/trang-+{page + 1}(\.html?)?$")
                    ):
                        info.update(
                            stop_reason="end_of_results", window_boundary_reached=True
                        )
                        break
            except Exception as exc:
                info.update(stop_reason="error", error=str(exc))
                break
        coverage.append(info)
    session.close()
    if not records:
        return pd.DataFrame(columns=COMMON_COLUMNS), coverage
    frame = pd.DataFrame(records).drop_duplicates("listing_id")
    adapted = adapt_nhatot(frame) if source == "nhatot" else adapt_alonhadat(frame)
    return adapted[COMMON_COLUMNS], coverage


def crawl(root, since, until, max_pages=120):
    root = Path(root)
    since, until = date.fromisoformat(str(since)), date.fromisoformat(str(until))
    today = datetime.now(ZONE).date()
    if since > until or until > today or max_pages < 1:
        raise ValueError("Invalid crawl window or page limit.")
    path = root / "data/processed/listings.csv"
    old = (
        pd.read_csv(path, encoding="utf-8-sig")
        if path.exists()
        else pd.DataFrame(columns=COMMON_COLUMNS)
    )
    if old.listing_id.duplicated().any() or not old.category.isin(CATEGORIES).all():
        raise ValueError("Snapshot must have unique IDs and only apartments/rooms.")
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                crawl_source, source, root, since, until, max_pages, today.isoformat()
            )
            for source in ["nhatot", "alonhadat"]
        ]
        results = [job.result() for job in jobs]
    collected = pd.concat([item[0] for item in results], ignore_index=True)
    collected = collected.drop_duplicates("listing_id")
    before_cleaning = len(collected)
    collected = drop_implausible(collected)
    new = collected.loc[~collected.listing_id.isin(old.listing_id)]
    # Historical fields and reviewed contexts are append-only; observations are cached above.
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        collected.to_csv(path, index=False, encoding="utf-8-sig")
    elif len(new):
        new.to_csv(path, mode="a", header=False, index=False, encoding="utf-8")
    coverage = [entry for result in results for entry in result[1]]
    summary = {
        "collected_at": datetime.now(ZONE).isoformat(),
        "since": str(since),
        "until": str(until),
        "previous_rows": len(old),
        "dropped_implausible_rows": before_cleaning - len(collected),
        "added_rows": len(new),
        "total_rows": len(old) + len(new),
        "added_early_month": int(pd.to_datetime(new.posted_date).dt.day.le(13).sum()),
        "added_by_source": new.source.value_counts().to_dict(),
        "coverage": coverage,
        "all_boundaries_reached": all(c["window_boundary_reached"] for c in coverage),
        "limit": "Only currently accessible ads; deleted ads and original publication dates cannot be reconstructed.",
        "raw_manifest": "reports/raw_manifest_latest.json",
        "raw_manifest_sha256": raw_manifest(root, today.isoformat()),
    }
    destination = root / "reports/crawl_latest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary
