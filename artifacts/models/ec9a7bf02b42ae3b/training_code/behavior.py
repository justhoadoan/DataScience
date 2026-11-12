"""Check the public model's shape on valid layouts; do not use benchmark targets."""

import numpy as np
import pandas as pd
from .layout import maximum_bedrooms

CONTRACT_VERSION = 2


def behavior_probe(model):
    rows = []
    for category in ["can_ho_chung_cu", "nha_tro"]:
        for district in sorted(model.districts_):
            for furniture in ["Unknown", "Furnished", "Unfurnished"]:
                for area in [10, 18, 28, 40, 50, 60, 80, 100, 150]:
                    for bedrooms in [
                        None,
                        *range(maximum_bedrooms(category, area) + 1),
                    ]:
                        rows.append(
                            {
                                "category": category,
                                "district_analysis": district,
                                "area_analysis_m2": area,
                                "bedrooms_analysis": bedrooms,
                                "furniture_analysis": furniture,
                                "source": "nhatot",
                            }
                        )
    frame = pd.DataFrame(rows)
    frame["prediction"] = model.predict(frame)
    bedroom_violations = 0
    for _, group in frame.dropna(subset=["bedrooms_analysis"]).groupby(
        ["category", "district_analysis", "furniture_analysis", "area_analysis_m2"]
    ):
        bedroom_violations += int(
            (np.diff(group.sort_values("bedrooms_analysis").prediction) < -0.01).sum()
        )
    area_violations = 0
    for _, group in frame.groupby(
        ["category", "district_analysis", "furniture_analysis", "bedrooms_analysis"],
        dropna=False,
    ):
        area_violations += int(
            (np.diff(group.sort_values("area_analysis_m2").prediction) < -0.01).sum()
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "checked_rows": len(frame),
        "bedroom_decreases": bedroom_violations,
        "area_decreases": area_violations,
        "violations": bedroom_violations + area_violations,
        "assumption": "Nondecreasing area/separate bedrooms with other inputs fixed; no ordering between categories.",
    }
