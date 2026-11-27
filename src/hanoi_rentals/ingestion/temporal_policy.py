"""Version the collection window and the retrospective temporal evaluation."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from hanoi_rentals.features.dates import EPOCH, TARGET_END, ZONE


def ensure_protocol(root):
    path = Path(root) / "data/benchmark/temporal_protocol.json"
    previous = json.loads(path.read_text()) if path.exists() else None
    if (
        previous
        and previous.get("version") == 2
        and previous.get("target_until") == str(TARGET_END)
    ):
        return previous
    protocol = {
        "version": 2,
        "updated_at": datetime.now(ZONE).isoformat(),
        "target_since": str(EPOCH),
        "target_until": str(TARGET_END),
        "evaluation_kind": "retrospective_chronological_development",
        "evaluation_month": "2026-11",
        "status": "retrospective",
        "training_rule": "Use evidenced observation dates through 30 November 2026. Each chronological fold fits earlier dates and purges validation property groups.",
        "assessment_rule": "November has already been used in development. Report its chronological validation errors and category counts.",
    }
    if previous:
        protocol["previous_protocol"] = previous
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
    return protocol


def reserved_rows(frame):
    """Exclude postings and collected prices beyond the collection deadline."""
    posted = pd.to_datetime(frame.posted_date, errors="coerce")
    collected = pd.to_datetime(frame.scraped_at, errors="coerce")
    return posted.gt(pd.Timestamp(TARGET_END)) | collected.gt(pd.Timestamp(TARGET_END))
