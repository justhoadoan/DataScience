"""Grouped regression experiments with frozen splits and original-scale evaluation."""

from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from itertools import product
from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted
from threadpoolctl import threadpool_limits

from .eda_audit import ROOT, CATEGORIES, SEED, normalize
from .eda_reporting import load_analysis
from .layout import layout_error

CORE = ["category", "district_analysis", "area_analysis_m2"]
FEATURE_SETS = {
    "A": CORE,
    "B": CORE + ["bedrooms_analysis"],
    "C": CORE + ["bedrooms_analysis", "furniture_analysis"],
}
NUMERIC = ["area_analysis_m2", "bedrooms_analysis"]
ALLOWED = set(FEATURE_SETS["C"] + ["source"])
DEPS = ["scikit-learn", "numpy", "pandas", "scipy", "joblib"]


class MonotoneHistogram(RegressorMixin, BaseEstimator):
    """Enforce increasing area/bedroom responses after train-only preprocessing."""

    def __init__(self, n_numeric=1, params=None):
        self.n_numeric = n_numeric
        self.params = params

    def fit(self, X, y):
        constraints = [1] * self.n_numeric + [0] * (X.shape[1] - self.n_numeric)
        self.estimator_ = HistGradientBoostingRegressor(
            monotonic_cst=constraints,
            early_stopping=False,
            random_state=SEED,
            max_iter=200,
            learning_rate=0.07,
            loss="squared_error",
            **(self.params or {}),
        )
        with threadpool_limits(limits=2):
            self.estimator_.fit(X, y)
        return self

    def predict(self, X):
        check_is_fitted(self, "estimator_")
        with threadpool_limits(limits=2):
            return self.estimator_.predict(X)


class MedianIndicators(TransformerMixin, BaseEstimator):
    """Training-only median fill; keep every column and an explicit missing indicator."""

    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        self.medians_ = np.array(
            [np.nanmedian(c) if np.isfinite(c).any() else 0.0 for c in values.T]
        )
        return self

    def transform(self, X):
        check_is_fitted(self, "medians_")
        values = np.asarray(X, dtype=float)
        missing = np.isnan(values)
        return np.column_stack(
            [np.where(missing, self.medians_, values), missing.astype(float)]
        )


class MonotoneForest(MonotoneHistogram):
    """Native constrained forests; evaluated with the same grouped folds as boosting."""

    def fit(self, X, y):
        constraints = [1] * self.n_numeric + [0] * (X.shape[1] - self.n_numeric)
        self.estimator_ = RandomForestRegressor(
            monotonic_cst=constraints,
            n_estimators=300,
            random_state=SEED,
            n_jobs=2,
            **(self.params or {}),
        )
        self.estimator_.fit(X, y)
        return self


