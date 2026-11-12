"""Verify the packaged frontend and real model, without retraining anything."""

import argparse
import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8000")
args = parser.parse_args()
base = args.url.rstrip("/")
for attempt in range(60):
    try:
        with urlopen(base + "/api/health", timeout=3) as response:
            health = json.load(response)
        break
    except (HTTPError, URLError, TimeoutError):
        time.sleep(1)
else:
    raise RuntimeError("Service did not become ready")
with urlopen(base + "/", timeout=5) as response:
    assert response.status == 200 and "text/html" in response.headers["Content-Type"]
with urlopen(base + "/api/schema", timeout=5) as response:
    schema = json.load(response)
payload = {
    "category": "can_ho_chung_cu",
    "district": schema["districts"][0],
    "area_m2": 60,
}
request = Request(
    base + "/api/predict",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urlopen(request, timeout=10) as response:
    result = json.load(response)
assert (
    math.isfinite(result["prediction_vnd_month"])
    and result["prediction_vnd_month"] >= 0
)
assert result["model_version"] == health["model_version"]
payload["category"] = "nha_rieng"
try:
    urlopen(
        Request(
            base + "/api/predict",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
    )
except HTTPError as exc:
    assert exc.code == 422
else:
    raise AssertionError("Unsupported house scope was accepted")
print(
    "Frontend, readiness, prediction and scope smoke checks passed. Model:",
    health["model_version"],
)
