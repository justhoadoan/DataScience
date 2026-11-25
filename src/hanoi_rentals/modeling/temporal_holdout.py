"""Score the pre-December candidate once, only after the reserved month ends."""

from hashlib import sha256
from math import isfinite
from pathlib import Path

import joblib
import pandas as pd

from hanoi_rentals.analysis.audit import prepare_analysis
from hanoi_rentals.features.dates import HOLDOUT_START, TARGET_END, today_hanoi
from hanoi_rentals.ingestion.observations import load_observations
from hanoi_rentals.ingestion.temporal_policy import ensure_protocol
from hanoi_rentals.modeling.training import metrics
from hanoi_rentals.operations.registry import read_json, write_json


def scores(actual, predicted):
    return {
        key: value if isfinite(value) else None
        for key, value in metrics(actual, predicted).items()
    }


def holdout_population(root):
    history = load_observations(root)
    if history.empty:
        return history
    verified = history.loc[
        history.date_origin.isin(
            ["live_collection", "verified_manifest_day", "verified_archive_capture"]
        )
    ].copy()
    verified["property_id"] = verified.listing_id
    verified["listing_id"] = "obs_" + verified.observation_id
    previous = verified.loc[verified.price_observed_date.lt(str(HOLDOUT_START))].copy()
    future = verified.loc[
        verified.price_observed_date.between(str(HOLDOUT_START), str(TARGET_END))
        & verified.posted_date.astype(str).between(str(HOLDOUT_START), str(TARGET_END))
    ].copy()
    if future.empty:
        return future
    # Keep one first observation per property; repeated daily quotes are not independent cases.
    future = future.sort_values(
        ["price_observed_date", "observation_id"]
    ).drop_duplicates("property_id")
    legacy = pd.read_csv(Path(root) / "data/processed/listings.csv")
    legacy = legacy.loc[
        legacy.scraped_at.astype(str).lt(str(HOLDOUT_START))
        & legacy.posted_date.astype(str).lt(str(HOLDOUT_START))
    ]
    old_ids = set(legacy.listing_id) | set(previous.listing_id)
    audited = prepare_analysis(pd.concat([legacy, previous, future], ignore_index=True))
    old_groups = set(audited.loc[audited.listing_id.isin(old_ids), "split_group"])
    selected = (
        audited.loc[
            audited.listing_id.isin(future.listing_id)
            & audited.include_price
            & ~audited.split_group.isin(old_groups)
        ]
        .drop_duplicates("split_group")
        .copy()
    )
    selected["valuation_date"] = selected.price_observed_date
    assert set(selected.split_group).isdisjoint(old_groups)
    return selected


def evaluate_holdout(root):
    root = Path(root).resolve()
    protocol = ensure_protocol(root)
    result_path = root / "data/benchmark/temporal_holdout_evaluation.json"
    if result_path.exists():
        return read_json(result_path)
    if today_hanoi() <= TARGET_END:
        return {
            "status": "pending",
            "reason": "December 2026 has not ended; no holdout rows or labels were loaded.",
        }
    if not protocol["reserved_before_collection_window"] or not protocol.get(
        "frozen_candidate"
    ):
        return {
            "status": "blocked",
            "reason": "No untouched reservation with a candidate frozen before December.",
        }
    if protocol["candidate_frozen_at"][:10] >= str(HOLDOUT_START):
        raise ValueError("Candidate was not frozen before the reserved window.")
    folder = root / "artifacts/temporal" / protocol["frozen_candidate"]
    model_path = folder / "model.joblib"
    if sha256(model_path.read_bytes()).hexdigest() != protocol["candidate_sha256"]:
        raise ValueError("Frozen candidate checksum mismatch.")
    data = holdout_population(root)
    if data.empty:
        return {
            "status": "pending",
            "reason": "No eligible, previously unseen properties in the reserved window.",
        }
    if len(data) < 100 or any(
        data.category.eq(c).sum() < 30 for c in ["can_ho_chung_cu", "nha_tro"]
    ):
        return {
            "status": "insufficient_coverage",
            "eligible_n": len(data),
            "reason": "Require at least 100 properties and 30 per category before scoring the frozen assessment.",
        }
    model = joblib.load(model_path)
    metadata = read_json(folder / "metadata.json")
    predicted = model.predict(data)
    baseline = data.category.map(metadata["training_category_medians"]).to_numpy()
    result = {
        "status": "scored_once",
        "candidate": protocol["frozen_candidate"],
        "model_sha256": protocol["candidate_sha256"],
        "evaluated_on": str(today_hanoi()),
        "overall": scores(data.price_month_vnd, predicted),
        "category_baseline": scores(data.price_month_vnd, baseline),
        "categories": {
            c: scores(data.loc[mask, "price_month_vnd"], predicted[mask.to_numpy()])
            for c in sorted(data.category.unique())
            for mask in [data.category.eq(c)]
        },
        "observation_ids": data.observation_id.tolist(),
        "group_overlap": 0,
        "promoted": False,
        "note": "Independent future assessment. Sparse coverage and production promotion require separate review; this command does not select or retrain models.",
    }
    write_json(result_path, result)
    return result
