"""Paired development experiments against the original October assignments."""

import io
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from hanoi_rentals.features.enrichment import enrich, match_versions
from hanoi_rentals.features.title_attributes import (
    area_claim,
    bedroom_claim,
    project_claim,
)
from hanoi_rentals.modeling.behavior import behavior_probe
from hanoi_rentals.modeling.training import FEATURE_SETS, RentalPriceEstimator
from hanoi_rentals.operations.registry import read_json, write_json
from hanoi_rentals.serving.api import PredictionRequest

REVISION = "f7641c1"
PARAMS = {"max_leaf_nodes": 15, "min_samples_leaf": 20}
ORIGINS = [
    "area_origin",
    "recovered_bedrooms_origin",
    "area_original_missing",
    "bedrooms_original_missing",
]


def original_csv(root, name):
    content = subprocess.check_output(["git", "show", REVISION + ":" + name], cwd=root)
    return pd.read_csv(io.BytesIO(content))


def annotation_scores(folder):
    annotations = pd.read_csv(folder / "annotations.csv")
    checks = {
        "area_label": lambda s: area_claim(s)[0],
        "bedrooms_label": lambda s: bedroom_claim(s)[0],
        "project_label": lambda s: project_claim(s)[0],
    }
    rows = []
    for label, extract in checks.items():
        pred = annotations.title.map(extract).replace("Unknown", np.nan)
        annotations[label + "_prediction"] = pred
        for subset, idx in annotations.groupby("subset").groups.items():
            reference = annotations.loc[idx, label]
            predicted = pred.loc[idx]
            tp = int((reference.notna() & reference.eq(predicted)).sum())
            n = int(predicted.notna().sum())
            rows.append(
                dict(
                    field=label,
                    subset=subset,
                    n=len(idx),
                    accepted=n,
                    relevant=int(reference.notna().sum()),
                    correct=tp,
                    disagreements=int(
                        (
                            ~reference.eq(predicted)
                            & (reference.notna() | predicted.notna())
                        ).sum()
                    ),
                    precision=tp / n if n else None,
                    recall=tp / max(1, reference.notna().sum()),
                )
            )
    annotations.to_csv(folder / "annotations_scored.csv", index=False)
    return rows


def freeze_requests(frame, districts):
    payloads = []
    for row in frame.itertuples():
        if (
            row.district_analysis not in districts
            or not 5 < row.area_analysis_m2 <= 500
        ):
            continue
        payload = PredictionRequest(
            category=row.category,
            district=row.district_analysis,
            area_m2=row.area_analysis_m2,
            bedrooms=int(row.bedrooms_analysis)
            if pd.notna(row.bedrooms_analysis)
            else None,
            furnishing=row.furniture_analysis,
        )
        payloads.append(dict(listing_id=row.listing_id, **payload.model_dump()))
    return pd.DataFrame(payloads)


def error_summary(group):
    errors = group.predicted - group.actual
    result = {"n": len(errors)}
    if len(errors) >= 10:
        result.update(
            mae_vnd=float(errors.abs().mean()),
            rmse_vnd=float(np.sqrt((errors**2).mean())),
        )
    return result


