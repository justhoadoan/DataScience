"""Regression checks for leakage boundaries, metrics and the serialized prediction contract."""

import tempfile
import unittest
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

from hanoi_rentals.modeling import (
    MedianIndicators,
    RentalPriceEstimator,
    metrics,
    make_splits,
    validate_splits,
    cross_validate,
    config,
)
from hanoi_rentals.eda_audit import prepare_analysis, DECISIONS
from test_eda import row


def samples(n=90):
    categories = ["can_ho_chung_cu", "nha_tro"]
    return pd.DataFrame(
        [
            {
                "listing_id": f"id{i}",
                "split_group": f"group{i // 2}",
                "category": categories[(i // 2) % len(categories)],
                "source": ["nhatot", "alonhadat"][i % 2],
                "district_analysis": "District A",
                "area_analysis_m2": float(20 + i % 30),
                "bedrooms_analysis": np.nan if i % 2 else 2.0,
                "furniture_analysis": "Unknown",
                "price_month_vnd": float(2_000_000 + (i % 30) * 100_000),
            }
            for i in range(n)
        ]
    )


class ModelingTests(unittest.TestCase):
    def test_metrics_scale_negative_r2_and_degenerate_targets(self):
        m = metrics([1e6, 3e6], [2e6, 2e6])
        self.assertEqual(m["mae_vnd"], 1e6)
        self.assertEqual(m["nmae_pct"], 50.0)
        self.assertEqual(m["r2"], 0.0)
        self.assertLess(metrics([1, 2], [100, 100])["r2"], 0)
        self.assertTrue(np.isnan(metrics([1, 1], [2, 2])["r2"]))
        self.assertTrue(np.isnan(metrics([1], [2])["r2"]))

    def test_imputation_training_only_and_empty_columns(self):
        fill = MedianIndicators().fit([[10, np.nan], [20, np.nan]])
        result = fill.transform([[np.nan, 7], [1000, np.nan]])
        np.testing.assert_array_equal(fill.medians_, [15, 0])
        np.testing.assert_array_equal(result, [[15, 7, 1, 0], [1000, 0, 0, 1]])

    def test_group_isolation_and_determinism(self):
        data = samples()
        a, _ = make_splits(data)
        b, _ = make_splits(data)
        pd.testing.assert_frame_equal(a, b)
        validate_splits(data, a)
        group = a[a.partition.eq("development")].split_group.iloc[0]
        broken = a.copy()
        indices = broken.index[broken.split_group.eq(group)]
        broken.loc[indices[0], "partition"] = "internal_test"
        with self.assertRaisesRegex(ValueError, "crosses"):
            validate_splits(data, broken)

    def test_clipping_and_inference_contract(self):
        x = samples(3)
        x["area_analysis_m2"] = [10.0, 20.0, 30.0]
        x["category"] = "nha_tro"
        model = RentalPriceEstimator(params={"alpha": 0.01}).fit(x, [3e6, 2e6, 1e6])
        request = x.iloc[[0]].copy()
        request["area_analysis_m2"] = 1000.0
        self.assertLess(model.predict_raw(request)[0], 0)
        self.assertEqual(model.predict(request)[0], 0)
        unknown = model.predict_listing(
            category="nha_tro", district="Unseen district", area=None
        )
        self.assertTrue(unknown["unseen_district"])
        self.assertTrue(np.isfinite(unknown["prediction_vnd_month"]))
        with self.assertRaises(ValueError):
            model.predict_listing(category="office", district="A")
        with self.assertRaises(ValueError):
            model.predict_listing(category="nha_rieng", district="A")
        with self.assertRaises(ValueError):
            model.predict_listing(category="nha_tro", district="A", area=-1)
        with self.assertRaises(ValueError):
            model.predict_listing(
                category="nha_tro", district="A", area=20, area_unit="sqft"
            )
        with self.assertRaises(ValueError):
            model.predict_listing(category="nha_tro", district="")

    def test_whitelist_and_reload(self):
        x = samples(12)
        model = RentalPriceEstimator(target="log", params={"alpha": 1.0}).fit(
            x, x.price_month_vnd
        )
        expected = model.predict(x)
        poisoned = x.copy()
        poisoned["price_month_vnd"] = 999_000_000
        poisoned["price_raw"] = "leak"
        np.testing.assert_allclose(expected, model.predict(poisoned))
        with self.assertRaises(ValueError):
            RentalPriceEstimator(
                features=("category", "district_analysis", "price_vnd")
            ).fit(x, x.price_month_vnd)
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "model.joblib"
            joblib.dump(model, p)
            np.testing.assert_array_equal(expected, joblib.load(p).predict(x))

    def test_fold_baseline_uses_only_training_targets(self):
        data = samples()
        split, _ = make_splits(data)
        dev = data.merge(split[["listing_id", "partition", "cv_fold"]], on="listing_id")
        dev = dev[dev.partition.eq("development")]
        _, pred, _, _ = cross_validate(dev, config("global_median"), "baseline")
        self.assertEqual(set(pred.listing_id), set(dev.listing_id))
        self.assertFalse(pred.listing_id.duplicated().any())
        for k, g in pred.groupby("fold"):
            self.assertTrue(
                g.prediction_vnd.eq(
                    dev.loc[dev.cv_fold.ne(k), "price_month_vnd"].median()
                ).all()
            )

    def test_explicit_unresolved_review_overrides_keyword_miss(self):
        raw = pd.DataFrame([row(title="Street-front premises")])
        review = pd.DataFrame(
            [
                {
                    "listing_id": "nt_1",
                    **dict.fromkeys(DECISIONS, ""),
                    "scope_decision": "unresolved",
                }
            ]
        )
        result = prepare_analysis(raw, review)
        self.assertFalse(result.include_price.iloc[0])
        self.assertEqual(result.scope_flag.iloc[0], "suspicious")
        review.loc[0, "scope_decision"] = "keep"
        review.loc[0, "price_decision"] = "unresolved"
        result = prepare_analysis(raw, review)
        self.assertFalse(result.include_price.iloc[0])


if __name__ == "__main__":
    unittest.main()
