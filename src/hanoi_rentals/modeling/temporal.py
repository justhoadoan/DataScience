"""Evidence-dated experiments with purged chronological validation and a preview bundle.

The old benchmark remains quarantined. December is reserved before collection;
neither its labels nor its features are loaded by this training path.
"""

import json
import shutil
from datetime import datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import joblib
import pandas as pd

from hanoi_rentals.analysis.audit import CATEGORIES, prepare_analysis, read_reviews
from hanoi_rentals.features.bedrooms import LAYOUT_POLICY
from hanoi_rentals.features.enrichment import match_versions
from hanoi_rentals.features.dates import (
    EPOCH,
    HOLDOUT_START,
    TARGET_END,
    ZONE,
    today_hanoi,
)
from hanoi_rentals.ingestion.observations import coverage_report, load_observations
from hanoi_rentals.ingestion.temporal_policy import ensure_protocol, reserved_rows
from hanoi_rentals.modeling.behavior import CONTRACT_VERSION, behavior_probe
from hanoi_rentals.modeling.training import (
    DEPS,
    FEATURE_SETS,
    RentalPriceEstimator,
    metrics,
)
from hanoi_rentals.operations.registry import market_profile, write_json
from hanoi_rentals.paths import source_files


def dated_population(root):
    root = Path(root)
    observations = load_observations(root, before=HOLDOUT_START)
    if observations.empty:
        return observations, {"reason": "No evidenced pre-December observations"}
    observations = observations.loc[
        observations.date_origin.isin(
            ["live_collection", "verified_manifest_day", "verified_archive_capture"]
        )
        & observations.price_observed_date.between(
            str(EPOCH), str(min(today_hanoi(), TARGET_END))
        )
        & (
            observations.posted_date.astype(str).between(
                str(EPOCH), str(HOLDOUT_START), inclusive="left"
            )
            | (
                observations.date_origin.eq("verified_archive_capture")
                & observations.posted_date.isna()
            )
        )
    ].copy()
    if observations.empty:
        return observations, {"reason": "No observations with verified price dates"}
    # Identical records repeated in pagination must not gain extra training weight.
    observations = observations.sort_values("observation_id").drop_duplicates(
        [
            "listing_id",
            "price_observed_date",
            "price_vnd",
            "price_raw",
            "title",
            "area_m2",
            "bedrooms",
            "furniture",
        ]
    )
    observations["property_id"] = observations.listing_id
    observations["listing_id"] = "obs_" + observations.observation_id
    legacy = pd.read_csv(root / "data/processed/listings.csv")
    legacy = legacy.loc[~reserved_rows(legacy)].copy()
    # Anchors preserve old review context and identify benchmark/duplicate peers.
    combined = pd.concat([legacy, observations], ignore_index=True)
    reviews = read_reviews(root / "data/analysis/review_queue.csv", combined)
    # Carry a reviewed label to the same property version only.
    context = [
        "listing_id",
        "category",
        "title",
        "price_vnd",
        "price_raw",
        "area_raw",
        "posted_date",
    ]
    versions = (
        legacy[context]
        .merge(reviews, on="listing_id")
        .rename(columns={"listing_id": "property_id"})
    )
    obs_context = observations[["listing_id", "property_id", *context[1:]]].copy()
    for frame in (versions, obs_context):
        frame["area_raw"] = pd.to_numeric(frame.area_raw, errors="coerce")
    matched = obs_context.merge(
        versions, on=["property_id", *context[1:]], validate="many_to_one"
    )
    reviews = pd.concat([reviews, matched[reviews.columns]], ignore_index=True)
    analysis = prepare_analysis(combined, reviews)
    benchmark = root / "data/benchmark/ids.csv"
    if not benchmark.exists():
        raise ValueError(
            "Frozen benchmark IDs are required to quarantine their observations."
        )
    ids = set(pd.read_csv(benchmark).listing_id)
    if not ids.issubset(set(legacy.listing_id)):
        raise ValueError("Frozen benchmark anchors are missing.")
    benchmark_groups = set(analysis.loc[analysis.listing_id.isin(ids), "split_group"])
    dated = analysis.loc[analysis.listing_id.str.startswith("obs_")].copy()
    eligible = dated.include_price & ~dated.split_group.isin(benchmark_groups)
    data = dated.loc[eligible].copy()
    # Earlier snapshot dates can rule out a new property, but do not date its price.
    known_dates = analysis.price_observed_date.fillna(analysis.scraped_at).astype(str)
    first_seen = known_dates.groupby(analysis.split_group).min()
    data["first_known_date"] = data.split_group.map(first_seen)
    data["valuation_date"] = data.price_observed_date
    assert not set(data.split_group) & benchmark_groups
    return data.reset_index(drop=True), {
        "dated_observations_before_audit": len(dated),
        "excluded_by_price_audit": int((~dated.include_price).sum()),
        "benchmark_peer_observations_quarantined": int(
            dated.split_group.isin(benchmark_groups).sum()
        ),
        "eligible_observations": len(data),
        "price_date_origins": data.date_origin.value_counts().to_dict(),
        "legacy_parser_dates_used": False,
    }


