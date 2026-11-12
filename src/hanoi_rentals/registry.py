"""Versioned evaluated models and explicit champion promotion rules."""

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .behavior import CONTRACT_VERSION, behavior_probe
from .layout import LAYOUT_POLICY
from .modeling import metrics

DEFAULT_POLICY = {
    "min_development_rows": 500,
    "min_benchmark_rows": 100,
    "min_category_rows": 30,
    "max_mae_vnd": 2_500_000,
    "max_category_mae_vnd": {"can_ho_chung_cu": 3_500_000, "nha_tro": 1_500_000},
    "min_baseline_improvement_pct": 10,
    "min_champion_improvement_pct": 1,
    "max_category_regression_pct": 5,
    "max_exclusion_rate": 0.15,
    "max_area_missing_rate": 0.5,
    "max_area_psi": 0.25,
    "max_contract_repair_regression_pct": 10,
}


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    temporary.replace(path)


def evaluate_gate(candidate, baseline, categories, quality, champion=None, policy=None):
    """Gate saved holdout metrics; never tune candidates against the benchmark."""
    policy = policy or DEFAULT_POLICY
    reasons = []
    if quality.get("behavior_violations", 0):
        reasons.append("Prediction behavior violates area/bedroom monotonicity")
    if quality["development_n"] < policy["min_development_rows"]:
        reasons.append("Too few development rows")
    if candidate["n"] < policy["min_benchmark_rows"]:
        reasons.append("Too few frozen benchmark rows")
    candidate_valid = np.isfinite(candidate["mae_vnd"]) and candidate["mae_vnd"] >= 0
    if not candidate_valid or candidate["mae_vnd"] > policy["max_mae_vnd"]:
        reasons.append("Overall MAE exceeds quality budget")
    baseline_valid = np.isfinite(baseline["mae_vnd"]) and baseline["mae_vnd"] > 0
    gain = (
        100 * (1 - candidate["mae_vnd"] / baseline["mae_vnd"])
        if baseline_valid and candidate_valid
        else 0
    )
    if not baseline_valid:
        reasons.append(
            "Baseline metric is invalid or has zero error; explicit review required"
        )
    if gain < policy["min_baseline_improvement_pct"]:
        reasons.append("Insufficient improvement over category baseline")
    for category, limit in policy["max_category_mae_vnd"].items():
        score = categories.get(category)
        if score is None or score["n"] < policy["min_category_rows"]:
            reasons.append(f"Insufficient benchmark coverage: {category}")
        elif not np.isfinite(score["mae_vnd"]) or score["mae_vnd"] > limit:
            reasons.append(f"Category MAE exceeds budget: {category}")
    if quality["exclusion_rate"] > policy["max_exclusion_rate"]:
        reasons.append("Too many invalid or unresolved listings")
    if quality["area_missing_rate"] > policy["max_area_missing_rate"]:
        reasons.append("Area missingness exceeds budget")
    if quality.get("crawl_errors") or quality.get("crawl_incomplete"):
        reasons.append("Crawl failed or stopped before its documented boundary")
    if quality.get("area_psi", 0) > policy["max_area_psi"]:
        reasons.append("Area drift requires review")
    champion_gain = None
    if champion:
        champion_gain = 100 * (
            1 - candidate["mae_vnd"] / champion["overall"]["mae_vnd"]
        )
        repairing = champion.get("behavior", {}).get("violations", 0) > 0
        if repairing and champion_gain < -policy.get(
            "max_contract_repair_regression_pct", 10
        ):
            reasons.append("Contract repair exceeds the allowed MAE regression budget")
        elif not repairing and champion_gain < policy["min_champion_improvement_pct"]:
            reasons.append("Candidate does not improve champion enough")
        for category, old in champion["categories"].items():
            current = categories.get(category)
            if current and current["mae_vnd"] > old["mae_vnd"] * (
                1 + policy["max_category_regression_pct"] / 100
            ):
                reasons.append(f"Category regresses against champion: {category}")
    return {
        "promoted": not reasons,
        "reasons": reasons,
        "baseline_improvement_pct": gain,
        "champion_improvement_pct": champion_gain,
    }


def market_profile(analysis):
    data = analysis.loc[analysis.include_price]
    summary = []
    for (category, district), group in data.groupby(["category", "district_analysis"]):
        summary.append(
            {
                "category": category,
                "district": district,
                "n": len(group),
                "median_vnd": float(group.price_month_vnd.median()),
                "q25_vnd": float(group.price_month_vnd.quantile(0.25)),
                "q75_vnd": float(group.price_month_vnd.quantile(0.75)),
                "area_median": float(group.area_analysis_m2.median())
                if group.area_analysis_m2.notna().any()
                else None,
            }
        )
    return {
        "rows": len(analysis),
        "eligible_rows": len(data),
        "posting_start": str(analysis.posted_date.min()),
        "posting_end": str(analysis.posted_date.max()),
        "source_counts": data.source.value_counts().to_dict(),
        "districts": summary,
        "area_distribution": area_distribution(analysis),
    }


def area_distribution(frame):
    bins = [-np.inf, 15, 25, 40, 60, 90, 150, np.inf]
    counts = (
        pd.cut(frame.area_analysis_m2, bins)
        .value_counts(sort=False)
        .to_numpy(dtype=float)
    )
    counts = np.append(counts, frame.area_analysis_m2.isna().sum()) + 0.5
    return (counts / counts.sum()).tolist()


