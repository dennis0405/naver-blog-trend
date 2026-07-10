from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.maintenance.prune_raw_data import (
    prune_daily_reports,
    prune_derived_directories,
    prune_derived_sqlite_rows,
    prune_raw_directories,
)


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

    def test_prune_daily_reports_keeps_recent_date_prefixed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports = Path(temp_dir)
            for name in [
                "2026-07-01.md",
                "2026-07-01.errors.md",
                "2026-07-01.trend.errors.md",
                "2026-07-02.md",
                "2026-07-03.md",
                "2026-07-09.md",
                "README.md",
                "20260701.md",
            ]:
                (reports / name).write_text("report", encoding="utf-8")

            deleted = prune_daily_reports(reports, date_value="2026-07-09", keep_days=7)

            self.assertEqual(
                deleted,
                [
                    "2026-07-01.errors.md",
                    "2026-07-01.md",
                    "2026-07-01.trend.errors.md",
                    "2026-07-02.md",
                ],
            )
            self.assertFalse((reports / "2026-07-01.md").exists())
            self.assertFalse((reports / "2026-07-02.md").exists())
            self.assertTrue((reports / "2026-07-03.md").exists())
            self.assertTrue((reports / "2026-07-09.md").exists())
            self.assertTrue((reports / "README.md").exists())
            self.assertTrue((reports / "20260701.md").exists())

    def test_prune_derived_directories_keeps_recent_date_dirs_and_root_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            derived = Path(temp_dir)
            for day in range(1, 10):
                (derived / f"2026-07-0{day}").mkdir()
            (derived / "candidates.sqlite").write_text("db", encoding="utf-8")
            (derived / "latest").mkdir()

            deleted = prune_derived_directories(derived, date_value="2026-07-09", keep_days=7)

            self.assertEqual(deleted, ["2026-07-01", "2026-07-02"])
            self.assertFalse((derived / "2026-07-02").exists())
            self.assertTrue((derived / "2026-07-03").exists())
            self.assertTrue((derived / "2026-07-09").exists())
            self.assertTrue((derived / "candidates.sqlite").exists())
            self.assertTrue((derived / "latest").exists())

    def test_prune_derived_sqlite_rows_deletes_old_date_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "candidates.sqlite"
            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE candidates (date TEXT, candidate_id TEXT)")
                connection.execute("CREATE TABLE reference_targets (date TEXT, target_id TEXT)")
                connection.executemany(
                    "INSERT INTO candidates VALUES (?, ?)",
                    [
                        ("2026-07-01", "old-a"),
                        ("2026-07-02", "old-b"),
                        ("2026-07-03", "kept-a"),
                        ("2026-07-09", "kept-b"),
                    ],
                )
                connection.executemany(
                    "INSERT INTO reference_targets VALUES (?, ?)",
                    [
                        ("2026-07-01", "old-target"),
                        ("2026-07-09", "kept-target"),
                    ],
                )

            deleted = prune_derived_sqlite_rows(db_path, date_value="2026-07-09", keep_days=7)

            self.assertEqual(deleted, {"reference_targets": 1, "candidates": 2})
            with sqlite3.connect(db_path) as connection:
                candidate_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT candidate_id FROM candidates ORDER BY candidate_id"
                    )
                ]
                target_ids = [
                    row[0]
                    for row in connection.execute(
                        "SELECT target_id FROM reference_targets ORDER BY target_id"
                    )
                ]
            self.assertEqual(candidate_ids, ["kept-a", "kept-b"])
            self.assertEqual(target_ids, ["kept-target"])


if __name__ == "__main__":
    unittest.main()
