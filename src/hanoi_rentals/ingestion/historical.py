"""Recover historical versions of the two Hanoi feeds from timestamped CDX captures."""

import base64
import fcntl
import gzip
import hashlib
import json
import re
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

from bs4 import BeautifulSoup

from hanoi_rentals.features.dates import ZONE, today_hanoi

from .crawler import Progress, write_json
from .observations import coverage_report, record_response
from .sources import NHATOT_CATEGORIES, parse_alonhadat, parse_nhatot

# Each search is restricted to the original publisher and Hanoi rental feed.
FEEDS = {
    "nt-ap-all": "www.nhatot.com/thue-can-ho-chung-cu-ha-noi",
    "nt-room-all": "www.nhatot.com/thue-phong-tro-ha-noi",
    "alo-ap-all": "alonhadat.com.vn/cho-thue-can-ho-chung-cu/ha-noi",
    "alo-room-all": "alonhadat.com.vn/cho-thue-phong-tro-nha-tro/ha-noi",
    "nt-ap-detail": "www.nhatot.com/thue-can-ho-chung-cu-quan-bac-tu-liem-ha-noi/130566737.htm",
    "nt-bds": "www.nhatot.com/thue-bat-dong-san-ha-noi",
    "alo-old-ap": "alonhadat.com.vn/nha-dat/cho-thue/can-ho-chung-cu/ha-noi/",
    "alo-old-room": "alonhadat.com.vn/nha-dat/cho-thue/phong-tro-nha-tro/ha-noi/",
}


def retrieve(url):
    for attempt in range(3):
        try:
            with urlopen(url, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
        time.sleep(2**attempt)


def captured_day(label, captured):
    """Use a relative time only when its entire rounded interval falls on one Hanoi day."""
    match = re.fullmatch(r"(\d+)\s+(giây|phút|giờ) trước", str(label).strip(), re.IGNORECASE)
    if not match:
        return None
    seconds = {"giây": 1, "phút": 60, "giờ": 3600}[match[2].lower()]
    latest = captured - timedelta(seconds=int(match[1]) * seconds)
    earliest = latest - timedelta(seconds=seconds)
    return latest.date().isoformat() if latest.date() == earliest.date() else None


def archived_rows(html, source, category, captured):
    if source == "alonhadat":
        records = parse_alonhadat(html, category, 1)
        if not records:
            raise ValueError("No Alonhadat listing cards in capture")
        return [r for r in records if r["city"] == "Hà Nội"]
    element = BeautifulSoup(html, "lxml").select_one("script#__NEXT_DATA__")
    if element is None:
        raise ValueError("Missing Nhatot serialized listing state")
    props = json.loads(element.get_text())["props"]
    state = props.get("initialState") or props["pageProps"]["initialState"]
    if "adView" in state and state["adView"].get("adInfo", {}).get("ad"):
        ads = [state["adView"]["adInfo"]["ad"]]
    else:
        ads = state["adlisting"]["data"]["ads"]
    if not isinstance(ads, list):
        raise ValueError("Invalid archived ads")
    records = []
    for cat, code in NHATOT_CATEGORIES.items():
        if category and cat != category:
            continue
        selected = [
            a
            for a in ads
            if a.get("category") == code
            and a.get("type") == "u"
            and a.get("region_name") == "Hà Nội"
            and a.get("list_id")
        ]
        rows = parse_nhatot(json.dumps({"ads": selected}), cat, 0)
        for row, ad in zip(rows, selected, strict=True):
            if not row["posted_raw"]:
                row["posted_raw"] = captured_day(ad.get("date"), captured)
            row["source_relative_date"] = ad.get("date")
        records.extend(rows)
    return records


def capture(root, entry):
    feed, stamp, url, digest = entry
    source = "nhatot" if feed.startswith("nt-") else "alonhadat"
    cat = (
        None if feed == "nt-bds" else "nha_tro" if "room" in feed else "can_ho_chung_cu"
    )
    captured = (
        datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC).astimezone(ZONE)
    )
    replay = "https://web.archive.org/web/" + stamp + "id_/" + url
    path = root / "data/raw/historical" / source / (stamp + "-" + digest + ".bin")
    payload = path.read_bytes() if path.exists() else retrieve(replay)
    if base64.b32encode(hashlib.sha1(payload).digest()).decode() != digest:
        raise ValueError("Response differs from the indexed archive digest")
    raw = (
        gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload
    ).decode("utf-8-sig")
    records = archived_rows(raw, source, cat, captured)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    decoded = path.with_suffix(".html")
    decoded.write_bytes(raw.encode())
    return (
        decoded,
        raw,
        records,
        dict(
            original_url=url,
            replay_url=replay,
            archive_digest=digest,
            date_origin="verified_archive_capture",
            collected_at=captured.isoformat(),
            price_observed_date=str(captured.date()),
            sha256=hashlib.sha256(raw.encode()).hexdigest(),
            archive_payload_sha256=hashlib.sha256(payload).hexdigest(),
        ),
    )


