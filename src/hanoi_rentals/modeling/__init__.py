"""Public modeling API, including the import paths used by existing joblib bundles.

Keep estimator classes available here: historical artifacts refer to
``hanoi_rentals.modeling.RentalPriceEstimator`` and the custom transformers.
Training implementation lives in :mod:`hanoi_rentals.modeling.training`.
"""

from .training import (
    ALLOWED,
    CORE,
    DEPS,
    FEATURE_SETS,
    NUMERIC,
    MedianIndicators,
    MonotoneForest,
    MonotoneHistogram,
    RentalPriceEstimator,
    build_model,
    config,
    cross_validate,
    finalize_outputs,
    fingerprint,
    fold_coverage,
    make_splits,
    metrics,
    modeling_population,
    permutation_diagnostics,
    prediction_frame,
    run_modeling,
    score_predictions,
    subgroup_metrics,
    validate_splits,
)

__all__ = [
    "ALLOWED",
    "CORE",
    "DEPS",
    "FEATURE_SETS",
    "NUMERIC",
    "MedianIndicators",
    "MonotoneForest",
    "MonotoneHistogram",
    "RentalPriceEstimator",
    "build_model",
    "config",
    "cross_validate",
    "finalize_outputs",
    "fingerprint",
    "fold_coverage",
    "make_splits",
    "metrics",
    "modeling_population",
    "permutation_diagnostics",
    "prediction_frame",
    "run_modeling",
    "score_predictions",
    "subgroup_metrics",
    "validate_splits",
]