class RentalPriceEstimator(RegressorMixin, BaseEstimator):
    """Serializable input validation, preprocessing, regression, inverse target and clipping."""

    def __init__(
        self, family="ridge", features=tuple(CORE), target="direct", params=None
    ):
        self.family = family
        self.features = features
        self.target = target
        self.params = params

    def _frame(self, X):
        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "Supply a DataFrame with named input features; area is in m²."
            )
        if not set(self.features).issubset(ALLOWED):
            raise ValueError(
                "Predictor schema contains unsupported or leakage-prone fields."
            )
        if not {"category", "district_analysis"}.issubset(X):
            raise ValueError("category and district_analysis are required.")
        frame = X.reindex(columns=list(self.features)).copy()
        if not frame.category.isin(CATEGORIES).all():
            raise ValueError("Unsupported or missing property category.")
        if not frame.district_analysis.map(
            lambda x: isinstance(x, str) and bool(x.strip())
        ).all():
            raise ValueError("A nonempty district name is required.")
        frame["district_analysis"] = frame.district_analysis.map(normalize)
        for col in self.features:
            if col in NUMERIC:
                value = pd.to_numeric(frame[col], errors="coerce").astype(float)
                bad = frame[col].notna() & (value.isna() | ~np.isfinite(value))
                if col == "area_analysis_m2":
                    bad |= value.le(0)
                else:
                    bad |= value.lt(0) | value.mod(1).ne(0) & value.notna()
                if bad.any():
                    raise ValueError(
                        f"Invalid {col}; supply numeric m² or a nonnegative integer count, or missing."
                    )
                frame[col] = value
            elif col not in ["category", "district_analysis"]:
                frame[col] = frame[col].fillna("Unknown").astype(str)
        if (
            "furniture_analysis" in frame
            and not frame.furniture_analysis.isin(
                ["Unknown", "Furnished", "Unfurnished"]
            ).all()
        ):
            raise ValueError("Furnishing must be Furnished, Unfurnished or Unknown.")
        if "source" in frame and not frame.source.isin(["nhatot", "alonhadat"]).all():
            raise ValueError("The source-aware variant requires nhatot or alonhadat.")
        return frame

    def fit(self, X, y):
        frame = self._frame(X)
        y = np.asarray(y, dtype=float)
        if len(y) != len(frame) or not len(y) or not (np.isfinite(y) & (y > 0)).all():
            raise ValueError(
                "Training target must contain finite positive monthly rents."
            )
        if self.target not in ["direct", "log"]:
            raise ValueError("Unknown target transform.")
        self.districts_ = set(frame.district_analysis)
        area = (
            frame.area_analysis_m2.dropna()
            if "area_analysis_m2" in frame
            else pd.Series(dtype=float)
        )
        self.area_range_ = (
            (float(area.min()), float(area.max())) if len(area) else (None, None)
        )
        if self.family in ["global_median", "category_median"]:
            self.global_median_ = float(np.median(y))
            self.category_medians_ = (
                pd.Series(y).groupby(frame.category.to_numpy()).median().to_dict()
            )
            return self
        if self.family in ["monotone", "monotone_forest"]:
            self.category_models_ = {}
            for category in sorted(frame.category.unique()):
                mask = frame.category.eq(category)
                features = list(self.features)
                # Sparse/ambiguous room counts must not borrow apartment effects.
                if (
                    "bedrooms_analysis" in features
                    and frame.loc[mask, "bedrooms_analysis"].notna().mean() < 0.35
                ):
                    features.remove("bedrooms_analysis")
                child = RentalPriceEstimator(
                    family=self.family + "_single",
                    features=tuple(features),
                    target=self.target,
                    params=self.params,
                )
                self.category_models_[category] = child.fit(
                    frame.loc[mask], y[mask.to_numpy()]
                )
            return self
        numeric = [c for c in self.features if c in NUMERIC]
        categorical = [c for c in self.features if c not in NUMERIC]
        numeric_steps = [("impute_and_indicate", MedianIndicators())]
        if self.family == "ridge":
            numeric_steps.append(("scale", StandardScaler()))
            estimator = Ridge(**(self.params or {}))
        elif self.family == "forest":
            estimator = RandomForestRegressor(
                n_estimators=300, random_state=SEED, n_jobs=2, **(self.params or {})
            )
        elif self.family == "monotone_single":
            estimator = MonotoneHistogram(n_numeric=len(numeric), params=self.params)
        elif self.family == "monotone_forest_single":
            estimator = MonotoneForest(n_numeric=len(numeric), params=self.params)
        else:
            raise ValueError("Unknown estimator family.")
        preprocessor = ColumnTransformer(
            [
                ("numeric", Pipeline(numeric_steps), numeric),
                (
                    "categorical",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    categorical,
                ),
            ]
        )
        self.pipeline_ = Pipeline(
            [("preprocess", preprocessor), ("regressor", estimator)]
        )
        self.pipeline_.fit(frame, np.log(y) if self.target == "log" else y)
        return self

    def predict_raw(self, X):
        check_is_fitted(self, "districts_")
        frame = self._frame(X)
        if self.family in ["monotone", "monotone_forest"]:
            raw = np.empty(len(frame), dtype=float)
            for category, child in self.category_models_.items():
                mask = frame.category.eq(category).to_numpy()
                if mask.any():
                    raw[mask] = child.predict_raw(frame.loc[mask])
            if not frame.category.isin(self.category_models_).all():
                raise ValueError("Category was not represented in development.")
        elif self.family == "global_median":
            raw = np.full(len(frame), self.global_median_)
        elif self.family == "category_median":
            raw = (
                frame.category.map(self.category_medians_)
                .fillna(self.global_median_)
                .to_numpy()
            )
        else:
            raw = self.pipeline_.predict(frame)
            if self.target == "log":
                raw = np.exp(raw)
        if not np.isfinite(raw).all():
            raise ValueError(
                "Non-finite prediction; investigate rather than silently clip."
            )
        return np.asarray(raw, dtype=float)

    def features_for_category(self, category):
        if self.family in ["monotone", "monotone_forest"]:
            return list(self.category_models_[category].features)
        if self.family == "global_median":
            return []
        if self.family == "category_median":
            return ["category"]
        return list(self.features)

    def predict(self, X):
        return np.maximum(self.predict_raw(X), 0.0)

    def predict_details(self, X):
        raw = self.predict_raw(X)
        frame = self._frame(X)
        return pd.DataFrame(
            {
                "prediction_vnd_month": np.maximum(raw, 0),
                "raw_prediction_vnd_month": raw,
                "clipped": raw < 0,
                "unseen_district": ~frame.district_analysis.isin(self.districts_),
            },
            index=X.index,
        )

    def predict_listing(
        self,
        *,
        category,
        district,
        area=None,
        bedrooms=None,
        furnishing="Unknown",
        area_unit="m2",
        source=None,
    ):
        if area_unit not in ["m2", "m²"]:
            raise ValueError("Area must be supplied in m2 or m².")
        if category not in CATEGORIES:
            raise ValueError("Unsupported property category.")
        if bedrooms is not None:
            if (
                isinstance(bedrooms, bool)
                or not np.isfinite(float(bedrooms))
                or float(bedrooms) < 0
                or not float(bedrooms).is_integer()
            ):
                raise ValueError("Bedrooms must be a nonnegative integer or missing.")
            error = layout_error(
                category, float(area) if area is not None else None, bedrooms
            )
            if error:
                raise ValueError(error)
        frame = pd.DataFrame(
            [
                {
                    "category": category,
                    "district_analysis": district,
                    "area_analysis_m2": area,
                    "bedrooms_analysis": bedrooms,
                    "furniture_analysis": furnishing,
                    "source": source,
                }
            ]
        )
        return self.predict_details(frame).iloc[0].to_dict()


