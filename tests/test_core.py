import io
import tarfile
import tempfile
from pathlib import Path
from unittest import SkipTest, TestCase

import numpy as np

from hanoi_rentals.operations.registry import evaluate_gate, gain_lower_bound
from hanoi_rentals.operations.state import restore_state

ROOT = Path(__file__).resolve().parents[1]
PASSING = dict(
    candidate={"n": 400, "mae_vnd": 1_500_000},
    baseline={"mae_vnd": 2_500_000},
    categories={
        "can_ho_chung_cu": {"n": 150, "mae_vnd": 2_300_000},
        "nha_tro": {"n": 250, "mae_vnd": 1_000_000},
    },
    quality={"development_n": 5000, "exclusion_rate": 0.05, "area_missing_rate": 0.1},
)


def champion(mae, ci_low):
    return {
        "overall": {"mae_vnd": mae},
        "categories": {},
        "behavior": {"violations": 0},
        "gain_ci_low_pct": ci_low,
    }


class GateTests(TestCase):
    def test_good_candidate_without_champion_is_promoted(self):
        self.assertTrue(evaluate_gate(**PASSING)["promoted"])

    def test_gain_within_noise_is_rejected(self):
        decision = evaluate_gate(**PASSING, champion=champion(1_560_000, -2.0))
        self.assertFalse(decision["promoted"])
        self.assertIn("noise", decision["reasons"][0])

    def test_clear_gain_is_promoted(self):
        self.assertTrue(
            evaluate_gate(**PASSING, champion=champion(1_700_000, 3.0))["promoted"]
        )

    def test_behavior_violation_blocks_promotion(self):
        quality = {**PASSING["quality"], "behavior_violations": 2}
        self.assertFalse(evaluate_gate(**{**PASSING, "quality": quality})["promoted"])

    def test_bootstrap_lower_bound(self):
        rng = np.random.default_rng(0)
        old = rng.uniform(0, 2, 400)
        self.assertGreater(gain_lower_bound(old, old * 0.8), 0)
        self.assertLess(gain_lower_bound(old, rng.permutation(old)), 0)


class StateTests(TestCase):
    def test_restore_rejects_unexpected_members(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "state.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                info = tarfile.TarInfo("src/evil.py")
                info.size = 1
                output.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                restore_state(Path(folder) / "root", archive)


class ApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except (ImportError, RuntimeError) as exc:
            raise SkipTest(f"API test client unavailable: {exc}")

        from hanoi_rentals.serving.api import create_app

        cls.context = TestClient(create_app(ROOT))
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def predict(self, **body):
        return self.client.post("/api/predict", json=body)

    def test_prediction_and_district_normalization(self):
        exact = self.predict(category="nha_tro", district="Cầu Giấy", area_m2=20)
        loose = self.predict(category="nha_tro", district="  cầu giấy ", area_m2=20)
        self.assertEqual(exact.status_code, 200)
        self.assertGreater(exact.json()["prediction_vnd_month"], 0)
        self.assertEqual(
            loose.json()["prediction_vnd_month"], exact.json()["prediction_vnd_month"]
        )

    def test_invalid_inputs_are_rejected(self):
        self.assertEqual(
            self.predict(category="nha_tro", district="Paris", area_m2=20).status_code,
            422,
        )
        self.assertEqual(
            self.predict(category="nha_tro", district="Cầu Giấy", area_m2=1).status_code,
            422,
        )
