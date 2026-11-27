from itertools import product
from unittest import TestCase

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from hanoi_rentals.features.dates import today_hanoi
from hanoi_rentals.modeling.temporal import estimator, variant_frame
from hanoi_rentals.serving.api import ModelService, PredictionRequest


class EnrichedPredictionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        day = today_hanoi().isoformat()
        rows = []
        for category, ward, project, bathrooms, repeat in product(
            ["can_ho_chung_cu", "nha_tro"],
            ["ward_a", "ward_b"],
            ["project_a", "project_b"],
            [1, 2],
            range(15),
        ):
            rows.append(
                {
                    "category": category,
                    "district_analysis": "Cầu Giấy",
                    "area_analysis_m2": 50,
                    "bedrooms_analysis": 1,
                    "furniture_analysis": "Unknown",
                    "valuation_date": day,
                    "ward_key": ward,
                    "project_id": project,
                    "bathroom_count": str(bathrooms),
                    "price": 3_000_000
                    + 1_000_000 * bathrooms
                    + 2_000_000 * (ward == "ward_b")
                    + 4_000_000 * (project == "project_b"),
                }
            )
        data = pd.DataFrame(rows)
        cls.service = object.__new__(ModelService)
        cls.service.model = estimator("enriched").fit(data, data.price)
        cls.service.districts = {"cầu giấy": "Cầu Giấy", "ba đình": "Ba Đình"}
        cls.service.market = {"districts": []}
        cls.service.support = pd.DataFrame()
        cls.service.metadata = {
            "version": "synthetic",
            "preview_only": True,
            "category_metrics": {
                c: {"mae_vnd": 1, "median_ae_vnd": 1, "n": 120}
                for c in data.category.unique()
            },
            "property_options": {
                "wards": [
                    {"value": w, "label": w, "district": "Cầu Giấy"}
                    for w in ["ward_a", "ward_b"]
                ],
                "projects": [
                    {"value": p, "label": p, "districts": ["Cầu Giấy"]}
                    for p in ["project_a", "project_b"]
                ],
            },
        }

    def payload(self, **changes):
        return PredictionRequest.model_validate(
            {
                "category": "can_ho_chung_cu",
                "district": "Cầu Giấy",
                "area_m2": 50,
                "bedrooms": 1,
                "ward_key": "ward_a",
                "project_id": "project_a",
                "bathrooms": 1,
                **changes,
            }
        )

    def test_serving_values_match_training_and_change_predictions(self):
        payload = self.payload()
        result = self.service.predict(payload)
        inputs = {
            **payload.estimator_inputs(),
            "valuation_date": today_hanoi().isoformat(),
        }
        expected = self.service.model.predict(pd.DataFrame([inputs]))[0]
        self.assertEqual(result["prediction_vnd_month"], round(expected / 1000) * 1000)
        self.assertIn("Ward / commune", result["used_features"])
        self.assertIn("Development", result["used_features"])
        self.assertIn("Bathrooms / WC", result["used_features"])
        for changes in [
            {"ward_key": "ward_b"},
            {"project_id": "project_b"},
            {"bathrooms": 2},
        ]:
            changed = self.service.predict(self.payload(**changes))
            self.assertGreater(
                changed["prediction_vnd_month"], result["prediction_vnd_month"]
            )

    def test_missing_values_remain_unknown(self):
        payload = self.payload(ward_key="Unknown", project_id="Unknown", bathrooms=None)
        self.assertEqual(payload.estimator_inputs()["bathroom_count"], "Unknown")
        self.assertGreater(self.service.predict(payload)["prediction_vnd_month"], 0)

    def test_unlisted_and_wrong_district_choices_are_rejected(self):
        for changes in [
            {"ward_key": "invented"},
            {"project_id": "invented"},
            {"district": "Ba Đình"},
        ]:
            with self.assertRaises(HTTPException) as caught:
                self.service.predict(self.payload(**changes))
            self.assertEqual(caught.exception.status_code, 422)

    def test_invalid_bathrooms_are_rejected(self):
        for value in [-1, 1.5, True, 11]:
            with self.assertRaises(ValidationError):
                self.payload(bathrooms=value)
        with self.assertRaises(ValidationError):
            self.payload(category="nha_tro", bathrooms=6)

    def test_recovery_does_not_change_baseline_or_use_provenance_as_predictor(self):
        data = pd.DataFrame(
            [
                {
                    "area_analysis_m2": 50,
                    "bedrooms_analysis": None,
                    "furniture_analysis": "Unknown",
                    "recovered_area": 50,
                    "recovered_bedrooms": 1,
                    "recovered_furnishing": "Furnished",
                    "toilets_analysis": 2,
                }
            ]
        )
        self.assertIs(variant_frame(data, "elapsed"), data)
        recovered = variant_frame(data, "enriched")
        self.assertEqual(recovered.iloc[0].bedrooms_analysis, 1)
        self.assertEqual(recovered.iloc[0].bathroom_count, "2")
        self.assertIsNone(data.iloc[0].bedrooms_analysis)
        self.assertNotIn("area_origin", estimator("enriched").features)
