"""Read Phongtro123's public Hanoi rental feeds with explicit page and date evidence."""

import json
import re
from datetime import date, datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

BASE = "https://phongtro123.com"
PATHS = {
    "can_ho_chung_cu": "/cho-thue-can-ho-chung-cu-ha-noi",
    "nha_tro": "/tinh-thanh/ha-noi",
}
DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
LISTING_ID = re.compile(r"-pr(\d+)\.html$")
MONTHLY_PRICE = re.compile(r"([\d.,]+)\s*(triệu|nghìn|ngàn|đồng|đ)/\s*tháng", re.I)
AREA = re.compile(r"([\d.,]+)\s*m[²2]", re.I)


def page_url(category, page):
    params = {"orderby": "moi-nhat"}
    if page > 1:
        params["page"] = page
    return BASE + PATHS[category] + "?" + urlencode(params)


def read_number(text):
    if re.fullmatch(r"\d+[.,]\d{1,2}|\d+", text):
        return float(text.replace(",", "."))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        return float(text.replace(".", ""))
    return None


def displayed_date(card):
    stamp = card.select_one("time")
    if not stamp:
        return None, None
    label = (
        stamp.get("title") or stamp.get("aria-label") or stamp.get_text(" ", strip=True)
    )
    if stamp.get("datetime"):
        try:
            value = stamp["datetime"]
            day = (
                date.fromisoformat(value)
                if len(value) == 10
                else datetime.fromisoformat(value).date()
            )
            return day.isoformat(), label
        except ValueError:
            pass
    match = DATE.search(label)
    if match:
        try:
            return datetime.strptime(match[0], "%d/%m/%Y").date().isoformat(), label
        except ValueError:
            pass
    return None, label


def listing(card, category):
    link = card.select_one("h3 a[href]")
    url = urljoin(BASE, link["href"]) if link else ""
    target = urlsplit(url)
    identity = LISTING_ID.search(target.path)
    if (
        not identity
        or target.netloc != urlsplit(BASE).netloc
        or target.scheme != "https"
    ):
        raise ValueError("Phongtro123 listing card has no valid listing URL.")
    script = card.select_one('script[type="application/ld+json"]')
    address = json.loads(script.get_text()).get("address", {}) if script else {}
    street = address.get("streetAddress") or ""
    city = address.get("addressLocality")
    location = card.select_one(".geo-alt + a")
    label = location.get_text(" ", strip=True) if location else ""
    district, _, locality = label.rpartition(",")
    district = district.strip() if locality.strip() == "Hà Nội" else None
    ward = re.search(r"(?:^|,\s*)((?:Phường|Xã|Thị trấn)\s+[^,]+)", street, re.I)
    price_tag = card.select_one(".text-green")
    size_tag = card.select_one(".dot + span")
    price_raw = price_tag.get_text(" ", strip=True) if price_tag else ""
    area_raw = size_tag.get_text("", strip=True) if size_tag else ""
    price = MONTHLY_PRICE.fullmatch(price_raw)
    amount = read_number(price[1]) if price else None
    factor = {"triệu": 1_000_000, "nghìn": 1_000, "ngàn": 1_000, "đồng": 1, "đ": 1}
    area = AREA.fullmatch(area_raw)
    posted, date_label = displayed_date(card)
    description = card.select_one("p.line-clamp-2")
    return {
        "listing_id": identity[1],
        "category": category,
        "url": url,
        "title": link.get_text(" ", strip=True),
        "price_vnd": round(amount * factor[price[2].lower()])
        if amount is not None
        else None,
        "price_raw": price_raw,
        "area_m2": read_number(area[1]) if area else None,
        "area_raw": area_raw,
        "district": district,
        "ward": ward[1] if ward else None,
        "city": city or ("Hà Nội" if locality.strip() == "Hà Nội" else None),
        "location_raw": street or label,
        "posted_raw": posted,
        "source_posted_label": date_label,
        "body": description.get_text(" ", strip=True) if description else "",
    }


def parse_phongtro123(raw, category, page):
    soup = BeautifulSoup(raw, "lxml")
    cards = soup.select("ul.post__listing > li")
    count = re.search(
        r"Có\s+([\d.,]+)\s+tin đăng cho thuê", soup.get_text(" ", strip=True)
    )
    total = int(re.sub(r"[.,]", "", count[1])) if count else None
    active = soup.select_one(".pagination .active .page-link")
    current = active.get_text(strip=True) if active else None
    if current is not None and current != str(page):
        raise ValueError(f"Requested Phongtro123 page {page}, received page {current}.")
    if not cards and total != 0:
        raise ValueError(
            "Missing Phongtro123 listings and explicit zero-result evidence."
        )
    rows = [listing(card, category) for card in cards]
    next_url = None
    next_link = next(
        (
            link
            for link in soup.select('.pagination a[rel~="next"]')
            if "Trang sau" in link.get_text(" ", strip=True)
        ),
        None,
    )
    if next_link:
        candidate = urlsplit(urljoin(BASE, next_link["href"]))
        params = parse_qs(candidate.query)
        if (
            candidate.scheme != "https"
            or candidate.netloc != urlsplit(BASE).netloc
            or candidate.path != PATHS[category]
            or params.get("page") != [str(page + 1)]
            or params.get("orderby") != ["moi-nhat"]
        ):
            raise ValueError("Unexpected Phongtro123 next page link.")
        next_url = page_url(category, page + 1)
    last_page = any(
        "Trang sau" in element.get_text(" ", strip=True)
        for element in soup.select(".pagination .disabled")
    )
    exhausted = (
        total == 0
        or last_page
        or (page == 1 and total is not None and total == len(cards))
    )
    if next_url:
        exhausted = False
    elif not exhausted:
        raise ValueError(
            "Missing Phongtro123 next page link and end-of-results evidence."
        )
    return rows, {"reported_total": total, "next_url": next_url, "exhausted": exhausted}