def metrics(actual, predicted):
    y, p = np.asarray(actual, float), np.asarray(predicted, float)
    if (
        len(y) != len(p)
        or not len(y)
        or not np.isfinite(y).all()
        or not np.isfinite(p).all()
    ):
        raise ValueError("Metrics require nonempty finite paired values.")
    errors = np.abs(p - y)
    variance = float(np.sum((y - y.mean()) ** 2))
    median = float(np.median(y))
    return {
        "n": len(y),
        "mae_vnd": float(errors.mean()),
        "rmse_vnd": float(np.sqrt(np.mean((p - y) ** 2))),
        "r2": float(1 - np.sum((p - y) ** 2) / variance)
        if len(y) > 1 and variance > 0
        else np.nan,
        "median_ae_vnd": float(np.median(errors)),
        "p90_ae_vnd": float(np.quantile(errors, 0.9)),
        "median_price_vnd": median,
        "nmae_pct": float(100 * errors.mean() / median) if median > 0 else np.nan,
    }


def config(family, target="direct", feature_set="A", params=None, features=None):
    return {
        "family": family,
        "target": target,
        "feature_set": feature_set,
        "params": params or {},
        "features": features or FEATURE_SETS[feature_set],
    }


def build_model(spec):
    return RentalPriceEstimator(
        family=spec["family"],
        target=spec["target"],
        features=tuple(spec["features"]),
        params=spec["params"],
    )


def make_splits(data, benchmark_ids=None):
    groups = sorted(data.split_group.unique())
    np.random.default_rng(SEED).shuffle(groups)
    test = set(groups[: round(0.2 * len(groups))])
    split = data[["listing_id", "split_group", "category", "source"]].copy()
    holdout = (
        split.listing_id.isin(benchmark_ids)
        if benchmark_ids is not None
        else split.split_group.isin(test)
    )
    split["partition"] = np.where(holdout, "internal_test", "development")
    split["cv_fold"] = -1
    dev = split[split.partition.eq("development")]
    policy = "GroupKFold(shuffle=True, random_state=42)"
    folds = list(
        GroupKFold(5, shuffle=True, random_state=SEED).split(
            dev, groups=dev.split_group
        )
    )

    def balanced(folds):
        expected = dev.category.value_counts(normalize=True)
        for train, valid in folds:
            for part in [dev.iloc[train], dev.iloc[valid]]:
                proportions = part.category.value_counts(normalize=True).reindex(
                    expected.index, fill_value=0
                )
                if (proportions < 0.5 * expected).any():
                    return False
        return True

    if not balanced(folds):
        policy = "StratifiedGroupKFold(category, shuffle=True, random_state=42)"
        folds = list(
            StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(
                dev, dev.category, dev.split_group
            )
        )
    if not balanced(folds):
        raise ValueError(
            "Five-fold category coverage fails the predeclared 50%-of-development-share check; redesign before fitting."
        )
    for k, (_, valid) in enumerate(folds):
        split.loc[dev.index[valid], "cv_fold"] = k
    validate_splits(data, split)
    return split, policy


