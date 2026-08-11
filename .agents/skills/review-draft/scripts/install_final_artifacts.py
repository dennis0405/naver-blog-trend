#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Sequence


EXPECTED_FILES = ("post.velog.md", "post.naver.txt", "quality_report.md")


class InstallError(ValueError):
    pass


def install_final_artifacts(source_dir: Path, output_dir: Path, *, replace: bool) -> None:
    source = source_dir.resolve()
    output = output_dir.resolve()
    if not source.is_dir():
        raise InstallError(f"staged artifact directory not found: {source_dir}")
    if output == source or output in source.parents or source in output.parents:
        raise InstallError("staged and final directories must not contain one another")

    entries = list(source.iterdir())
    present = sorted(path.name for path in entries)
    if present != sorted(EXPECTED_FILES):
        raise InstallError("staged directory must contain exactly the three final artifacts")
    for filename in EXPECTED_FILES:
        artifact = source / filename
        if not artifact.is_file() or artifact.is_symlink():
            raise InstallError(f"staged artifact must be a regular file: {filename}")
        if not artifact.read_bytes():
            raise InstallError(f"staged artifact is empty: {filename}")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not output.is_dir():
        raise InstallError("final output path exists and is not a directory")
    if output.exists() and not replace:
        raise InstallError("final output directory already exists; explicit replacement is required")

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    backup: Path | None = None
    try:
        for filename in EXPECTED_FILES:
            shutil.copyfile(source / filename, staging / filename)

        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            os.replace(output, backup)
        try:
            os.replace(staging, output)
        except OSError:
            if backup is not None and backup.exists():
                os.replace(backup, output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not output.exists():
            os.replace(backup, output)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a verified review-draft artifact set as one directory replacement."
    )
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        install_final_artifacts(args.source_dir, args.output_dir, replace=args.replace)
    except (InstallError, OSError) as exc:
        raise SystemExit(f"final artifact install failed: {exc}") from exc
    print(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
