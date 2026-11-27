import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import pandas as pd

from hanoi_rentals.features.dates import TARGET_END
from hanoi_rentals.ingestion.temporal_policy import ensure_protocol, reserved_rows
from hanoi_rentals.modeling.temporal_holdout import evaluate_holdout


class NovemberWindowTests(TestCase):
    def test_old_reservation_is_preserved_during_window_migration(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "data/benchmark/temporal_protocol.json"
            path.parent.mkdir(parents=True)
            old = {
                "version": 1,
                "target_until": "2026-12-31",
                "frozen_candidate": "old",
            }
            path.write_text(json.dumps(old))
            new = ensure_protocol(root)
            self.assertEqual(new["target_until"], "2026-11-30")
            self.assertEqual(new["status"], "retrospective")
            self.assertEqual(new["previous_protocol"], old)
            self.assertEqual(ensure_protocol(root), new)
            self.assertEqual(evaluate_holdout(root)["status"], "training_required")

    def test_deadline_includes_november_and_excludes_later_versions(self):
        self.assertEqual(str(TARGET_END), "2026-11-30")
        rows = pd.DataFrame(
            {
                "posted_date": ["2026-11-30", "2026-12-01", "2026-11-30", None],
                "scraped_at": ["2026-11-30", "2026-11-30", "2026-12-01", "2026-11-30"],
            }
        )
        self.assertEqual(reserved_rows(rows).tolist(), [False, True, True, False])