def validate_splits(data, split):
    if split.listing_id.duplicated().any() or set(split.listing_id) != set(
        data.listing_id
    ):
        raise ValueError(
            "Saved split IDs differ from the eligible input; do not silently recreate the split."
        )
    joined = data[["listing_id", "split_group", "category", "source"]].merge(
        split, on="listing_id", suffixes=("_input", "")
    )
    for col in ["split_group", "category", "source"]:
        if not joined[col + "_input"].eq(joined[col]).all():
            raise ValueError("Saved split context no longer matches the input.")
    if not split.partition.isin(["development", "internal_test"]).all():
        raise ValueError("Unknown split partition.")
    if split.groupby("split_group").partition.nunique().max() != 1:
        raise ValueError("Duplicate group crosses development/internal test.")
    dev = split[split.partition.eq("development")]
    if (
        not set(dev.cv_fold.unique()) == set(range(5))
        or dev.groupby("split_group").cv_fold.nunique().max() != 1
    ):
        raise ValueError("Invalid folds or duplicate group crosses CV folds.")
    if not split.loc[split.partition.eq("internal_test"), "cv_fold"].eq(-1).all():
        raise ValueError("Internal-test rows must not belong to development folds.")


def fold_coverage(data):
    rows = []
    dev = data[data.partition.eq("development")]
    for k in range(5):
        for name, part in [
            ("training", dev[dev.cv_fold.ne(k)]),
            ("validation", dev[dev.cv_fold.eq(k)]),
        ]:
            t = (
                part.groupby(["category", "source"])
                .agg(n=("listing_id", "size"), groups=("split_group", "nunique"))
                .reset_index()
            )
            t["fold"] = k
            t["role"] = name
            rows.append(t)
    return pd.concat(rows, ignore_index=True)


def prediction_frame(model, frame, name, partition, fold):
    detail = model.predict_details(frame)
    out = frame[
        [
            "listing_id",
            "split_group",
            "category",
            "source",
            "district_analysis",
            "area_analysis_m2",
            "price_month_vnd",
        ]
    ].copy()
    out = out.rename(columns={"price_month_vnd": "actual_vnd"})
    out["raw_prediction_vnd"] = detail.raw_prediction_vnd_month.to_numpy()
    out["prediction_vnd"] = detail.prediction_vnd_month.to_numpy()
    out["clipped"] = detail.clipped.to_numpy()
    out["unseen_district"] = detail.unseen_district.to_numpy()
    out["area_available"] = out.area_analysis_m2.notna()
    out["residual_vnd"] = out.prediction_vnd - out.actual_vnd
    out["absolute_error_vnd"] = out.residual_vnd.abs()
    out["model"] = name
    out["partition"] = partition
    out["fold"] = fold
    return out


def score_predictions(pred):
    result = metrics(pred.actual_vnd, pred.prediction_vnd)
    result["macro_category_mae_vnd"] = float(
        np.mean(
            [
                metrics(g.actual_vnd, g.prediction_vnd)["mae_vnd"]
                for _, g in pred.groupby("category")
            ]
        )
    )
    result["clipping_count"] = int(pred.clipped.sum())
    result["clipping_rate_pct"] = float(100 * pred.clipped.mean())
    return result


