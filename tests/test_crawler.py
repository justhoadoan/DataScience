from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from hanoi_rentals.ingestion import crawler
from hanoi_rentals.ingestion.normalization import COMMON_COLUMNS
from hanoi_rentals.ingestion.sources import parse_nhatot
from test_eda import row
import json


def test_new_month_does_not_overwrite_reviewed_history_and_deduplicates(
    tmp_path, monkeypatch
):
    old = pd.DataFrame([row()])[COMMON_COLUMNS]
    destination = tmp_path / "data/processed/listings.csv"
    destination.parent.mkdir(parents=True)
    old.to_csv(destination, index=False, encoding="utf-8-sig")
    before = destination.read_bytes()
    incoming = pd.DataFrame(
        [row(price_vnd=9e6), row(listing_id="nt_2", posted_date="2026-10-01")]
    )[COMMON_COLUMNS]

    def fake(source, *args):
        frame = incoming if source == "nhatot" else pd.DataFrame(columns=COMMON_COLUMNS)
        return frame, [{"source": source, "window_boundary_reached": True}]

    monkeypatch.setattr(crawler, "crawl_source", fake)
    result = crawler.crawl(tmp_path, "2026-10-01", "2026-10-27")
    after = pd.read_csv(destination)
    assert result["added_rows"] == 1 and after.listing_id.is_unique
    assert destination.read_bytes().startswith(before)
    assert after.iloc[0].price_vnd == 5_000_000
    assert after.iloc[1].posted_date == "2026-10-01"


def test_future_window_is_rejected_before_network(tmp_path):
    with pytest.raises(ValueError):
        crawler.crawl(tmp_path, "2099-10-01", "2099-10-31")


def test_source_timestamp_uses_vietnam_day_boundary():
    stamp = int(
        datetime(2026, 10, 1, 0, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).timestamp()
        * 1000
    )
    raw = json.dumps({"ads": [{"type": "u", "list_time": stamp, "list_id": 1}]})
    assert parse_nhatot(raw, "nha_tro", 0)[0]["posted_raw"] == "2026-10-01"