def chronological_folds(data):
    """Compare earlier observations to each supported later month (day for short histories)."""
    periods = data.valuation_date.str[:7]
    windows = periods if periods.nunique() >= 3 else data.valuation_date
    for cutoff in sorted(windows.unique())[1:]:
        valid = (
            data.loc[windows.eq(cutoff)]
            .sort_values(["valuation_date", "observation_id"])
            .drop_duplicates("split_group")
        )
        earlier = data.loc[windows.lt(cutoff)]
        train = earlier.loc[~earlier.split_group.isin(valid.split_group)]
        if any(
            (train.category.eq(c).sum() < 20 or valid.category.eq(c).sum() < 5)
            for c in CATEGORIES
        ):
            continue
        assert train.valuation_date.max() < valid.valuation_date.min()
        assert set(train.split_group).isdisjoint(valid.split_group)
        yield train, valid, len(earlier) - len(train)


def estimator(kind):
    features = FEATURE_SETS["C"] + ([] if kind == "no_date" else ["valuation_date"])
    return RentalPriceEstimator(
        family="monotone_single",
        target="log",
        features=tuple(features),
        params={"max_leaf_nodes": 15, "min_samples_leaf": 20},
        date_seasonal=kind == "calendar",
    )


def train_temporal(root):
    root = Path(root).resolve()
    report = root / "reports/temporal"
    report.mkdir(parents=True, exist_ok=True)
    coverage_report(root)
    protocol = ensure_protocol(root)
    data, audit = dated_population(root)
    base = {
        "created_at": datetime.now(ZONE).isoformat(),
        "audit": audit,
        "target_since": str(EPOCH),
        "target_until": str(TARGET_END),
        "reserved_holdout": [str(HOLDOUT_START), str(TARGET_END)],
        "holdout_status": protocol["status"],
        "promoted": False,
        "evaluation_kind": "retrospective_chronological_development",
        "selection_rule": "Dated variants only; prefer elapsed days within 1% of the best MAE. No-date is diagnostic.",
    }
    folds = list(chronological_folds(data)) if not data.empty else []
    if not folds:
        result = {
            **base,
            "status": "awaiting_dated_observations",
            "reason": "Need at least two verified observation days with 20 training and 5 validation rows per category after purging duplicate groups.",
        }
        write_json(report / "evaluation.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return result
    records, assignments, fold_summary = [], [], []
    for fold, (train, valid, purged) in enumerate(folds):
        fold_summary.append(
            {
                "fold": fold,
                "training_end": train.valuation_date.max(),
                "validation_date": valid.valuation_date.min(),
                "validation_end": valid.valuation_date.max(),
                "training_n": len(train),
                "validation_n": len(valid),
                "purged_training_rows": purged,
                "group_overlap": 0,
            }
        )
        for role, frame in [("training", train), ("validation", valid)]:
            assignment = frame[
                ["observation_id", "property_id", "split_group", "valuation_date"]
            ].copy()
            assignment["fold"], assignment["role"] = fold, role
            assignments.append(assignment)
        for kind in ["no_date", "elapsed", "calendar"]:
            model = estimator(kind).fit(train, train.price_month_vnd)
            pred = valid[
                [
                    "observation_id",
                    "property_id",
                    "category",
                    "valuation_date",
                    "first_known_date",
                    "split_group",
                    "price_month_vnd",
                ]
            ].copy()
            pred["prediction_vnd"] = model.predict(valid)
            pred["variant"], pred["fold"] = kind, fold
            records.append(pred)
            print(
                f"Temporal fold {fold} / {kind}: MAE={metrics(pred.price_month_vnd, pred.prediction_vnd)['mae_vnd']:,.0f} VND",
                flush=True,
            )
    predictions = pd.concat(records, ignore_index=True)
    comparisons = {
        name: {
            "overall": metrics(group.price_month_vnd, group.prediction_vnd),
            "categories": {
                category: metrics(g.price_month_vnd, g.prediction_vnd)
                for category, g in group.groupby("category")
            },
        }
        for name, group in predictions.groupby("variant")
    }
    selected = (
        "elapsed"
        if comparisons["elapsed"]["overall"]["mae_vnd"]
        <= 1.01 * comparisons["calendar"]["overall"]["mae_vnd"]
        else "calendar"
    )
    model = estimator(selected).fit(data, data.price_month_vnd)
    behavior = behavior_probe(model)
    if behavior["violations"]:
        raise ValueError("Dated candidate failed the area/bedroom behavior contract.")
    population_bytes = data.sort_values("observation_id").to_csv(index=False).encode()
    code = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in source_files().items()
    }
    digest = sha256(
        population_bytes + json.dumps(code, sort_keys=True).encode()
    ).hexdigest()
    version_id = digest[:16]
    # Explicitly isolated preview: this never writes the production champion registry.
    preview = root / ".work/temporal-preview"
    destination = root / "artifacts/temporal" / version_id
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "model.joblib"
    joblib.dump(model, model_path, compress=3)
    profile = market_profile(data)
    score = comparisons[selected]
    metadata = {
        "version": version_id,
        "run_fingerprint": digest,
        "preview_only": True,
        "model_sha256": sha256(model_path.read_bytes()).hexdigest(),
        "input": {"versions": {name: version(name) for name in DEPS}, "code": code},
        "prediction_contract_version": CONTRACT_VERSION,
        "layout_policy": LAYOUT_POLICY,
        "supported_districts": sorted(model.districts_),
        "feature_schema": list(model.features),
        "category_feature_schema": {
            c: model.features_for_category(c) for c in CATEGORIES
        },
        "selected_model": "temporal_" + selected,
        "evaluated_at": base["created_at"],
        "date_range": list(model.date_range_),
        "date_epoch": str(EPOCH),
        "timezone": str(ZONE),
        "date_origin_rules": [
            "live_collection",
            "verified_manifest_day",
            "verified_archive_capture",
        ],
        "property_feature_contract": "Shared pooled log-target monotone histogram, feature set C; missing numerics use training medians and indicators. Reviewed E6 architecture.",
        "location_fallback": "District. Ward and project were assessed only in development.",
        "config_sha256": {
            name: digest
            for name, digest in code.items()
            if name == "features/reference.py"
        },
        "date_features": ["elapsed_days"]
        + (["month_sin", "month_cos"] if selected == "calendar" else []),
        "benchmark": score["overall"],
        "category_metrics": score["categories"],
        "evaluation_kind": base["evaluation_kind"],
        "development_n": len(data),
        "internal_test_n": score["overall"]["n"],
        "behavior": behavior,
        "dataset": {k: v for k, v in profile.items() if k != "districts"},
        "training_category_medians": data.groupby("category")
        .price_month_vnd.median()
        .to_dict(),
    }
    # Lock feature and date choices before retrieving any benchmark targets.
    benchmark_file = destination / "operational_benchmark.json"
    if not benchmark_file.exists():
        frozen = pd.read_csv(root / "data/benchmark/ids.csv")
        legacy = pd.read_csv(root / "data/processed/listings.csv")
        eligible = prepare_analysis(
            legacy[legacy.listing_id.isin(frozen.listing_id)].copy()
        )
        benchmark = match_versions(root, eligible)
        benchmark = benchmark.loc[
            benchmark.include_price & benchmark.raw_match_status.eq("exact_version")
        ].copy()
        benchmark["valuation_date"] = benchmark.scraped_at
        assessment = {
            "frozen_ids": len(frozen),
            "matched_ids": len(benchmark),
            "missing_evidenced_date": len(frozen) - len(benchmark),
            "selected_before_scoring": True,
            "kind": "reused_operational_benchmark_exact_versions",
            "promoted": False,
            "listing_ids": benchmark.listing_id.tolist(),
        }
        if len(benchmark):
            benchmark["prediction_vnd"] = model.predict(benchmark)
            for name, g in [("all", benchmark), *benchmark.groupby("category")]:
                assessment[name] = (
                    {
                        "n": len(g),
                        "mae_vnd": float(
                            (g.price_month_vnd - g.prediction_vnd).abs().mean()
                        ),
                    }
                    if len(g) >= 10
                    else {"n": len(g)}
                )
        write_json(benchmark_file, assessment)
    write_json(destination / "metadata.json", metadata)
    write_json(destination / "market.json", profile)
    support = data[
        [
            "category",
            "district_analysis",
            "area_analysis_m2",
            "bedrooms_analysis",
            "price_month_vnd",
        ]
    ]
    write_json(
        destination / "support.json", json.loads(support.to_json(orient="records"))
    )
    data[["observation_id", "property_id", "split_group", "valuation_date"]].to_csv(
        destination / "training_ids.csv", index=False
    )
    for name, source in source_files().items():
        target = destination / "training_code" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(
        destination, preview / "artifacts/models" / version_id, dirs_exist_ok=True
    )
    write_json(
        preview / "artifacts/registry.json",
        {"champion": version_id, "history": [], "preview_only": True},
    )
    if today_hanoi() < HOLDOUT_START:
        protocol["frozen_candidate"] = version_id
        protocol["candidate_frozen_at"] = datetime.now(ZONE).isoformat()
        protocol["candidate_sha256"] = metadata["model_sha256"]
        write_json(root / "data/benchmark/temporal_protocol.json", protocol)
    if (root / "frontend/dist").exists():
        shutil.copytree(
            root / "frontend/dist", preview / "frontend/dist", dirs_exist_ok=True
        )
    first = (
        predictions.loc[predictions.valuation_date.eq(predictions.first_known_date)]
        .sort_values("observation_id")
        .drop_duplicates(["fold", "variant", "split_group"])
    )
    chronological = []
    for scope, frame in [
        ("all_retrospective", predictions),
        ("new_groups_first_known", first),
    ]:
        for (kind, day, category), g in frame.groupby(
            ["variant", "valuation_date", "category"]
        ):
            chronological.append(
                dict(
                    scope=scope,
                    variant=kind,
                    date=day,
                    category=category,
                    n=len(g),
                    mae_vnd=float((g.price_month_vnd - g.prediction_vnd).abs().mean())
                    if len(g) >= 10
                    else None,
                )
            )
    pd.DataFrame(chronological).to_csv(
        report / "chronological_by_category.csv", index=False
    )
    predictions.to_csv(report / "predictions.csv", index=False)
    pd.concat(assignments, ignore_index=True).to_csv(
        report / "fold_assignments.csv", index=False
    )
    data[
        [
            "observation_id",
            "property_id",
            "split_group",
            "valuation_date",
            "date_origin",
            "raw_path",
            "raw_sha256",
        ]
    ].to_csv(report / "training_observations.csv", index=False)
    result = {
        **base,
        "status": "preview_ready",
        "selected_variant": selected,
        "candidate": version_id,
        "folds": fold_summary,
        "comparisons": comparisons,
        "date_range": list(model.date_range_),
        "behavior": behavior,
        "preview_root": str(preview),
        "promotion_blockers": [
            "December prospective holdout remains reserved and unscored.",
            "Chronological development scores are not the frozen production benchmark; no automatic promotion is authorized by these scores.",
        ],
    }
    write_json(report / "evaluation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result
