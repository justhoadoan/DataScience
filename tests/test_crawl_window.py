import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from hanoi_rentals.ingestion.crawler import page_response
from hanoi_rentals.ingestion.http import FetchError, fetch
from hanoi_rentals.ingestion.pagination import parse_page


class CrawlWindowTests(TestCase):
    def test_nhatot_advances_past_total_and_skipped_sale(self):
        raw = json.dumps({"total": 0, "ads": [{"type": "s"}]})
        rows, page = parse_page(raw, "nhatot", "nha_tro", 1, 50)
        self.assertEqual(rows, [])
        self.assertEqual(page["next_offset"], 51)
        self.assertFalse(page["exhausted"])
        self.assertTrue(
            parse_page('{"ads":[]}', "nhatot", "nha_tro", 2)[1]["exhausted"]
        )
        for raw in ("{}", '{"ads":[null]}'):
            with self.assertRaises(ValueError):
                parse_page(raw, "nhatot", "nha_tro", 1)

    def test_unrecognized_html_is_not_an_empty_page(self):
        with self.assertRaises(ValueError):
            parse_page("<html>maintenance</html>", "alonhadat", "nha_tro", 1)
        self.assertTrue(
            parse_page("<p>Tìm thấy 0 tin</p>", "alonhadat", "nha_tro", 1)[1][
                "exhausted"
            ]
        )

    def test_resume_checks_request_and_body(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "p1.json"
            body = '{"ads":[]}'
            with patch(
                "hanoi_rentals.ingestion.crawler.fetch",
                return_value=(body, {"collected_at": "2026-11-25T09:00:00+07:00"}),
            ) as network:
                page_response(None, path, "example", {"o": 0}, False)
                raw, receipt, cached = page_response(
                    None, path, "example", {"o": 0}, True
                )
                self.assertTrue(cached)
                self.assertEqual(receipt["sha256"], sha256(raw.encode()).hexdigest())
                with self.assertRaises(ValueError):
                    page_response(None, path, "example", {"o": 50}, True)
                path.write_text("{}")
                with self.assertRaises(ValueError):
                    page_response(None, path, "example", {"o": 0}, True)
                network.assert_called_once()

    def test_verification_stops_without_retry(self):
        from unittest.mock import Mock

        session = Mock()
        session.get.return_value = Mock(
            status_code=429,
            headers={},
            url="example",
            text="<title>Vui lòng xác minh không phải Robot</title>",
        )
        with self.assertRaises(FetchError) as ctx:
            fetch(session, "example")
        self.assertEqual(ctx.exception.kind, "verification_required")
        session.get.assert_called_once()


class ArchivedPriceTests(TestCase):
    def test_archive_relative_time_crossing_midnight_is_unknown(self):
        from datetime import datetime
        from hanoi_rentals.ingestion.historical import captured_day

        instant = datetime.fromisoformat("2025-11-04T01:30:00+07:00")
        self.assertIsNone(captured_day("1 giờ trước", instant))
        self.assertEqual(captured_day("10 phút trước", instant), "2025-11-04")
        self.assertIsNone(captured_day("3 tháng trước", instant))

    def test_only_original_rental_categories_and_hanoi_in_archived_state(self):
        from datetime import datetime
        from hanoi_rentals.ingestion.historical import archived_rows

        ad = dict(
            category=1010,
            region_name="Hà Nội",
            list_id=19,
            type="u",
            date="1 phút trước",
        )
        ads = [
            ad,
            {**ad, "type": "s"},
            {**ad, "region_name": "Hồ Chí Minh"},
            {**ad, "category": 1040},
        ]
        state = {"props": {"initialState": {"adlisting": {"data": {"ads": ads}}}}}
        rows = archived_rows(
            '<script id="__NEXT_DATA__">' + json.dumps(state) + "</script>",
            "nhatot",
            None,
            datetime.fromisoformat("2025-11-04T12:00:00+07:00"),
        )
        self.assertEqual([r["listing_id"] for r in rows], [19])
        self.assertEqual(rows[0]["posted_raw"], "2025-11-04")
