"""FastAPI serving contract for the evaluated champion and bundled frontend."""

import logging
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from hanoi_rentals.analysis.audit import normalize
from hanoi_rentals.features.bedrooms import LAYOUT_POLICY, layout_error
from hanoi_rentals.features.dates import ZONE, today_hanoi, valuation_date_limits
from hanoi_rentals.operations.registry import champion_directory, read_json

LOGGER = logging.getLogger(__name__)
CATEGORY_LABELS = {"can_ho_chung_cu": "Căn hộ / chung cư", "nha_tro": "Phòng trọ"}


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    category: Literal["can_ho_chung_cu", "nha_tro"]
    district: str = Field(min_length=2, max_length=80)
    area_m2: float = Field(gt=5, le=500)
    bedrooms: int | None = Field(default=None, ge=0, le=6, strict=True)
    furnishing: Literal["Unknown", "Furnished", "Unfurnished"] = "Unknown"
    valuation_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("valuation_date")
    @classmethod
    def valid_calendar_date(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value

    def estimator_inputs(self):
        return {
            "category": self.category,
            "district_analysis": self.district,
            "area_analysis_m2": self.area_m2,
            "bedrooms_analysis": self.bedrooms,
            "furniture_analysis": self.furnishing,
        }

    @field_validator("bedrooms")
    @classmethod
    def room_count(cls, value, info: ValidationInfo):
        if value is not None and "category" in info.data and "area_m2" in info.data:
            message = layout_error(info.data["category"], info.data["area_m2"], value)
            if message:
                raise ValueError(message)
        return value


class ModelService:
    def __init__(self, root):
        bundle = champion_directory(root)
        self.metadata = read_json(bundle / "metadata.json")
        if (
            sha256((bundle / "model.joblib").read_bytes()).hexdigest()
            != self.metadata["model_sha256"]
        ):
            raise ValueError("Model artifact checksum mismatch")
        for name, expected in self.metadata["input"]["versions"].items():
            if version(name) != expected:
                raise ValueError(f"Model dependency mismatch: {name}")
        self.model = joblib.load(bundle / "model.joblib")
        self.market = read_json(bundle / "market.json")
        self.support = pd.DataFrame(read_json(bundle / "support.json", []))
        self.districts = {
            normalize(name).casefold(): name
            for name in self.metadata["supported_districts"]
        }
        if (
            self.metadata.get("prediction_contract_version", 1) >= 2
            and self.metadata["layout_policy"] != LAYOUT_POLICY
        ):
            raise ValueError("Serving layout policy differs from evaluated artifact.")

    def local_evidence(self, payload):
        if self.support.empty:
            return {
                "nearby_training_n": None,
                "bedroom_training_n": None,
                "area_tolerance_m2": None,
                "category_comparison": [],
            }
        tolerance = max(5, payload.area_m2 * 0.25)
        nearby = self.support[
            self.support.district_analysis.eq(payload.district)
            & self.support.area_analysis_m2.between(
                payload.area_m2 - tolerance, payload.area_m2 + tolerance
            )
        ]
        selected = nearby[nearby.category.eq(payload.category)]
        comparisons = []
        for category, group in nearby.groupby("category"):
            comparisons.append(
                {
                    "category": category,
                    "n": len(group),
                    "median_vnd": float(group.price_month_vnd.median())
                    if len(group) >= 5
                    else None,
                    "q25_vnd": float(group.price_month_vnd.quantile(0.25))
                    if len(group) >= 5
                    else None,
                    "q75_vnd": float(group.price_month_vnd.quantile(0.75))
                    if len(group) >= 5
                    else None,
                }
            )
        bedrooms_n = (
            int(selected.bedrooms_analysis.eq(payload.bedrooms).sum())
            if payload.bedrooms is not None
            else None
        )
        return {
            "nearby_training_n": len(selected),
            "bedroom_training_n": bedrooms_n,
            "area_tolerance_m2": tolerance,
            "category_comparison": comparisons,
        }

    def predict(self, payload):
        today = today_hanoi()
        chosen = (
            date.fromisoformat(payload.valuation_date)
            if payload.valuation_date
            else today
        )
        first, last = valuation_date_limits(today)
        if not first <= chosen <= last:
            raise HTTPException(
                422,
                detail=[
                    {
                        "loc": ["body", "valuation_date"],
                        "msg": f"Chọn ngày từ {first:%d/%m/%Y} đến {last:%d/%m/%Y} (giờ Hà Nội).",
                    }
                ],
            )
        valuation_date = chosen.isoformat()
        district = self.districts.get(normalize(payload.district).casefold())
        if district is None:
            raise HTTPException(
                422,
                detail=[
                    {
                        "loc": ["body", "district"],
                        "msg": "Quận/huyện chưa có đủ dữ liệu. Vui lòng chọn từ danh sách.",
                    }
                ],
            )
        payload = payload.model_copy(update={"district": district})
        inputs = {**payload.estimator_inputs(), "valuation_date": valuation_date}
        result = self.model.predict_details(pd.DataFrame([inputs])).iloc[0].to_dict()
        warnings = []
        used = self.model.features_for_category(payload.category)
        if "valuation_date" not in used:
            warnings.append("Phiên bản hiện tại chưa học ảnh hưởng của ngày định giá.")
        elif valuation_date > self.model.date_range_[1]:
            # Tree models cannot extrapolate time: later dates reuse the last learned level.
            warnings.append(
                f"Ngày định giá sau dữ liệu huấn luyện (đến {self.model.date_range_[1]}); "
                "mô hình không dự báo xu hướng mà dùng mức giá của ngày cuối cùng đó."
            )
        elif valuation_date < self.model.date_range_[0]:
            warnings.append(
                "Ngày định giá trước thời gian huấn luyện; chưa có bằng chứng về độ chính xác ở thời điểm này."
            )
        if self.metadata.get("preview_only"):
            warnings.append(
                "Bản thử nghiệm theo thời gian, chưa được duyệt thay thế model đang sử dụng."
            )
        support = self.local_evidence(payload)
        if (
            support["nearby_training_n"] is not None
            and support["nearby_training_n"] < 10
        ):
            warnings.append(
                f"Chỉ có {support['nearby_training_n']} tin huấn luyện cùng loại/quận và gần diện tích này; chưa đủ để suy ra mức giá đáng tin cho mọi bố trí."
            )
        if payload.bedrooms is not None and "bedrooms_analysis" not in used:
            reason = (
                "vì độ phủ dữ liệu còn thấp"
                if "bedrooms_analysis" in self.model.features
                else "trong bộ đặc trưng được chọn của phiên bản này"
            )
            warnings.append(
                f"Model của loại căn này chưa dùng số phòng ngủ riêng {reason}. Bố trí đã nhập không được dùng để cộng/trừ giá."
            )
        elif (
            payload.bedrooms is not None
            and support["bedroom_training_n"] is not None
            and support["bedroom_training_n"] < 5
        ):
            warnings.append(
                f"Chỉ có {support['bedroom_training_n']} tin huấn luyện gần diện tích này ghi rõ cùng số phòng ngủ; ảnh hưởng của bố trí còn ít bằng chứng tại khu vực này."
            )
        low, high = self.model.area_range_
        if (
            "area_analysis_m2" in used
            and low is not None
            and not low <= payload.area_m2 <= high
        ):
            warnings.append(
                "Diện tích nằm ngoài khoảng đã thấy khi huấn luyện; dự đoán có thể kém tin cậy."
            )
        similar = next(
            (
                r
                for r in self.market["districts"]
                if r["category"] == payload.category
                and r["district"] == payload.district
            ),
            None,
        )
        if similar is None or similar["n"] < 30:
            warnings.append(
                "Nhóm loại căn và quận/huyện này có ít hơn 30 tin trong mẫu."
            )
        if payload.bedrooms is None and "bedrooms_analysis" in used:
            warnings.append(
                "Chưa có số phòng ngủ; mô hình sử dụng cách xử lý thiếu dữ liệu đã học từ tập huấn luyện."
            )
        stats = self.metadata["category_metrics"][payload.category]
        feature_names = {
            "category": "Loại căn",
            "district_analysis": "Quận/huyện",
            "area_analysis_m2": "Diện tích",
            "bedrooms_analysis": "Phòng ngủ riêng",
            "furniture_analysis": "Nội thất",
            "valuation_date": "Ngày định giá",
        }
        LOGGER.info(
            "prediction model=%s valuation_date=%s date_feature_used=%s",
            self.metadata["version"],
            valuation_date,
            "valuation_date" in used,
        )
        return {
            "valuation_date": valuation_date,
            "date_feature_used": "valuation_date" in used,
            "prediction_vnd_month": round(float(result["prediction_vnd_month"]) / 1000)
            * 1000,
            "model_version": self.metadata["version"],
            "warnings": warnings,
            "used_features": [feature_names.get(f, f) for f in used],
            "historical_error": {
                "evaluation_kind": self.metadata.get(
                    "evaluation_kind", "frozen_benchmark"
                ),
                "mae_vnd": stats["mae_vnd"],
                "median_ae_vnd": stats["median_ae_vnd"],
                "n": stats["n"],
                "note": "Sai số kiểm định theo thời gian trong phát triển, chưa phải đánh giá tương lai độc lập."
                if self.metadata.get("preview_only")
                else "Sai số trên benchmark đã lưu, không phải khoảng tin cậy cho căn này.",
            },
            "district_sample": similar,
            "support": support,
            "scope_note": "Ước lượng giá chào thuê theo tháng cho một căn/phòng tại Hà Nội.",
        }


def create_app(root=None):
    root = Path(root or os.environ.get("RENTAL_ROOT", Path.cwd())).resolve()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = None
        app.state.load_error = None
        try:
            app.state.service = ModelService(root)
        except (FileNotFoundError, ValueError, ImportError) as exc:
            app.state.load_error = str(exc)
            LOGGER.error("Model startup failed: %s", exc)
        yield

    app = FastAPI(title="Hanoi Rent Insight API", version="1.0.0", lifespan=lifespan)
    app.state.counts = Counter()
    app.state.duration = 0.0

    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", "static")
        app.state.counts[(path, response.status_code)] += 1
        app.state.duration += perf_counter() - start
        if path == "/api/predict":
            LOGGER.info(
                "prediction status=%s latency_ms=%.1f",
                response.status_code,
                (perf_counter() - start) * 1000,
            )
        return response

    def service(request):
        value = request.app.state.service
        if value is None:
            raise HTTPException(
                503,
                "Model chưa sẵn sàng. Hãy chạy pipeline và kiểm tra deployment gate.",
            )
        return value

    @app.get("/api/health")
    def health(request: Request):
        value = service(request)
        return {"status": "ok", "model_version": value.metadata["version"]}

    @app.get("/api/schema")
    def schema(request: Request):
        value = service(request)
        today = today_hanoi()
        first, last = valuation_date_limits(today)
        return {
            "categories": [
                {"value": k, "label": v} for k, v in CATEGORY_LABELS.items()
            ],
            "districts": value.metadata["supported_districts"],
            "required": ["category", "district", "area_m2"],
            "optional": ["bedrooms", "furnishing", "valuation_date"],
            "layout_policy": LAYOUT_POLICY,
            "bedrooms_help": "Đếm phòng ngủ riêng có ngăn phòng. Studio/phòng khép kín có giường, bếp và WC nhưng không ngăn phòng ngủ là 0; chưa rõ thì để trống.",
            "area_unit": "m²",
            "currency": "VND/month",
            "valuation_date": {
                "source": "client_or_server",
                "timezone": ZONE.key,
                "today": today.isoformat(),
                "min": first.isoformat(),
                "max": last.isoformat(),
                "supported_categories": [
                    category
                    for category in CATEGORY_LABELS
                    if "valuation_date" in value.model.features_for_category(category)
                ],
            },
            "furnishing": [
                {"value": "Unknown", "label": "Chưa rõ"},
                {"value": "Furnished", "label": "Đầy đủ"},
                {"value": "Unfurnished", "label": "Nhà trống"},
            ],
        }

    @app.post("/api/predict")
    def predict(payload: PredictionRequest, request: Request):
        return service(request).predict(payload)

    @app.get("/api/model")
    def model_info(request: Request):
        value = service(request)
        meta = value.metadata
        response = {
            k: meta[k]
            for k in [
                "version",
                "evaluated_at",
                "selected_model",
                "feature_schema",
                "benchmark",
                "category_metrics",
                "development_n",
                "internal_test_n",
                "dataset",
            ]
        }
        response["category_feature_schema"] = meta.get(
            "category_feature_schema",
            {c: value.model.features_for_category(c) for c in CATEGORY_LABELS},
        )
        response["behavior"] = meta.get("behavior")
        response["preview_only"] = meta.get("preview_only", False)
        response["date_range"] = meta.get("date_range")
        response["evaluation_kind"] = meta.get("evaluation_kind", "frozen_benchmark")
        return response

    @app.get("/api/market")
    def market_info(request: Request):
        return service(request).market

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics_endpoint():
        lines = ["# TYPE rental_http_requests_total counter"]
        lines += [
            f'rental_http_requests_total{{route="{route}",status="{status}"}} {count}'
            for (route, status), count in sorted(app.state.counts.items())
        ]
        lines += [
            "# TYPE rental_http_duration_seconds_total counter",
            f"rental_http_duration_seconds_total {app.state.duration}",
        ]
        return "\n".join(lines) + "\n"

    frontend = Path(os.environ.get("FRONTEND_DIST", root / "frontend/dist"))
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
