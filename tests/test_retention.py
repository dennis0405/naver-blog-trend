from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.maintenance.prune_raw_data import prune_raw_directories


class RetentionTests(unittest.TestCase):
    def test_prune_keeps_recent_seven_days(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = Path(temp_dir)
            for day in range(1, 10):
                (raw / f"2026-07-0{day}").mkdir()
            deleted = prune_raw_directories(raw, date_value="2026-07-09", keep_days=7)
            self.assertEqual(deleted, ["2026-07-01", "2026-07-02"])
            self.assertFalse((raw / "2026-07-02").exists())
            self.assertTrue((raw / "2026-07-03").exists())
            self.assertTrue((raw / "2026-07-09").exists())


if __name__ == "__main__":
    unittest.main()

