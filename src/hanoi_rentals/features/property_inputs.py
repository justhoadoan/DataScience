"""Shared values for optional property inputs in training and serving."""

import pandas as pd

from hanoi_rentals.features.reference import PROJECT_ALIASES
from hanoi_rentals.features.title_attributes import plain
from hanoi_rentals.ingestion.normalization import strip_admin_prefix


def bathroom_value(value):
    return str(int(value)) if pd.notna(value) else "Unknown"


def property_options(data):
    """Build choices from training inputs, without using prices.

    Ward encodings stay source scoped. For an identically named ward/district,
    the form uses the most observed encoding; it never merges training keys.
    """
    wards = data.loc[data.ward_key.ne("Unknown")].copy()
    wards["label"] = wards.ward.map(strip_admin_prefix)
    wards = (
        wards.groupby(["ward_key", "district_analysis", "label"])
        .size()
        .rename("n")
        .reset_index()
        .sort_values(["n", "ward_key"], ascending=[False, True])
    )
    wards["name_key"] = wards.label.map(plain)
    wards = wards.drop_duplicates(["district_analysis", "name_key"])
    aliases = {r["project_id"]: r["alias"].title() for r in PROJECT_ALIASES}
    projects = []
    for key, rows in data.loc[data.project_id.ne("Unknown")].groupby("project_id"):
        names = rows.source_project_name.dropna().astype(str)
        names = names.loc[names.str.strip().ne("")]
        label = aliases.get(key) or (names.mode().iloc[0] if len(names) else None)
        if label:
            projects.append(
                {
                    "value": key,
                    "label": label,
                    "districts": sorted(rows.district_analysis.unique()),
                }
            )
    return {
        "wards": [
            {"value": r.ward_key, "label": r.label, "district": r.district_analysis}
            for r in wards.sort_values(["district_analysis", "label"]).itertuples()
        ],
        "projects": sorted(projects, key=lambda r: r["label"]),
        "bathrooms": sorted({int(n) for n in data.toilets_analysis.dropna()}),
    }
