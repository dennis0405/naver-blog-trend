from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "review-draft"
    / "scripts"
    / "install_final_artifacts.py"
)
SPEC = importlib.util.spec_from_file_location("install_final_artifacts", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"failed to load installer: {SCRIPT_PATH}")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


def _write_staged(directory: Path) -> None:
    directory.mkdir(parents=True)
    for filename in INSTALLER.EXPECTED_FILES:
        (directory / filename).write_text(f"content for {filename}\n", encoding="utf-8")


class InstallFinalArtifactsTests(unittest.TestCase):
    def test_installs_exact_complete_set(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            staged = base / "staged"
            output = base / "final" / "draft"
            _write_staged(staged)

            INSTALLER.install_final_artifacts(staged, output, replace=False)

            self.assertEqual(
                sorted(path.name for path in output.iterdir()),
                sorted(INSTALLER.EXPECTED_FILES),
            )

    def test_requires_explicit_replacement(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            staged = base / "staged"
            output = base / "final"
            _write_staged(staged)
            output.mkdir()
            (output / "post.final.md").write_text("legacy\n", encoding="utf-8")

            with self.assertRaisesRegex(INSTALLER.InstallError, "explicit replacement"):
                INSTALLER.install_final_artifacts(staged, output, replace=False)

            self.assertEqual((output / "post.final.md").read_text(encoding="utf-8"), "legacy\n")

    def test_replacement_removes_legacy_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            staged = base / "staged"
            output = base / "final"
            _write_staged(staged)
            output.mkdir()
            (output / "post.final.md").write_text("legacy\n", encoding="utf-8")

            INSTALLER.install_final_artifacts(staged, output, replace=True)

            self.assertFalse((output / "post.final.md").exists())
            self.assertEqual(
                sorted(path.name for path in output.iterdir()),
                sorted(INSTALLER.EXPECTED_FILES),
            )

    def test_rejects_partial_staged_set(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            staged = base / "staged"
            staged.mkdir()
            (staged / "post.velog.md").write_text("post\n", encoding="utf-8")

            with self.assertRaisesRegex(INSTALLER.InstallError, "exactly"):
                INSTALLER.install_final_artifacts(staged, base / "final", replace=False)

    def test_rejects_extra_staged_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            staged = base / "staged"
            _write_staged(staged)
            (staged / "unexpected").mkdir()

            with self.assertRaisesRegex(INSTALLER.InstallError, "exactly"):
                INSTALLER.install_final_artifacts(staged, base / "final", replace=False)


if __name__ == "__main__":
    unittest.main()
