import json
from hashlib import sha256
from importlib.metadata import version

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hanoi_rentals.api import create_app
from hanoi_rentals.modeling import RentalPriceEstimator, metrics


@pytest.fixture
def client(tmp_path):
    folder = tmp_path / "artifacts/models/test-version"
    folder.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "category": ["nha_tro", "can_ho_chung_cu"],
            "district_analysis": ["Cầu Giấy", "Cầu Giấy"],
            "area_analysis_m2": [25.0, 60.0],
        }
    )
    model = RentalPriceEstimator(family="category_median").fit(frame, [3e6, 10e6])
    joblib.dump(model, folder / "model.joblib")
    score = metrics([3e6, 10e6], [3e6, 9e6])
    metadata = {
        "model_sha256": sha256((folder / "model.joblib").read_bytes()).hexdigest(),
        "input": {"versions": {"scikit-learn": version("scikit-learn")}},
        "version": "test-version",
        "supported_districts": ["Cầu Giấy"],
        "category_metrics": {c: score for c in frame.category},
        "evaluated_at": "2026-10-30",
        "selected_model": "baseline_category",
        "feature_schema": list(model.features),
        "benchmark": score,
        "development_n": 100,
        "internal_test_n": 2,
        "dataset": {},
    }
    (folder / "metadata.json").write_text(json.dumps(metadata))
    (folder / "market.json").write_text(json.dumps({"districts": []}))
    (tmp_path / "artifacts/registry.json").write_text(
        json.dumps({"champion": "test-version"})
    )
    with TestClient(create_app(tmp_path)) as session:
        yield session


def test_optional_fields_are_optional_and_model_version_is_returned(client):
    response = client.post(
        "/api/predict",
        json={"category": "nha_tro", "district": "Cầu Giấy", "area_m2": 25},
    )
    assert response.status_code == 200
    assert response.json()["prediction_vnd_month"] == 3_000_000
    assert response.json()["model_version"] == "test-version"
    assert response.json()["historical_error"]["n"] == 2
    assert client.get("/api/health").json()["status"] == "ok"


@pytest.mark.parametrize(
    "change",
    [
        {"category": "nha_rieng"},
        {"area_m2": 0},
        {"area_m2": 501},
        {"area_m2": "nan"},
        {"district": "Unseen"},
        {"bedrooms": 1.5},
        {"bedrooms": 6},
        {"furnishing": "luxury"},
        {"price_vnd": 10000000},
    ],
)
def test_invalid_inputs_and_unsupported_scope_are_rejected(client, change):
    payload = {"category": "nha_tro", "district": "Cầu Giấy", "area_m2": 25, **change}
    assert client.post("/api/predict", json=payload).status_code == 422


def test_required_area_and_no_model_readiness(tmp_path, client):
    assert (
        client.post(
            "/api/predict", json={"category": "nha_tro", "district": "Cầu Giấy"}
        ).status_code
        == 422
    )
    with TestClient(create_app(tmp_path / "empty")) as empty:
        assert empty.get("/api/health").status_code == 503


def test_metrics_do_not_expose_request_payload(client):
    client.post(
        "/api/predict",
        json={"category": "nha_tro", "district": "Cầu Giấy", "area_m2": 25},
    )
    text = client.get("/metrics").text
    assert "rental_http_requests_total" in text
    assert "Cầu Giấy" not in text and "area_m2" not in text


def test_corrupt_model_is_not_reported_ready(client, tmp_path):
    path = tmp_path / "artifacts/models/test-version/model.joblib"
    path.write_bytes(path.read_bytes() + b"corrupt")
    with TestClient(create_app(tmp_path)) as corrupted:
        assert corrupted.get("/api/health").status_code == 503


def test_joint_layout_error_is_attached_to_bedrooms_and_studio_zero_is_valid(client):
    base = {"category": "nha_tro", "district": "Cầu Giấy", "area_m2": 10}
    bad = client.post("/api/predict", json={**base, "bedrooms": 5})
    assert bad.status_code == 422
    assert bad.json()["detail"][0]["loc"] == ["body", "bedrooms"]
    assert "tối đa 0" in bad.json()["detail"][0]["msg"]
    for beds in [0, None]:
        good = client.post("/api/predict", json={**base, "bedrooms": beds})
        assert good.status_code == 200
    assert client.get("/api/schema").json()["layout_policy"]["shared_area_m2"] == 8
    assert client.get("/api/model").status_code == 200


def test_nearby_evidence_uses_bundle_training_rows_and_suppresses_small_medians(
    client, tmp_path
):
    folder = tmp_path / "artifacts/models/test-version"
    support = [
        {
            "category": "nha_tro",
            "district_analysis": "Cầu Giấy",
            "area_analysis_m2": 25,
            "bedrooms_analysis": 0,
            "price_month_vnd": 3e6 + i * 1e5,
        }
        for i in range(5)
    ] + [
        {
            "category": "can_ho_chung_cu",
            "district_analysis": "Cầu Giấy",
            "area_analysis_m2": 28,
            "bedrooms_analysis": 1,
            "price_month_vnd": 10e6,
        },
        {
            "category": "nha_tro",
            "district_analysis": "Cầu Giấy",
            "area_analysis_m2": 80,
            "bedrooms_analysis": 2,
            "price_month_vnd": 30e6,
        },
    ]
    (folder / "support.json").write_text(json.dumps(support))
    with TestClient(create_app(tmp_path)) as session:
        result = session.post(
            "/api/predict",
            json={
                "category": "nha_tro",
                "district": "Cầu Giấy",
                "area_m2": 25,
                "bedrooms": 0,
            },
        ).json()
    assert result["support"]["nearby_training_n"] == 5
    assert result["support"]["bedroom_training_n"] == 5
    groups = {g["category"]: g for g in result["support"]["category_comparison"]}
    assert groups["nha_tro"]["median_vnd"] == 3_200_000
    assert groups["can_ho_chung_cu"]["median_vnd"] is None
    assert "Phòng ngủ riêng" not in result["used_features"]
