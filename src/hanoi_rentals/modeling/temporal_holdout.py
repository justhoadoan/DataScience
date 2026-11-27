"""Summarize November chronological validation from the saved development predictions."""

from math import isfinite
from pathlib import Path

import pandas as pd

from hanoi_rentals.features.dates import TARGET_END, today_hanoi
from hanoi_rentals.ingestion.temporal_policy import ensure_protocol
from hanoi_rentals.modeling.training import metrics
from hanoi_rentals.operations.registry import read_json, write_json


def scores(actual, predicted):
    result = {"n": len(actual)}
    if len(actual) >= 10:
        result.update(
            {
                key: value if isfinite(value) else None
                for key, value in metrics(actual, predicted).items()
            }
        )
    return result


def evaluate_november(root):
    root = Path(root).resolve()
    protocol = ensure_protocol(root)
    folder = root / "reports/temporal"
    evaluation = read_json(folder / "evaluation.json", {})
    if evaluation.get("status") != "preview_ready" or evaluation.get(
        "target_until"
    ) != str(TARGET_END):
        return {
            "status": "training_required",
            "reason": "Run train-temporal for the November collection window first.",
        }
    predictions = pd.read_csv(folder / "predictions.csv")
    dates = predictions.valuation_date.astype(str)
    selected = predictions.loc[
        dates.between("2026-11-01", str(TARGET_END)) & dates.le(str(today_hanoi()))
    ].copy()
    if selected.empty:
        return {
            "status": "insufficient_coverage",
            "reason": "No November chronological validation predictions.",
        }
    fold_info = {item["fold"]: item for item in evaluation["folds"]}
    assignments = pd.read_csv(folder / "fold_assignments.csv")
    for fold in selected.fold.unique():
        info = fold_info[fold]
        if info["training_end"] >= info["validation_date"]:
            raise ValueError(
                "November validation requires strictly earlier training dates."
            )
        split = assignments.loc[assignments.fold.eq(fold)]
        train = split.loc[split.role.eq("training")]
        valid = split.loc[split.role.eq("validation")]
        if set(train.split_group) & set(valid.split_group):
            raise ValueError("Property overlap in November chronological evaluation.")
        expected = set(valid.observation_id)
        for _, variant in selected.loc[selected.fold.eq(fold)].groupby("variant"):
            if (
                not set(variant.observation_id).issubset(expected)
                or variant.observation_id.duplicated().any()
            ):
                raise ValueError(
                    "November predictions differ from the saved validation assignments."
                )
    comparisons = {}
    for name, rows in selected.groupby("variant"):
        comparisons[name] = {
            "overall": scores(rows.price_month_vnd, rows.prediction_vnd),
            "categories": {
                category: scores(group.price_month_vnd, group.prediction_vnd)
                for category, group in rows.groupby("category")
            },
        }
    result = {
        "status": "evaluated",
        "evaluation_kind": protocol["evaluation_kind"],
        "candidate": evaluation["candidate"],
        "selected_variant": evaluation["selected_variant"],
        "target_since": "2026-11-01",
        "target_until": str(TARGET_END),
        "as_of": str(today_hanoi()),
        "month_complete": today_hanoi() > TARGET_END,
        "validation_start": selected.valuation_date.min(),
        "validation_end": selected.valuation_date.max(),
        "comparisons": comparisons,
        "group_overlap": 0,
        "promoted": False,
        "note": "November labels have already been used in development. Scores use the earlier-to-later, property-purged development folds.",
    }
    write_json(folder / "november_evaluation.json", result)
    return result


def evaluate_holdout(root):
    """Keep the former CLI entry point compatible with the November assessment."""
    return evaluate_november(root)
