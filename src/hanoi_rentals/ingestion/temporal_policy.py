"""Persist the reservation before future data arrive; never silently renew it."""

import json
from datetime import datetime
from pathlib import Path

from hanoi_rentals.features.dates import (
    EPOCH,
    HOLDOUT_START,
    TARGET_END,
    ZONE,
    today_hanoi,
)


def ensure_protocol(root):
    path = Path(root) / "data/benchmark/temporal_protocol.json"
    if path.exists():
        return json.loads(path.read_text())
    protocol = {
        "version": 1,
        "reserved_at": datetime.now(ZONE).isoformat(),
        "target_since": str(EPOCH),
        "target_until": str(TARGET_END),
        "holdout_since": str(HOLDOUT_START),
        "holdout_until": str(TARGET_END),
        "reserved_before_collection_window": today_hanoi() < HOLDOUT_START,
        "training_rule": "Only evidenced observations before 2026-12-01. Never use December rows for fitting, feature selection or development validation.",
        "holdout_rule": "Prospective assessment requires reservation before December and exclusion of properties/duplicate groups used in development or the old benchmark.",
        "status": "reserved_unscored"
        if today_hanoi() < HOLDOUT_START
        else "late_reservation_not_untouched",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(protocol, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return protocol


def reserved_rows(frame):
    posted = frame.posted_date.astype(str).str[:10]
    collected = frame.scraped_at.astype(str).str[:10]
    return posted.between(str(HOLDOUT_START), str(TARGET_END)) | collected.between(
        str(HOLDOUT_START), str(TARGET_END)
    )