def cross_validate(data, spec, name, dedup_training=False):
    start = time.monotonic()
    predictions = []
    models = []
    fold_metrics = []
    for fold in range(5):
        train = data[data.cv_fold.ne(fold)]
        valid = data[data.cv_fold.eq(fold)]
        assert set(train.split_group).isdisjoint(valid.split_group)
        if dedup_training:
            train = train.sort_values("listing_id").drop_duplicates("split_group")
        model = build_model(spec).fit(train, train.price_month_vnd)
        pred = prediction_frame(model, valid, name, "development_oof", fold)
        predictions.append(pred)
        models.append(model)
        fold_metrics.append(
            {
                "model": name,
                "partition": "development_oof",
                "fold": fold,
                **score_predictions(pred),
            }
        )
    predictions = pd.concat(predictions, ignore_index=True)
    if predictions.listing_id.duplicated().any() or set(predictions.listing_id) != set(
        data.listing_id
    ):
        raise AssertionError(
            "OOF predictions must cover each development listing exactly once."
        )
    result = {
        "model": name,
        "partition": "development_oof",
        "family": spec["family"],
        "target": spec["target"],
        "feature_set": spec["feature_set"],
        "params": json.dumps(spec["params"], sort_keys=True),
        **score_predictions(predictions),
        "fold_mae_std_vnd": float(np.std([r["mae_vnd"] for r in fold_metrics], ddof=1)),
        "runtime_seconds": time.monotonic() - start,
    }
    return result, predictions, models, fold_metrics


def subgroup_metrics(predictions):
    rows = []
    for (model, partition), p in predictions.groupby(["model", "partition"]):
        for dimension in [
            "category",
            "source",
            "area_available",
            "unseen_district",
            "source_category",
        ]:
            values = (
                p.source + "/" + p.category
                if dimension == "source_category"
                else p[dimension].astype(str)
            )
            for value, g in p.groupby(values):
                row = {
                    "model": model,
                    "partition": partition,
                    "dimension": dimension,
                    "group": value,
                    "n": len(g),
                    "comparison_tier": "counts_only"
                    if len(g) < 10
                    else ("exploratory" if len(g) < 30 else "main"),
                }
                if len(g) >= 10:
                    row.update(metrics(g.actual_vnd, g.prediction_vnd))
                rows.append(row)
    return pd.DataFrame(rows)


def permutation_diagnostics(dev, models, spec, name):
    rows = []
    for fold, model in enumerate(models):
        valid = dev[dev.cv_fold.eq(fold)]
        base = metrics(valid.price_month_vnd, model.predict(valid))["mae_vnd"]
        for feature in spec["features"]:
            for repeat in range(5):
                shuffled = valid.copy()
                rng = np.random.default_rng(SEED + fold * 100 + repeat)
                shuffled[feature] = rng.permutation(shuffled[feature].to_numpy())
                loss = metrics(valid.price_month_vnd, model.predict(shuffled))[
                    "mae_vnd"
                ]
                rows.append(
                    {
                        "model": name,
                        "fold": fold,
                        "feature": feature,
                        "repeat": repeat,
                        "mae_increase_vnd": loss - base,
                    }
                )
    return pd.DataFrame(rows)


def fingerprint(root):
    paths = ["data/analysis/listings_analysis.csv"]
    if (root / "data/benchmark/ids.csv").exists():
        paths.append("data/benchmark/ids.csv")
    payload = {p: sha256((root / p).read_bytes()).hexdigest() for p in paths}
    for name in ["modeling.py", "eda_audit.py", "layout.py"]:
        payload["code/" + name] = sha256(
            Path(__file__).with_name(name).read_bytes()
        ).hexdigest()
    payload["versions"] = {p: version(p) for p in DEPS}
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), payload


def modeling_population(root):
    """Freeze benchmark membership and quarantine duplicate peers from development."""
    raw = load_analysis(root)
    data = raw[raw.include_price].copy().reset_index(drop=True)
    benchmark = Path(root) / "data/benchmark/ids.csv"
    if benchmark.exists():
        ids = set(pd.read_csv(benchmark).listing_id)
        if not ids or not ids.issubset(set(data.listing_id)):
            raise ValueError(
                "Frozen benchmark IDs are missing or no longer eligible; review/version the benchmark explicitly."
            )
        groups = set(data.loc[data.listing_id.isin(ids), "split_group"])
        data = data.loc[
            ~data.split_group.isin(groups) | data.listing_id.isin(ids)
        ].reset_index(drop=True)
    return data


