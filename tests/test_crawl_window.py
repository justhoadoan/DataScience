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


class Phongtro123Tests(TestCase):
    def test_legacy_listing_url_uses_the_card_id(self):
        from bs4 import BeautifulSoup

        from hanoi_rentals.ingestion.phongtro123 import listing

        card = BeautifulSoup(
            '<li><h3><a href="/tinh-thanh/ha-noi/cho-thue-phong.html">Phòng trọ</a></h3>'
            '<button data-post-id="271992"></button></li>',
            "lxml",
        ).li
        self.assertEqual(listing(card, "nha_tro")["listing_id"], "271992")

    def test_crawl_from_selected_page_replays_without_duplicate_observations(self):
        import contextlib
        import io

        from hanoi_rentals.ingestion.crawler import crawl
        from hanoi_rentals.ingestion.observations import (
            load_observations,
            replay_archives,
        )

        path = "https://phongtro123.com/tinh-thanh/ha-noi"
        html = f"""<ul class="post__listing"><li>
          <script type="application/ld+json">{{"address":{{
            "addressLocality":"Hà Nội","streetAddress":"Ngõ 3, Phường Bồ Đề, Hà Nội"
          }}}}</script>
          <h3><a href="/phong-tro-pr600001.html">Phòng trọ</a></h3>
          <span class="text-green">3.5 triệu/tháng</span>
          <span class="dot"></span><span>20 m<sup>2</sup></span>
          <i class="geo-alt"></i><a>Long Biên, Hà Nội</a>
          <time title="Thứ 3, 08:45 18/11/2025">1 giờ trước</time>
        </li></ul>
        <ul class="pagination">
          <li class="active"><span class="page-link">55</span></li>
          <li><a rel="next" href="{path}?orderby=moi-nhat&amp;page=345">»»</a></li>
          <li><a rel="next" href="{path}?orderby=moi-nhat&amp;page=56">Trang sau »</a></li>
        </ul>"""
        receipt = {"collected_at": "2026-11-25T09:00:00+07:00", "http_attempts": 1}
        with TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            with patch(
                "hanoi_rentals.ingestion.crawler.fetch", return_value=(html, receipt)
            ) as network:
                result = crawl(
                    root,
                    "2025-11-01",
                    "2025-11-30",
                    1,
                    sources=["phongtro123"],
                    categories=["nha_tro"],
                    start_page=55,
                )
                self.assertEqual(
                    network.call_args.args[1], f"{path}?orderby=moi-nhat&page=55"
                )
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["coverage"][0]["next_page"], 56)
            self.assertEqual(result["added_rows"], 1)
            self.assertEqual(replay_archives(root)["added_observations"], 0)
            rows = load_observations(root)
            record = rows.iloc[0]
            self.assertEqual(record.listing_id, "pt123_600001")
            self.assertEqual(record.price_vnd, 3_500_000)
            self.assertEqual(record.area_m2, 20)
            self.assertEqual(record.posted_date, "2025-11-18")
            self.assertEqual(record.price_observed_date, "2026-11-25")
            self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            parse_page(html, "phongtro123", "nha_tro", 56)
