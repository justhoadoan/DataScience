"""Product plausibility rules for separate bedrooms; these are not building regulations."""

import math
import re

LAYOUT_POLICY = {
    "shared_area_m2": 8,
    "area_per_separate_bedroom_m2": 10,
    "category_max_bedrooms": {"can_ho_chung_cu": 6, "nha_tro": 2},
    "bedrooms_meaning": "Separate sleeping rooms; studio/open-plan sleeping area is 0. Unknown stays missing.",
    "kind": "Product plausibility heuristic, not a legal standard or floor-plan verification",
}


def maximum_bedrooms(category, area):
    cap = LAYOUT_POLICY["category_max_bedrooms"][category]
    if area is None:
        return cap
    if not math.isfinite(float(area)):
        return 0
    space = max(
        0,
        math.floor(
            (float(area) - LAYOUT_POLICY["shared_area_m2"])
            / LAYOUT_POLICY["area_per_separate_bedroom_m2"]
        ),
    )
    return min(cap, space)


def layout_error(category, area, bedrooms):
    if bedrooms is None:
        return None
    maximum = maximum_bedrooms(category, area)
    if bedrooms > maximum:
        area_label = f"diện tích {area:g} m²" if area is not None else "loại căn này"
        return (
            f"Với {area_label}, ứng dụng chỉ hỗ trợ tối đa {maximum} phòng ngủ riêng. "
            "Chọn 0 nếu là studio/phòng khép kín không ngăn phòng ngủ; chưa rõ thì để trống."
        )
    return None


COUNT_PATTERNS = [
    re.compile(r"(?<!\d)(\d{1,2})\s*(?:pn\b|phòng\s*ngủ\b|ngủ\b)", re.I),
    re.compile(r"(?<!\d)(\d{1,2})\s*n\s*\d\s*k\b", re.I),
]
STUDIO = re.compile(
    r"\bstudio\b|không\s*(?:có\s*)?phòng\s*ngủ\s*riêng|không\s*ngăn\s*phòng", re.I
)


def explicit_bedrooms(title):
    """Read an unambiguous layout claim; do not infer zero from a missing source count."""
    values = {
        int(match)
        for pattern in COUNT_PATTERNS
        for match in pattern.findall(str(title))
    }
    if STUDIO.search(str(title)):
        values.add(0)
    if len(values) == 1:
        return next(iter(values)), "title_explicit"
    return None, "title_ambiguous" if values else "unknown"