def run_modeling(root=ROOT):
    root = Path(root)
    report = root / "reports"
    artifacts = root / "artifacts"
    report.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    digest, input_info = fingerprint(root)
    meta_path = artifacts / "model_metadata.json"
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text())
        if metadata["run_fingerprint"] != digest:
            raise ValueError(
                "A completed frozen run already exists for different data/code/dependencies. Preserve it before starting a separately named experiment; do not silently reuse the internal test."
            )
        required = [
            "reports/model_comparison.csv",
            "reports/modeling_predictions.csv",
            "reports/modeling_subgroups.csv",
            "reports/model_fold_metrics.csv",
            "reports/modeling_permutation.csv",
            "reports/modeling_error_review.csv",
            "reports/modeling_fold_coverage.csv",
            "data/analysis/modeling_splits.csv",
            "artifacts/rental_price_pipeline.joblib",
        ]
        if not all((root / p).exists() for p in required):
            raise FileNotFoundError(
                "Completed run is missing artifacts; restore them rather than silently re-score the test."
            )
        if (
            sha256(
                (root / "data/analysis/modeling_splits.csv").read_bytes()
            ).hexdigest()
            != metadata["split_sha256"]
        ):
            raise ValueError(
                "The frozen split file has changed; restore the original assignments."
            )
        print(
            "Reusing the completed frozen experiment; internal test is not scored again.",
            flush=True,
        )
        return metadata
    if (artifacts / "rental_price_pipeline.joblib").exists():
        raise RuntimeError(
            "An incomplete export already contains an evaluated model. Finalize its saved outputs; do not retrain or re-score the test."
        )
    data = modeling_population(root)
    if data.listing_id.duplicated().any() or not data.price_month_vnd.gt(0).all():
        raise ValueError("Invalid eligible input.")
    split_path = root / "data/analysis/modeling_splits.csv"
    if split_path.exists():
        splits = pd.read_csv(split_path)
        validate_splits(data, splits)
        policy = "Previously frozen split assignments"
    else:
        benchmark = root / "data/benchmark/ids.csv"
        ids = set(pd.read_csv(benchmark).listing_id) if benchmark.exists() else None
        splits, policy = make_splits(data, ids)
        splits.to_csv(split_path, index=False)
    data = data.merge(
        splits[["listing_id", "partition", "cv_fold"]],
        on="listing_id",
        validate="one_to_one",
    )
    fold_coverage(data).to_csv(report / "modeling_fold_coverage.csv", index=False)
    dev = data[data.partition.eq("development")].copy()
    test = data[data.partition.eq("internal_test")].copy()
    results = []
    predictions = []
    fold_results = []
    evaluated = {}

    def evaluate(spec, name, dedup=False):
        r, p, m, f = cross_validate(dev, spec, name, dedup)
        results.append(r)
        predictions.append(p)
        fold_results.extend(f)
        evaluated[name] = (spec, r, p, m)
        print(
            f"{name}: OOF MAE={r['mae_vnd'] / 1e6:.3f}M, R²={r['r2']:.3f}", flush=True
        )
        return name

    global_name = evaluate(config("global_median"), "baseline_global")
    baseline_name = evaluate(config("category_median"), "baseline_category")
    candidates = []
    for target, alpha in product(["direct", "log"], [0.1, 1, 10, 100]):
        candidates.append(
            evaluate(
                config("ridge", target, params={"alpha": alpha}),
                f"ridge_{target}_a{alpha}",
            )
        )
    for i, (target, depth, leaf, features) in enumerate(
        product(["direct", "log"], [8, None], [3, 10], [0.7, 1.0])
    ):
        candidates.append(
            evaluate(
                config(
                    "forest",
                    target,
                    params={
                        "max_depth": depth,
                        "min_samples_leaf": leaf,
                        "max_features": features,
                    },
                ),
                f"forest_{target}_{i:02d}",
            )
        )

    def choose(names):
        best = min(names, key=lambda n: evaluated[n][1]["mae_vnd"])
        best_score = evaluated[best][1]["mae_vnd"]
        # A predeclared 1% tie band favors the simpler family / smaller feature schema.
        close = [n for n in names if evaluated[n][1]["mae_vnd"] <= 1.01 * best_score]
        return min(
            close,
            key=lambda n: (
                evaluated[n][0]["family"] != "ridge",
                len(evaluated[n][0]["features"]),
                evaluated[n][1]["mae_vnd"],
            ),
        )

    monotone_candidates = []
    for i, (target, leaves, minimum) in enumerate(
        product(["direct", "log"], [15, 31], [20, 40])
    ):
        monotone_candidates.append(
            evaluate(
                config(
                    "monotone",
                    target,
                    params={"max_leaf_nodes": leaves, "min_samples_leaf": minimum},
                ),
                f"monotone_{target}_{i:02d}",
            )
        )
    # Unconstrained models remain diagnostics; the public predictor must satisfy the layout contract.
    for i, (target, minimum) in enumerate(product(["direct", "log"], [3, 10])):
        monotone_candidates.append(
            evaluate(
                config(
                    "monotone_forest",
                    target,
                    params={"min_samples_leaf": minimum, "max_features": 0.7},
                ),
                f"monotone_forest_{target}_{i:02d}",
            )
        )
    core = choose(monotone_candidates)
    core_spec = evaluated[core][0]
    ablations = [core]
    for feature_set in ["B", "C"]:
        ablations.append(
            evaluate(
                config(
                    core_spec["family"],
                    core_spec["target"],
                    feature_set,
                    core_spec["params"],
                ),
                f"ablation_{feature_set}",
            )
        )
    candidate_name = choose(ablations)
    candidate_spec, candidate_result, candidate_pred, _ = evaluated[candidate_name]
    baseline_pred = evaluated[baseline_name][2]
    base_mae = evaluated[baseline_name][1]["mae_vnd"]
    improvement = 100 * (base_mae - candidate_result["mae_vnd"]) / base_mae
    category_changes = {}
    for cat in CATEGORIES:
        a = candidate_pred[candidate_pred.category.eq(cat)]
        b = baseline_pred[baseline_pred.category.eq(cat)]
        category_changes[cat] = 100 * (
            a.absolute_error_vnd.mean() / b.absolute_error_vnd.mean() - 1
        )
    qualifies = improvement >= 10 and max(category_changes.values()) <= 10
    selected = candidate_name if qualifies else baseline_name
    selected_spec = evaluated[selected][0]
    source_name = evaluate(
        config(
            candidate_spec["family"],
            candidate_spec["target"],
            "D",
            candidate_spec["params"],
            candidate_spec["features"] + ["source"],
        ),
        "source_diagnostic_D",
    )
    sensitivity_name = evaluate(candidate_spec, "dedup_training_sensitivity", True)
    importance = permutation_diagnostics(
        dev, evaluated[candidate_name][3], candidate_spec, candidate_name
    )
    importance.to_csv(report / "modeling_permutation.csv", index=False)
    # Record largest development errors before touching the internal test.
    largest = candidate_pred.nlargest(10, "absolute_error_vnd").merge(
        data[["listing_id", "title", "quality_flags", "review_note"]], on="listing_id"
    )
    largest.to_csv(
        report / "modeling_error_review.csv", index=False, encoding="utf-8-sig"
    )
    # Freeze selection before scoring the internal test. No test-dependent tuning below.
    selection = {
        "selected_model": selected,
        "best_source_free_candidate": candidate_name,
        "candidate_passes_practical_rule": bool(qualifies),
        "candidate_oof_improvement_pct": improvement,
        "candidate_category_mae_change_pct": category_changes,
        "selected_config": selected_spec,
        "source_diagnostic": source_name,
        "sensitivity_model": sensitivity_name,
    }
    (artifacts / "model_selection.json").write_text(
        json.dumps(selection, indent=2), encoding="utf-8"
    )
    final_model = None
    for name in dict.fromkeys([global_name, baseline_name, selected]):
        spec = evaluated[name][0]
        started = time.monotonic()
        model = build_model(spec).fit(dev, dev.price_month_vnd)
        pred = prediction_frame(model, test, name, "internal_test", -1)
        predictions.append(pred)
        results.append(
            {
                "model": name,
                "partition": "internal_test",
                "family": spec["family"],
                "target": spec["target"],
                "feature_set": spec["feature_set"],
                "params": json.dumps(spec["params"], sort_keys=True),
                **score_predictions(pred),
                "runtime_seconds": time.monotonic() - started,
            }
        )
        if name == selected:
            final_model = model
    comparison = pd.DataFrame(results)
    for part in comparison.partition.unique():
        base = float(
            comparison.loc[
                comparison.partition.eq(part) & comparison.model.eq(baseline_name),
                "mae_vnd",
            ].iloc[0]
        )
        comparison.loc[
            comparison.partition.eq(part), "improvement_vs_category_baseline_pct"
        ] = (
            100
            * (base - comparison.loc[comparison.partition.eq(part), "mae_vnd"])
            / base
        )
    comparison["selected"] = comparison.model.eq(selected)
    comparison.to_csv(report / "model_comparison.csv", index=False)
    all_predictions = pd.concat(predictions, ignore_index=True)
    all_predictions.to_csv(report / "modeling_predictions.csv", index=False)
    pd.DataFrame(fold_results).to_csv(report / "model_fold_metrics.csv", index=False)
    subgroup_metrics(all_predictions).to_csv(
        report / "modeling_subgroups.csv", index=False
    )
    joblib.dump(final_model, artifacts / "rental_price_pipeline.joblib", compress=3)
    return finalize_outputs(root, policy)