def run(root, since, until):
    root = Path(root).resolve()
    start = date.fromisoformat(since)
    end = min(date.fromisoformat(until), today_hanoi())
    if start > end:
        raise ValueError("Empty historical window")
    report = {
        "since": str(start),
        "until": str(end),
        "sources": ["nhatot", "alonhadat"],
        "sampling": "Earliest accessible city page per feed and Hanoi calendar day, preferring unfiltered URLs. Frozen archive versions only.",
        "catalogs": [],
        "captures": [],
    }
    folder = root / "data/raw/historical" / (since + "_" + str(end))
    folder.mkdir(parents=True, exist_ok=True)
    entries = {}
    for feed, prefix in FEEDS.items():
        try:
            catalog = folder / (feed + ".json")
            if catalog.exists():
                rows = json.loads(catalog.read_text())
            else:
                query = urlencode(
                    dict(
                        url=prefix,
                        matchType="prefix",
                        output="json",
                        fl="timestamp,original,statuscode,digest",
                        filter="statuscode:200",
                        **{
                            "from": (start - timedelta(days=1)).strftime("%Y%m%d"),
                            "to": end.strftime("%Y%m%d"),
                        },
                    )
                )
                rows = json.loads(
                    retrieve("https://web.archive.org/cdx/search/cdx?" + query)
                )
                write_json(catalog, rows)
            report["catalogs"].append(dict(feed=feed, indexed=max(0, len(rows) - 1)))
            for stamp, url, status, digest in rows[1:]:
                captured = (
                    datetime.strptime(stamp, "%Y%m%d%H%M%S")
                    .replace(tzinfo=UTC)
                    .astimezone(ZONE)
                    .date()
                )
                if (
                    not start <= captured <= end
                    or status != "200"
                    or not re.fullmatch("[A-Z2-7]{32}", digest)
                ):
                    continue
                parts = urlsplit(url)
                if (
                    parts.scheme not in ("http", "https")
                    or parts.netloc + parts.path[: len(prefix.split("/", 1)[1]) + 1]
                    != prefix
                ):
                    continue
                key = (feed, captured)
                item = (feed, stamp, url, digest)
                if key not in entries or (len(url), stamp) < (
                    len(entries[key][2]),
                    entries[key][1],
                ):
                    entries[key] = item
        except (ValueError, KeyError, OSError) as exc:
            report["catalogs"].append(dict(feed=feed, error=str(exc)))
    output = root / "reports/historical_backfill.json"

    # Handle one monthly snapshot per source/category before adding more days.
    monthly = {}
    for entry in sorted(entries.values(), key=lambda e: (len(e[2]), e[1])):
        feed, stamp, url, digest = entry
        monthly.setdefault((feed, stamp[:6]), []).append(entry)
    schedule = sorted(
        (i, entry) for group in monthly.values() for i, entry in enumerate(group)
    )
    lock = root / ".work/crawl.lock"
    lock.parent.mkdir(exist_ok=True)
    failures = 0
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        progress = Progress(root, {"run_id": "historical"})
        for _, entry in schedule:
            feed, stamp, url, digest = entry
            source = "nhatot" if feed.startswith("nt-") else "alonhadat"
            cached = (
                root / "data/raw/historical" / source / (stamp + "-" + digest + ".bin")
            ).exists()
            error = None
            result = None
            if failures >= 3 and not cached:
                error = "Archive unavailable after three transport failures; deferred"
            else:
                if not cached:
                    time.sleep(3)
                try:
                    result = capture(root, entry)
                    if not cached:
                        failures = 0
                except HTTPError as exc:
                    error = str(exc)
                    if exc.code in (403, 429):
                        failures = 3
                except OSError as exc:
                    error = str(exc)
                    failures += 1
                except (ValueError, KeyError, TypeError) as exc:
                    error = str(exc)
            detail = dict(
                feed=feed, capture_utc=stamp, original_url=url, archive_digest=digest
            )
            if error:
                detail["error"] = error
            else:
                path, raw, rows, receipt = result
                source = "nhatot" if feed.startswith("nt-") else "alonhadat"
                rows = [
                    r
                    for r in rows
                    if not r.get("posted_raw")
                    or since <= r["posted_raw"][:10] <= receipt["price_observed_date"]
                ]
                for row in rows:
                    row["scraped_at"] = receipt["price_observed_date"]
                write_json(path.with_suffix(".meta.json"), receipt)
                added = record_response(root, path, raw, rows, source, receipt)
                count, _, _ = progress.append(rows, source)
                detail.update(
                    raw_path=str(path.relative_to(root)),
                    observations_added=added,
                    listing_ids_added=count,
                    rows=len(rows),
                )
            report["captures"].append(detail)
            write_json(output, report)
            print(stamp, feed, error or detail["rows"], flush=True)
    write_json(output, report)
    coverage_report(root)
    return report
