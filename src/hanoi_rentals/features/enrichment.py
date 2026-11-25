"""Join only exact archived versions and retain evidence for recovered features."""

import numpy as np
import pandas as pd

from hanoi_rentals.features.bedrooms import maximum_bedrooms
from hanoi_rentals.features.reference import WARD_SCHEMES
from hanoi_rentals.features.title_attributes import (
    area_claim,
    bedroom_claim,
    plain,
    project_claim,
)
from hanoi_rentals.ingestion.normalization import (
    extract_furniture_full,
    strip_admin_prefix,
)
from hanoi_rentals.ingestion.observations import load_observations


def match_versions(root, frame):
    obs = load_observations(root, before="2026-12-01")
    attrs = [
        "body",
        "source_project_id",
        "source_project_name",
        "source_latitude",
        "source_longitude",
        "source_subtype",
        "source_original_timestamp_ms",
    ]
    keys = [
        "source",
        "category",
        "listing_id",
        "price_vnd",
        "price_raw",
        "title",
        "posted_date",
        "scraped_at",
    ]
    frame = frame.copy()
    verified = obs.loc[
        obs.date_origin.isin(
            ["live_collection", "verified_manifest_day", "verified_archive_capture"]
        )
    ].copy()
    verified["scraped_at"] = verified.price_observed_date
    # If several distinct descriptions/structured attributes match the same coarse CSV
    # version, a date-only snapshot cannot tell which response supplied that version.
    versions = verified.reindex(
        columns=keys + attrs + ["raw_path", "raw_sha256"]
    ).sort_values("raw_path")
    versions = versions.drop_duplicates(keys + attrs)
    exact = versions.loc[~versions.duplicated(keys, keep=False)].dropna(
        subset=["raw_sha256"]
    )
    frame = frame.merge(exact, on=keys, how="left", validate="many_to_one")
    frame["raw_match_status"] = np.select(
        [frame.raw_sha256.notna(), frame.listing_id.isin(verified.listing_id)],
        ["exact_version", "different_or_ambiguous_version"],
        default="unavailable",
    )
    return frame


def enrich(frame):
    frame = frame.copy()
    schemes = {row["source"]: row["scheme"] for row in WARD_SCHEMES}
    features = []
    for row in frame.itertuples():
        body = row.body if isinstance(row.body, str) else ""
        a, status, evidence = area_claim(row.title)
        desc, ds, de = area_claim(body)
        origin = "title" if a is not None else "unknown"
        if status == "absent" and ds != "absent":
            a, status, evidence, origin = desc, ds, de, "description"
        elif a is not None and (ds == "ambiguous" or desc is not None and desc != a):
            a, status, origin = None, "text_conflict", "unknown"
        original = row.area_analysis_m2
        if pd.notna(original):
            if a is not None and abs(a - original) > max(2, 0.05 * original):
                status = "source_text_conflict"
            a, origin = original, "structured"
        elif str(row.area_decision) in ("exclude", "unresolved") or a is None:
            a, origin = np.nan, "unknown"
        bed, bs = bedroom_claim(row.title)
        bd, bds = bedroom_claim(body)
        b, bo = row.bedrooms_analysis, row.bedrooms_origin
        if bs == "title_ambiguous" or (
            bed is not None and bd is not None and bed != bd
        ):
            b, bo = np.nan, "text_conflict"
        elif bo not in (
            "source_title_conflict",
            "title_ambiguous",
            "implausible_layout",
        ):
            count, from_where = (
                (bed, "title_explicit")
                if bed is not None
                else (bd, "description_explicit")
            )
            if count is not None:
                if (pd.notna(b) and b != count) or count > maximum_bedrooms(
                    row.category, a if pd.notna(a) else None
                ):
                    b, bo = np.nan, "layout_conflict"
                else:
                    b, bo = count, from_where
        furn = row.furniture_analysis
        recovered = extract_furniture_full(str(row.title) + " " + body)
        projected, title_status = project_claim(row.title)
        project, ps = projected, title_status
        if isinstance(row.source_project_name, str) and row.source_project_name.strip():
            mapped, _ = project_claim(row.source_project_name)
            structured = (
                mapped
                if mapped != "Unknown"
                else "nhatot:name:" + plain(row.source_project_name)
            )
            if projected != "Unknown" and projected != structured:
                project, ps = "Unknown", "source_title_conflict"
            else:
                project, ps = structured, "structured"
        elif (
            pd.notna(row.source_project_id)
            and projected == "Unknown"
            and ps == "unmatched"
        ):
            project, ps = "nhatot:id:" + str(row.source_project_id), "structured_id"
        ward = strip_admin_prefix(row.ward)
        ward_key = (
            schemes[row.source] + ":" + plain(row.district_analysis) + ":" + plain(ward)
            if pd.notna(ward) and pd.notna(row.district_analysis)
            else "Unknown"
        )
        features.append(
            dict(
                recovered_area=a,
                area_origin=origin,
                area_status=status,
                area_evidence=evidence,
                recovered_bedrooms=b,
                recovered_bedrooms_origin=bo,
                bedroom_evidence=row.title
                if bo == "title_explicit"
                else body
                if bo == "description_explicit"
                else "",
                area_original_missing=str(pd.isna(row.area_m2)),
                bedrooms_original_missing=str(pd.isna(row.bedrooms)),
                recovered_furnishing="Furnished"
                if furn == "Unknown" and pd.notna(recovered)
                else furn,
                ward_key=ward_key,
                ward_status="source_scoped" if ward_key != "Unknown" else "unknown",
                project_id=project,
                project_match_status=ps,
            )
        )
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(features)], axis=1)