def run(root):
    root = Path(root).resolve()
    folder = root / "reports/improvement"
    folder.mkdir(parents=True, exist_ok=True)
    split = original_csv(root, "data/analysis/modeling_splits.csv")
    old = original_csv(root, "data/analysis/listings_analysis.csv").merge(
        split.loc[split.partition.eq("development"), ["listing_id", "cv_fold"]],
        on="listing_id",
        validate="one_to_one",
    )
    reviews = read_json(root / "artifacts/models/ec9a7bf02b42ae3b/metadata.json")
    decisions = pd.read_csv(folder / "label_reviews.csv").set_index("listing_id")
    rejected = decisions.index[
        decisions[["price_decision", "scope_decision"]]
        .isin(["unresolved", "exclude"])
        .any(axis=1)
    ]
    retained = old.loc[~old.listing_id.isin(rejected)].copy()
    requests = freeze_requests(retained, set(reviews["supported_districts"]))
    requests.to_csv(folder / "fixed_requests.csv", index=False)
    app = pd.DataFrame(
        [
            PredictionRequest(
                **{
                    k: v
                    for k, v in row.items()
                    if k != "listing_id" and pd.notna(v) and k != "bedrooms"
                },
                bedrooms=int(row["bedrooms"]) if pd.notna(row["bedrooms"]) else None,
            ).estimator_inputs()
            for row in requests.to_dict("records")
        ],
        index=requests.listing_id,
    )
    retained[["listing_id", "cv_fold", "split_group", "price_month_vnd"]].to_csv(
        folder / "reviewed_folds.csv", index=False
    )
    pre = original_csv(root, "reports/modeling_predictions.csv")
    pre = pre.loc[pre.partition.eq("development_oof") & pre.model.eq("ablation_C")]
    fixed = {
        "original": float(pre.absolute_error_vnd.mean()),
        "retained": float(
            pre.loc[
                pre.listing_id.isin(retained.listing_id), "absolute_error_vnd"
            ].mean()
        ),
        "original_n": len(pre),
        "retained_n": len(retained),
    }
    reviewed = enrich(match_versions(root, retained))
    reviewed.to_csv(folder / "enriched_development.csv.gz", index=False)
    coverage = reviewed.groupby(["source", "category"]).agg(
        n=("listing_id", "size"),
        raw_area=("area_m2", "count"),
        old_area=("area_analysis_m2", "count"),
        recovered_area=("recovered_area", "count"),
        raw_bedrooms=("bedrooms", "count"),
        old_bedrooms=("bedrooms_analysis", "count"),
        recovered_bedrooms=("recovered_bedrooms", "count"),
        ward=("ward", "count"),
        posting_date=("posted_date", "count"),
        project=("project_id", lambda x: x.ne("Unknown").sum()),
        furnished_before=("furniture_analysis", lambda x: x.ne("Unknown").sum()),
        furnished_after=("recovered_furnishing", lambda x: x.ne("Unknown").sum()),
    )
    coverage.to_csv(folder / "feature_coverage.csv")
    for name in [
        "area_status",
        "area_origin",
        "recovered_bedrooms_origin",
        "raw_match_status",
        "project_match_status",
        "ward_status",
    ]:
        reviewed.groupby(["source", "category", name]).size().rename("n").to_csv(
            folder / (name + ".csv")
        )
    reviewed.groupby(
        ["source", "district_analysis", "ward", "ward_key", "ward_status"], dropna=False
    ).size().rename("n").to_csv(folder / "ward_inventory.csv")
    annotations = annotation_scores(folder)
    prepared = reviewed.assign(
        area_analysis_m2=reviewed.recovered_area,
        bedrooms_analysis=reviewed.recovered_bedrooms,
        bathroom_count=reviewed.toilets_analysis.map(
            lambda n: str(int(n)) if pd.notna(n) else "Unknown"
        ),
    )
    cols = FEATURE_SETS["C"]
    results = []
    details = []
    subgroups = []
    configs = {}

    def evaluate(
        name,
        train_data,
        features,
        *,
        family="monotone",
        adaptive=True,
        target="log",
        native=False,
    ):
        start = time.monotonic()
        records = []
        violations = 0
        for fold in sorted(retained.cv_fold.unique()):
            train = train_data[train_data.cv_fold != fold]
            valid = train_data[
                (train_data.cv_fold == fold)
                & train_data.listing_id.isin(retained.listing_id)
            ].copy()
            assert set(train.split_group).isdisjoint(valid.split_group)
            model = RentalPriceEstimator(
                family=family,
                features=tuple(features),
                target=target,
                params=PARAMS,
                adaptive_bedrooms=adaptive,
                native_missing=native,
            ).fit(train, train.price_month_vnd)
            # Monotonicity is imposed on every fit. Check the public input grid on each fold.
            violations += behavior_probe(model)["violations"]
            base = valid.set_index("listing_id")
            api = app.loc[app.index.intersection(base.index)]
            for mode, x in (("all", base), ("api", api)):
                context = base.loc[x.index]
                p = pd.DataFrame(
                    dict(
                        listing_id=x.index,
                        fold=fold,
                        category=context.category.to_numpy(),
                        actual=context.price_month_vnd.to_numpy(),
                        predicted=model.predict(x),
                        mode=mode,
                        variant=name,
                    )
                )
                records.append(p)
                if mode == "all":
                    strata = {
                        "missing_area": context.area_analysis_m2.isna(),
                        "missing_bedrooms": context.bedrooms_analysis.isna(),
                        "rare_district": context.district_analysis.map(
                            train.district_analysis.value_counts()
                        )
                        .fillna(0)
                        .lt(20),
                        "unseen_district": ~context.district_analysis.isin(
                            train.district_analysis
                        ),
                    }
                    for col in ("ward_key", "project_id"):
                        if col in context:
                            strata["unseen_" + col] = context[col].ne(
                                "Unknown"
                            ) & ~context[col].isin(train[col])
                    if "area_origin" in context:
                        for value in ["title", "description", "structured", "unknown"]:
                            strata["area_" + value] = context.area_origin.eq(value)
                    for group, mask in strata.items():
                        subgroups.append(
                            dict(
                                variant=name,
                                fold=fold,
                                group=group,
                                **error_summary(p.loc[mask.to_numpy()]),
                            )
                        )
        predictions = pd.concat(records, ignore_index=True)
        details.append(predictions)
        scores = {}
        for mode, g in predictions.groupby("mode"):
            overall = error_summary(g)
            by_cat = {c: error_summary(v)["mae_vnd"] for c, v in g.groupby("category")}
            scores[mode] = {"mae": overall["mae_vnd"], **by_cat}
            for c, v in [("all", g), *g.groupby("category")]:
                fold_mae = (
                    v.assign(ae=(v.actual - v.predicted).abs())
                    .groupby("fold")
                    .ae.mean()
                )
                results.append(
                    dict(
                        variant=name,
                        population=mode,
                        category=c,
                        **error_summary(v),
                        fold_std_vnd=float(fold_mae.std()),
                        runtime_s=time.monotonic() - start,
                        behavior_violations=violations,
                    )
                )
        configs[name] = dict(
            features=list(features),
            family=family,
            adaptive_bedrooms=adaptive,
            target=target,
            native_missing=native,
            scores=scores,
            behavior_violations=violations,
        )
        print(
            name, round(scores["all"]["mae"]), round(scores["api"]["mae"]), flush=True
        )

    def better(candidate, reference):
        x, y = configs[candidate], configs[reference]
        if x["behavior_violations"]:
            return False
        for mode in ["all", "api"]:
            a, b = x["scores"][mode], y["scores"][mode]
            if (
                any(a[c] > 1.05 * b[c] for c in ("can_ho_chung_cu", "nha_tro"))
                or a["mae"] > 1.01 * b["mae"]
            ):
                return False
        a, b = x["scores"]["all"], y["scores"]["all"]
        return (
            a["mae"] <= 0.99 * b["mae"]
            or a["mae"] <= b["mae"]
            and any(a[c] <= 0.99 * b[c] for c in ("can_ho_chung_cu", "nha_tro"))
        )

    evaluate("E0_original", old, cols)
    evaluate("E0_reviewed", reviewed, cols)
    evaluate("E1", prepared, cols)
    evaluate("E2", prepared, cols + ORIGINS)
    for name, extra in [
        ("E3", ["ward_key"]),
        ("E4", ["project_id"]),
        ("E5", ["ward_key", "project_id"]),
    ]:
        evaluate(name, prepared, cols + ORIGINS + extra)
    # Isolated property experiments. A feature requiring an unvalidated description
    # fallback must also clear an independent description review before export.
    leader = "E0_reviewed"
    for name in ["E1", "E2", "E3", "E4", "E5"]:
        if better(name, leader):
            leader = name
    base = reviewed if leader == "E0_reviewed" else prepared
    features = configs[leader]["features"]
    for target in ["log", "direct"]:
        for shape, family in [("pooled", "monotone_single"), ("split", "monotone")]:
            evaluate(
                "E6_A_" + shape + "_" + target,
                base,
                FEATURE_SETS["A"],
                family=family,
                adaptive=False,
                target=target,
            )
    for target in ["log", "direct"]:
        for shape, family in [("pooled", "monotone_single"), ("split", "monotone")]:
            evaluate(
                "E6_" + shape + "_" + target,
                base,
                features,
                family=family,
                adaptive=False,
                target=target,
            )
    pool = min(
        ("E6_pooled_log", "E6_pooled_direct"),
        key=lambda n: configs[n]["scores"]["all"]["mae"],
    )
    split = min(
        ("E6_split_log", "E6_split_direct"),
        key=lambda n: configs[n]["scores"]["all"]["mae"],
    )
    a, b = configs[pool]["scores"]["all"], configs[split]["scores"]["all"]
    architecture = (
        pool
        if a["mae"] <= 1.01 * b["mae"]
        and all(a[c] <= 1.05 * b[c] for c in ("can_ho_chung_cu", "nha_tro"))
        else split
    )
    selected = configs[architecture]
    kwargs = dict(family=selected["family"], adaptive=False, target=selected["target"])
    evaluate("E7_native", base, features, native=True, **kwargs)
    native = better("E7_native", architecture)
    quality = base.assign(bathroom_count=prepared.bathroom_count.to_numpy())
    evaluate(
        "E9_bathrooms", quality, features + ["bathroom_count"], native=native, **kwargs
    )
    evaluate(
        "E9_furnishing",
        base.assign(furniture_analysis=reviewed.recovered_furnishing.to_numpy()),
        features,
        native=native,
        **kwargs,
    )
    pd.DataFrame(results).to_csv(folder / "ablation.csv", index=False)
    pd.concat(details).to_csv(folder / "predictions.csv.gz", index=False)
    pd.DataFrame(subgroups).to_csv(folder / "subgroups.csv", index=False)
    write_json(
        folder / "decision.json",
        dict(
            revision=REVISION,
            original_fixed_predictions=fixed,
            excluded_ids=list(rejected),
            annotations=annotations,
            leading_feature_variant=leader,
            matched_architecture=architecture,
            native_missing_selected=native,
            variants=configs,
        ),
    )
    from .diagnostics import summarize_improvements

    summarize_improvements(root)
