"""Reporting on frozen development rows and posting-date sensitivity windows."""

from pathlib import Path

import pandas as pd

from .improvement import PARAMS
from .training import FEATURE_SETS, RentalPriceEstimator


def summarize_improvements(root):
    folder = Path(root) / "reports/improvement"
    data = pd.read_csv(folder / "enriched_development.csv.gz")
    saved = pd.read_csv(folder / "predictions.csv.gz")
    predictions = saved.loc[
        saved["mode"].eq("all")
        & saved.variant.isin(["E0_reviewed", "E5", "E6_pooled_log", "E9_bathrooms"])
    ].copy()
    predictions = predictions.merge(
        data[["listing_id", "district_analysis", "area_band"]],
        on="listing_id",
        validate="many_to_one",
    )
    predictions["error"] = predictions.predicted - predictions.actual
    predictions["absolute_error"] = predictions.error.abs()
    local = (
        predictions.groupby(["category", "district_analysis", "area_band", "variant"])
        .agg(
            n=("actual", "size"),
            mae_vnd=("absolute_error", "mean"),
            bias_vnd=("error", "mean"),
        )
        .reset_index()
    )
    local.loc[local.n < 10, ["mae_vnd", "bias_vnd"]] = float("nan")
    local.to_csv(folder / "within_area.csv", index=False)
    rows = []
    for low, high in [
        ("2026-10-01", "2026-10-10"),
        ("2026-10-11", "2026-10-20"),
        ("2026-10-21", "2026-10-30"),
    ]:
        earlier = data.loc[data.posted_date.lt(low)]
        valid = data.loc[data.posted_date.between(low, high)]
        train = earlier.loc[~earlier.split_group.isin(valid.split_group)]
        model = RentalPriceEstimator(
            family="monotone_single",
            features=tuple(FEATURE_SETS["C"]),
            target="log",
            params=PARAMS,
        ).fit(train, train.price_month_vnd)
        for name, g in [("all", valid), *valid.groupby("category")]:
            error = (model.predict(g) - g.price_month_vnd).abs()
            rows.append(
                dict(
                    cutoff=low,
                    validation_end=high,
                    category=name,
                    training_n=len(train),
                    training_collected_on_or_after_cutoff=int(
                        train.scraped_at.ge(low).sum()
                    ),
                    validation_n=len(g),
                    mae_vnd=error.mean() if len(g) >= 10 else None,
                    group_overlap=0,
                    evaluation_kind="retrospective_posting_window",
                )
            )
    pd.DataFrame(rows).to_csv(folder / "october_posting_windows.csv", index=False)
