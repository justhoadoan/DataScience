"""Layout semantics and constrained model responses, including adversarial targets."""

import joblib
import numpy as np
import pandas as pd
import pytest
from test_eda import row

from hanoi_rentals.behavior import behavior_probe
from hanoi_rentals.eda_audit import prepare_analysis
from hanoi_rentals.layout import explicit_bedrooms, layout_error, maximum_bedrooms
from hanoi_rentals.modeling import FEATURE_SETS, RentalPriceEstimator


def test_studio_is_known_zero_but_unknown_room_count_stays_missing():
    raw = pd.DataFrame(
        [
            row(
                listing_id="studio",
                category="nha_tro",
                title="Phòng studio khép kín",
                bedrooms=1,
            ),
            row(
                listing_id="unknown",
                category="nha_tro",
                title="Phòng khép kín có giường, bếp và WC",
                bedrooms=1,
            ),
            row(
                listing_id="explicit",
                category="nha_tro",
                title="Cho thuê 2N1K 2WC",
                area_m2=50,
                area_raw=50,
                bedrooms=np.nan,
            ),
            row(
                listing_id="impossible",
                title="Căn hộ 5PN",
                bedrooms=5,
                area_m2=10,
                area_raw=10,
            ),
            row(
                listing_id="conflict",
                title="Căn hộ 2PN",
                bedrooms=3,
                area_m2=70,
                area_raw=70,
            ),
        ]
    )
    result = prepare_analysis(raw).set_index("listing_id")
    assert result.loc["studio", "bedrooms_analysis"] == 0
    assert pd.isna(result.loc["unknown", "bedrooms_analysis"])
    assert result.loc["explicit", "bedrooms_analysis"] == 2
    assert pd.isna(result.loc["impossible", "bedrooms_analysis"])
    assert result.loc["impossible", "bedrooms_origin"] == "implausible_layout"
    assert pd.isna(result.loc["conflict", "bedrooms_analysis"])
    assert result.loc["conflict", "bedrooms_origin"] == "source_title_conflict"
    pd.testing.assert_frame_equal(
        raw.reset_index(drop=True), result.reset_index()[raw.columns]
    )


def test_layout_guard_and_ambiguous_title_do_not_invent_bedrooms():
    assert maximum_bedrooms("can_ho_chung_cu", 10) == 0
    assert maximum_bedrooms("can_ho_chung_cu", 50) == 4
    assert maximum_bedrooms("nha_tro", 100) == 2
    assert layout_error("nha_tro", 10, 5)
    assert layout_error("nha_tro", 10, 0) is None
    assert layout_error("nha_tro", 10, None) is None
    assert explicit_bedrooms("Căn hộ 1PN hoặc 2PN") == (None, "title_ambiguous")
    assert explicit_bedrooms("Cho thuê phòng đầy đủ giường, bếp, WC")[0] is None


@pytest.mark.parametrize(
    "family,params",
    [
        ("monotone", {"max_leaf_nodes": 7, "min_samples_leaf": 5}),
        ("monotone_forest", {"min_samples_leaf": 3, "max_features": 0.7}),
    ],
)
@pytest.mark.parametrize("target", ["direct", "log"])
def test_monotonic_shape_survives_confounded_training_and_serialization(
    tmp_path, family, params, target
):
    rng = np.random.default_rng(14)
    n = 180
    data = pd.DataFrame(
        {
            "category": np.where(np.arange(n) % 2, "nha_tro", "can_ho_chung_cu"),
            "district_analysis": "Hai Bà Trưng",
            "area_analysis_m2": rng.uniform(20, 150, n),
            "bedrooms_analysis": np.where(
                np.arange(n) % 2, np.nan, rng.integers(0, 4, n)
            ),
            "furniture_analysis": "Unknown",
        }
    )
    # Deliberately inverse targets: a free tree learns decreasing area/bedroom effects.
    y = (
        25e6
        - data.area_analysis_m2.to_numpy() * 60_000
        - data.bedrooms_analysis.fillna(0).to_numpy() * 2e6
        + rng.normal(0, 1e6, n)
    )
    model = RentalPriceEstimator(
        family=family, features=tuple(FEATURE_SETS["C"]), target=target, params=params
    ).fit(data, y)
    assert "bedrooms_analysis" in model.features_for_category("can_ho_chung_cu")
    assert "bedrooms_analysis" not in model.features_for_category("nha_tro")
    assert behavior_probe(model)["violations"] == 0
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)
    restored = joblib.load(path)
    np.testing.assert_allclose(model.predict(data), restored.predict(data), rtol=1e-12)
    room = {"category": "nha_tro", "district": "Hai Bà Trưng", "area": 50}
    np.testing.assert_allclose(
        restored.predict_listing(**room, bedrooms=0)["prediction_vnd_month"],
        restored.predict_listing(**room, bedrooms=2)["prediction_vnd_month"],
        rtol=1e-12,
        atol=1e-6,
    )
    with pytest.raises(ValueError, match="phòng ngủ riêng"):
        restored.predict_listing(
            category="can_ho_chung_cu", district="Hai Bà Trưng", area=10, bedrooms=5
        )
