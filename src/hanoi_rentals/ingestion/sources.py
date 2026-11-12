"""Parse public listing responses into source records. Source text stays intact."""

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

BASE = "https://alonhadat.com.vn"
ID_RE = re.compile(r"-(\d+)\.html$")
RENT_TYPE = "u"
FURNISHING_LABELS = {1: "Đầy đủ", 2: "Đầy đủ", 3: "Trống"}
NHATOT_CATEGORIES = {"can_ho_chung_cu": 1010, "nha_tro": 1050}
ALONHADAT_PATHS = {
    "can_ho_chung_cu": "/cho-thue-can-ho-chung-cu/ha-noi",
    "nha_tro": "/cho-thue-phong-tro-nha-tro/ha-noi",
}


def parse_nhatot(raw_json, cat, offset):
    data = json.loads(raw_json)
    rows = []
    for ad in data.get("ads", []):
        if ad.get("type") != RENT_TYPE:
            continue  # skip for-sale ads
        list_time = ad.get("list_time")
        posted = (
            datetime.fromtimestamp(list_time / 1000, ZoneInfo("Asia/Ho_Chi_Minh"))
            .date()
            .isoformat()
            if list_time
            else None
        )
        rows.append(
            {
                "listing_id": ad.get("list_id"),
                "category": cat,
                "url": f"https://www.nhatot.com/{ad.get('list_id')}.htm",
                "title": ad.get("subject"),
                "price_raw": ad.get("price_string"),
                "price": ad.get("price"),
                "area_raw": ad.get("size"),
                "bedrooms_raw": ad.get("rooms"),
                "toilets_raw": ad.get("toilets"),
                "furniture": FURNISHING_LABELS.get(
                    ad.get("furnishing_sell") or ad.get("furnishing_rent")
                ),
                "location_raw": " - ".join(
                    filter(
                        None,
                        [
                            ad.get("street_name"),
                            ad.get("ward_name"),
                            ad.get("area_name"),
                        ],
                    )
                ),
                "region_name": ad.get("region_name"),
                "posted_raw": posted,
                "body": (ad.get("body") or "")[:500],  # keep for debugging/cleaning
                "page_offset": offset,
                "scraped_at": date.today().isoformat(),
            }
        )
    return rows


def first_text(card, selector):
    el = card.select_one(selector)
    return el.get_text(" ", strip=True) if el else None


def parse_alonhadat(html, cat, page):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for card in soup.select("article.property-item"):
        link = card.select_one("a.link")
        href = link.get("href", "") if link else ""
        m = ID_RE.search(href)
        if not m:
            continue

        price_el = card.select_one(".price [itemprop=price]")
        price_vnd = (
            int(price_el["content"])
            if price_el and price_el.get("content", "").isdigit()
            else None
        )
        time_el = card.select_one("time.created-date")

        rows.append(
            {
                "listing_id": m.group(1),
                "category": cat,
                "url": href if href.startswith("http") else BASE + href,
                "title": first_text(card, "h3.property-title"),
                "price_vnd": price_vnd,
                "price_raw": first_text(card, ".price"),
                "area_raw": first_text(card, ".area [itemprop=value]"),
                "bedrooms_raw": first_text(card, ".bedroom [itemprop=value]"),
                "street": first_text(card, "[itemprop=streetAddress]"),
                "ward": first_text(card, "[itemprop=addressLocality]"),
                "city": first_text(card, "[itemprop=addressRegion]"),
                "old_address_raw": first_text(card, "p.old-address span"),
                "posted_raw": time_el.get("datetime") if time_el else None,
                "body": (first_text(card, "p.brief") or "")
                .replace("<< Xem chi tiết >>", "")
                .strip()[:500],
                "page": page,
                "scraped_at": date.today().isoformat(),
            }
        )
    return rows