def finalize_outputs(
    root=ROOT, policy="Previously frozen split assignments", completion_note=""
):
    """Complete an export from saved predictions/model without fitting or computing new scores."""
    root = Path(root)
    artifacts = root / "artifacts"
    report = root / "reports"
    selection = json.loads((artifacts / "model_selection.json").read_text())
    selected = selection["selected_model"]
    selected_spec = selection["selected_config"]
    data = modeling_population(root)
    split_path = root / "data/analysis/modeling_splits.csv"
    splits = pd.read_csv(split_path)
    validate_splits(data, splits)
    data = data.merge(
        splits[["listing_id", "partition", "cv_fold"]],
        on="listing_id",
        validate="one_to_one",
    )
    dev = data[data.partition.eq("development")]
    test = data[data.partition.eq("internal_test")]
    pred = pd.read_csv(report / "modeling_predictions.csv")
    saved = pred[
        pred.model.eq(selected) & pred.partition.eq("internal_test")
    ].set_index("listing_id")
    if set(saved.index) != set(test.listing_id) or saved.index.duplicated().any():
        raise ValueError(
            "Saved selected-model predictions do not match the frozen test rows."
        )
    np.testing.assert_allclose(
        saved.loc[test.listing_id, "actual_vnd"], test.price_month_vnd, rtol=0, atol=0
    )
    loaded = joblib.load(artifacts / "rental_price_pipeline.joblib")
    if (
        list(loaded.features) != selected_spec["features"]
        or loaded.family != selected_spec["family"]
        or loaded.target != selected_spec["target"]
        or loaded.params != selected_spec["params"]
    ):
        raise ValueError(
            "Serialized estimator differs from the pre-test model selection."
        )
    # Parallel forest accumulation may differ at ~1e-7 VND; tolerate <1e-6 VND plus relative floating-point error.
    # This verifies serialization, not another evaluation or model-selection decision.
    np.testing.assert_allclose(
        loaded.predict(test),
        saved.loc[test.listing_id, "prediction_vnd"],
        rtol=1e-12,
        atol=1e-6,
    )
    digest, input_info = fingerprint(root)
    metadata = {
        "run_fingerprint": digest,
        "input": input_info,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "eligible_n": len(data),
        "development_n": len(dev),
        "internal_test_n": len(test),
        "split_sha256": sha256(split_path.read_bytes()).hexdigest(),
        "split_groups": data.split_group.nunique(),
        "fold_policy": policy,
        "fold_balance_rule": "Every training/validation category share >=50% of development share; category-stratified grouped fallback if needed.",
        "tie_policy": "Candidates within 1% of best OOF MAE: favor Ridge, then fewer features, then MAE.",
        "clipping_policy": "max(raw_prediction_vnd, 0); non-finite predictions rejected",
        "serialization_tolerance": "rtol=1e-12, atol=1e-6 VND; floating-point accumulation only",
        "completion_note": completion_note,
        "target_units": "VND/month",
        "feature_schema": selected_spec["features"],
        "model_fitted_on": "development only",
        "internal_test_exposure": "Previously inspected during EDA; not an untouched external test.",
        "bounded_review": "Persisted audit-queue decisions are applied before splitting, with context validation. Automated audit flags quarantine unresolved cases in the current snapshot. Manual evidence is CSV-only, not webpage verification; no numeric price threshold exclusion.",
        **selection,
    }
    (artifacts / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Frozen experiment complete. Selected: {selected}", flush=True)
    return metadata
