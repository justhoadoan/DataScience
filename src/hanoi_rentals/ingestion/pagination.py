"""Validate result pages before interpreting any response as end-of-results."""

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .sources import ALONHADAT_PATHS, parse_alonhadat, parse_nhatot


def parse_page(raw, source, category, page, offset=0, known_pages=None):
    if source == "nhatot":
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("ads"), list):
            raise ValueError(
                "Nhatot response has no valid ads array; not end-of-results."
            )
        ads = payload["ads"]
        if any(not isinstance(ad, dict) or "type" not in ad for ad in ads):
            raise ValueError("Invalid Nhatot ad item; incomplete result page.")
        total = payload.get("total")
        if total is not None and (
            isinstance(total, bool) or not isinstance(total, int) or total < 0
        ):
            raise ValueError("Invalid Nhatot total.")
        rows = parse_nhatot(raw, category, offset)
        if any(row["listing_id"] is None for row in rows):
            raise ValueError("Nhatot rental record is missing its listing ID.")
        return rows, {
            "returned_items": len(ads),
            "reported_total": total,
            "exhausted": not ads,
            "next_offset": offset + len(ads),
        }
    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text(" ", strip=True)
    cards = soup.select("article.property-item")
    count_match = re.search(r"Tìm thấy\s+([\d.,]+)\s+tin", text, re.IGNORECASE)
    page_match = re.search(
        r"(?:đang xem\s+)?trang\s+(\d+)\s+trong tổng số\s+([\d.,]+)\s+trang",
        text,
        re.IGNORECASE,
    )
    reported_total = int(re.sub(r"[.,]", "", count_match[1])) if count_match else None
    pages = int(re.sub(r"[.,]", "", page_match[2])) if page_match else known_pages
    if page_match and int(page_match[1]) != page:
        raise ValueError(
            f"Requested Alonhadat page {page}, received page {page_match[1]}."
        )
    if not cards:
        if reported_total == 0:
            return [], {"returned_items": 0, "reported_total": 0, "exhausted": True}
        raise ValueError(
            "No listing cards and no explicit zero-result count; page may be a challenge or changed layout."
        )
    rows = parse_alonhadat(raw, category, page)
    if len(rows) != len(cards):
        raise ValueError(
            f"Parsed {len(rows)}/{len(cards)} Alonhadat cards; inspect layout instead of dropping records."
        )
    base = "https://alonhadat.com.vn" + ALONHADAT_PATHS[category]
    next_url = None
    for link in soup.find_all("a", href=True):
        candidate = urljoin(base, link["href"])
        parsed = urlparse(candidate)
        if parsed.netloc == "alonhadat.com.vn" and re.fullmatch(
            re.escape(ALONHADAT_PATHS[category]) + rf"/trang-+{page + 1}(?:\.html?)?",
            parsed.path,
        ):
            next_url = candidate
            break
    exhausted = next_url is None and pages is not None and page >= pages
    if not exhausted and next_url is None:
        if pages is None:
            raise ValueError(
                "Missing next link and last-page evidence; not a verified end-of-results."
            )
        next_url = base + f"/trang-{page + 1}"
    return rows, {
        "returned_items": len(cards),
        "reported_total": reported_total,
        "reported_pages": pages,
        "exhausted": exhausted,
        "next_url": next_url,
    }
