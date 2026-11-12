"""One orchestration path for local development and monthly GitHub Actions."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np

from .behavior import behavior_probe
from .eda_audit import run_audit
from .eda_reporting import generate_figures, write_report
from .modeling import run_modeling
from .modeling_reporting import generate_modeling_report
from .registry import area_distribution, read_json, register, write_json


def area_psi(previous_distribution, current):
    old, new = np.asarray(previous_distribution), np.asarray(area_distribution(current))
    return float(np.sum((new - old) * np.log(new / old)))


def eda(root):
    analysis = run_audit(root)
    figures = generate_figures(analysis, root)
    write_report(analysis, figures, root)
    return analysis


def train(root, crawl_summary=None):
    root = Path(root).resolve()
    run = root / ".work" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    for name in [
        "data/processed/listings.csv",
        "data/analysis/review_queue.csv",
        "data/benchmark/ids.csv",
    ]:
        source = root / name
        if source.exists():
            (run / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, run / name)
    registry = read_json(root / "artifacts/registry.json", {})
    previous = None
    if registry.get("champion"):
        previous = read_json(
            root / "artifacts/models" / registry["champion"] / "market.json"
        ).get("area_distribution")
    analysis = eda(run)
    meta = run_modeling(run)
    generate_modeling_report(run)
    quality = {
        "behavior_violations": behavior_probe(
            joblib.load(run / "artifacts/rental_price_pipeline.joblib")
        )["violations"],
        "development_n": meta["development_n"],
        "exclusion_rate": float((~analysis.include_price).mean()),
        "area_missing_rate": float(
            analysis.loc[analysis.include_price, "area_analysis_m2"].isna().mean()
        ),
        "area_psi": area_psi(previous, analysis) if previous is not None else 0,
        "input_mode": "integrated_crawl" if crawl_summary else "existing_snapshot",
        "crawl_errors": any(
            item.get("error") for item in (crawl_summary or {}).get("coverage", [])
        ),
        "crawl_incomplete": bool(
            crawl_summary and not crawl_summary.get("all_boundaries_reached")
        ),
    }
    decision = register(root, run, quality)
    # Expose the latest candidate reports independently of the serving champion.
    for name in ["data/analysis", "reports"]:
        shutil.copytree(run / name, root / name, dirs_exist_ok=True)
    result = {
        "finished_utc": datetime.now(UTC).isoformat(),
        "quality": quality,
        "eligible_rows": int(analysis.include_price.sum()),
        "input_rows": len(analysis),
        "evaluation": decision,
        "crawl": crawl_summary,
        "latest_collection_report": read_json(root / "reports/crawl_latest.json"),
    }
    write_json(root / "reports/pipeline_latest.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result