def register(root, run_root, quality):
    root, run_root = Path(root), Path(run_root)
    meta = read_json(run_root / "artifacts/model_metadata.json")
    version = meta["run_fingerprint"][:16]
    destination = root / "artifacts/models" / version
    registry_path = root / "artifacts/registry.json"
    registry = read_json(registry_path, {"champion": None, "history": []})
    if registry["champion"] == version:
        return {
            "promoted": False,
            "candidate": version,
            "champion": version,
            "reasons": ["Identical evaluated model is already champion"],
        }
    comparison = pd.read_csv(run_root / "reports/model_comparison.csv")
    baseline = comparison[
        (comparison.model == "baseline_category")
        & (comparison.partition == "internal_test")
    ].iloc[0]
    pred = pd.read_csv(run_root / "reports/modeling_predictions.csv")
    pred = pred[
        (pred.model == meta["selected_model"]) & (pred.partition == "internal_test")
    ]
    categories = {
        category: metrics(g.actual_vnd, g.prediction_vnd)
        for category, g in pred.groupby("category")
    }
    overall = metrics(pred.actual_vnd, pred.prediction_vnd)
    champion_scores = None
    if registry["champion"]:
        current = root / "artifacts/models" / registry["champion"]
        old_meta = read_json(current / "metadata.json")
        if old_meta["input"].get("data/benchmark/ids.csv") != meta["input"].get(
            "data/benchmark/ids.csv"
        ):
            raise ValueError(
                "Benchmark changed: explicitly version the evaluation protocol before comparing champions."
            )
        model = joblib.load(current / "model.joblib")
        analysis = pd.read_csv(
            run_root / "data/analysis/listings_analysis.csv"
        ).set_index("listing_id")
        benchmark = analysis.loc[pred.listing_id].copy()
        prediction = model.predict(benchmark)
        champion_scores = {
            "overall": metrics(benchmark.price_month_vnd, prediction),
            "categories": {},
            "behavior": behavior_probe(model),
        }
        for category in categories:
            mask = benchmark.category.eq(category).to_numpy()
            champion_scores["categories"][category] = metrics(
                benchmark.price_month_vnd.to_numpy()[mask], prediction[mask]
            )
    policy_path = root / "config/promotion.json"
    policy = read_json(policy_path, DEFAULT_POLICY)
    candidate_behavior = behavior_probe(
        joblib.load(run_root / "artifacts/rental_price_pipeline.joblib")
    )
    quality = {**quality, "behavior_violations": candidate_behavior["violations"]}
    decision = evaluate_gate(
        overall, baseline.to_dict(), categories, quality, champion_scores, policy
    )
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        run_root / "artifacts/rental_price_pipeline.joblib",
        destination / "model.joblib",
    )
    analysis = pd.read_csv(run_root / "data/analysis/listings_analysis.csv")
    profile = market_profile(analysis)
    model = joblib.load(destination / "model.joblib")
    bundle = {
        **meta,
        "model_sha256": sha256((destination / "model.joblib").read_bytes()).hexdigest(),
        "version": version,
        "prediction_contract_version": CONTRACT_VERSION,
        "behavior": candidate_behavior,
        "layout_policy": LAYOUT_POLICY,
        "category_feature_schema": {
            c: model.features_for_category(c) for c in ["can_ho_chung_cu", "nha_tro"]
        },
        "benchmark": overall,
        "category_metrics": categories,
        "supported_districts": sorted(model.districts_),
        "scope": ["can_ho_chung_cu", "nha_tro"],
        "evaluated_at": datetime.now(UTC).isoformat(),
        "quality": quality,
        "dataset": {k: v for k, v in profile.items() if k != "districts"},
    }
    write_json(destination / "metadata.json", bundle)
    write_json(destination / "market.json", profile)
    write_json(
        destination / "evaluation.json",
        {
            "decision": decision,
            "champion_on_same_benchmark": champion_scores,
            "policy": policy,
            "benchmark_sha256": meta["input"].get("data/benchmark/ids.csv"),
        },
    )
    provenance = destination / "training_code"
    provenance.mkdir(exist_ok=True)
    for name in ["modeling.py", "eda_audit.py", "layout.py", "behavior.py"]:
        shutil.copy2(Path(__file__).with_name(name), provenance / name)
    for name in ["pyproject.toml", "requirements.lock", "config/promotion.json"]:
        source = root / name
        if source.exists():
            shutil.copy2(source, provenance / source.name)
    splits = pd.read_csv(run_root / "data/analysis/modeling_splits.csv")
    splits[splits.partition.eq("development")][["listing_id", "split_group"]].to_csv(
        destination / "training_ids.csv", index=False
    )
    development_ids = set(splits.loc[splits.partition.eq("development"), "listing_id"])
    support = analysis.loc[
        analysis.listing_id.isin(development_ids),
        [
            "category",
            "district_analysis",
            "area_analysis_m2",
            "bedrooms_analysis",
            "price_month_vnd",
        ],
    ]
    write_json(
        destination / "support.json", json.loads(support.to_json(orient="records"))
    )
    entry = {
        "candidate": version,
        "previous_champion": registry["champion"],
        "evaluated_at": bundle["evaluated_at"],
        **decision,
    }
    registry["history"].append(entry)
    if decision["promoted"]:
        registry["champion"] = version
    write_json(registry_path, registry)
    return {**decision, "candidate": version, "champion": registry["champion"]}


def champion_directory(root):
    root = Path(root)
    registry = read_json(root / "artifacts/registry.json")
    if not registry or not registry.get("champion"):
        raise FileNotFoundError(
            "No model has passed the deployment gate. Run the training pipeline first."
        )
    return root / "artifacts/models" / registry["champion"]
