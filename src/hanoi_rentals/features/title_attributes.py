"""Auditable explicit claims for individual rental units."""

import re
import unicodedata
from functools import lru_cache

from hanoi_rentals.features.bedrooms import explicit_bedrooms
from hanoi_rentals.features.reference import PROJECT_ALIASES


def plain(text):
    text = unicodedata.normalize("NFKD", str(text).casefold().replace("đ", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


AREA = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*m(?:2|²)\b", re.IGNORECASE)
AMBIGUOUS = re.compile(
    r"\d\s*(?:-|–|đến|tới|/|hoặc)\s*\d+(?:[.,]\d+)?\s*m[2²]|(?:cả tòa|cả toà|mỗi sàn|mặt sàn|mỗi tầng|tổng sàn|diện tích đất)|m[²2]\s*[x×]\s*\d|\d\s*[x×]\s*\d+\s*m[²2]|(?:gần|khoảng|hơn|trên|dưới|từ)\s*\d+(?:[.,]\d+)?\s*m[²2]",
    re.IGNORECASE,
)


def area_claim(text):
    text = unicodedata.normalize("NFC", str(text))
    matches = list(AREA.finditer(text))
    if not matches:
        return None, "absent", ""
    values = {float(m[1].replace(",", ".")) for m in matches}
    evidence = " | ".join(m[0] for m in matches)
    if len(values) != 1 or AMBIGUOUS.search(text):
        return None, "ambiguous", evidence
    value = values.pop()
    return (
        (value, "explicit", evidence)
        if 5 < value <= 500
        else (None, "out_of_range", evidence)
    )


def bedroom_claim(text):
    text = unicodedata.normalize("NFC", str(text))
    if re.search(
        r"\d\s*[-–+/]\s*\d+\s*(?:pn|ngủ|phòng ngủ)|\d+\s*(?:pn|ngủ)\s*[-–/]\s*\d+\s*(?:pn|ngủ)",
        text,
        re.IGNORECASE,
    ):
        return None, "title_ambiguous"
    extra = {
        int(m)
        for pattern in (
            r"(?<!\w)(\d)\s*n(?=\s*(?:\+|[- ]?\d\s*(?:wc|k)|[,;]|$))",
            r"(?<!\w)\d\s*k\s*(\d)\s*n\b",
        )
        for m in re.findall(pattern, text, re.IGNORECASE)
    }
    base, status = explicit_bedrooms(text)
    if base is not None:
        extra.add(base)
    if status == "title_ambiguous" or len(extra) > 1:
        return None, "title_ambiguous"
    return (extra.pop(), "title_explicit") if extra else (None, "unknown")


@lru_cache(maxsize=1)
def aliases():
    return sorted(PROJECT_ALIASES, key=lambda row: -len(row["alias"]))


def project_claim(text):
    text = plain(text)
    found = set()
    for row in aliases():
        pattern = r"(?<!\w)" + re.escape(row["alias"]) + r"(?!\w)"
        for match in list(re.finditer(pattern, text)):
            if re.search(
                r"(?:\bgan|\bcanh|doi dien|\bcach|\bview|huong ra|nhin sang|\bnear)\b[^,;.]{0,30}$",
                text[: match.start()],
            ):
                return "Unknown", "proximity"
            if re.match(r"\s*[-–/]\s*\d\b", text[match.end() :]) and row[
                "project_id"
            ].startswith("ocean_park"):
                return "Unknown", "ambiguous"
            found.add(row["project_id"])
        text = re.sub(pattern, " ", text)
    if len(found) == 1:
        return found.pop(), "matched"
    return "Unknown", "ambiguous" if found else "unmatched"
