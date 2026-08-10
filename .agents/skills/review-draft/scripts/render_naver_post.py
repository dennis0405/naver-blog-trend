#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path
from typing import Sequence


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
OPENING_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\n]+)\)")
AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")
STRONG_RE = re.compile(r"(?:\*\*|__)(.+?)(?:\*\*|__)")
EMPHASIS_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
UNDERSCORE_EMPHASIS_RE = re.compile(r"(?<![\w_])_([^_\n]+)_(?![\w_])")
STRIKETHROUGH_RE = re.compile(r"~~([^~\n]+)~~")
BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")
HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
TASK_ITEM_RE = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+")
NAVER_UI_PLACEHOLDERS = frozenset({"AI 활용 설정", "사진 설명을 입력하세요."})


class NaverRenderError(ValueError):
    pass


def _table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if "|" not in stripped:
        return []

    cells: list[str] = []
    current: list[str] = []
    body = stripped
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith(r"\|"):
        body = body[:-1]
    index = 0
    in_inline_code = False
    found_delimiter = False
    while index < len(body):
        character = body[index]
        if character == "\\" and index + 1 < len(body) and body[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if character == "`":
            in_inline_code = not in_inline_code
            current.append(character)
        elif character == "|" and not in_inline_code:
            cells.append("".join(current).strip())
            current = []
            found_delimiter = True
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells if found_delimiter else []


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _clean_inline(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = IMAGE_RE.sub(lambda match: f"[이미지: {match.group(1) or '설명 없음'}]", text)
    text = LINK_RE.sub(lambda match: f"{match.group(1)} ({match.group(2)})", text)
    text = AUTOLINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = STRONG_RE.sub(r"\1", text)
    text = EMPHASIS_RE.sub(r"\1", text)
    text = UNDERSCORE_EMPHASIS_RE.sub(r"\1", text)
    text = STRIKETHROUGH_RE.sub(r"\1", text)
    return text.rstrip()


def _append_blank(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _append_table(lines: list[str], table_lines: Sequence[str]) -> None:
    rows = [_table_cells(line) for line in table_lines]
    if len(rows) < 2 or not _is_table_separator(table_lines[1]):
        raise NaverRenderError("invalid Markdown table")

    headers = [_clean_inline(cell) for cell in rows[0]]
    _append_blank(lines)
    for row_index, row in enumerate(rows[2:]):
        for column_index, cell in enumerate(row):
            label = headers[column_index] if column_index < len(headers) else f"열 {column_index + 1}"
            lines.append(f"{label}: {_clean_inline(cell)}")
        if row_index < len(rows[2:]) - 1:
            _append_blank(lines)
    _append_blank(lines)


def _closing_fence(line: str, marker: str) -> bool:
    character = re.escape(marker[0])
    return bool(re.fullmatch(rf"\s*{character}{{{len(marker)},}}\s*", line))


def _validate_title(source_lines: Sequence[str]) -> None:
    first_non_empty = next((line for line in source_lines if line.strip()), "")
    if not H1_RE.fullmatch(first_non_empty):
        raise NaverRenderError("canonical Markdown must begin with one H1 title")


def render_naver_post(markdown: str) -> str:
    """Convert canonical Markdown into Naver-editor-friendly plain text."""
    source_lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    _validate_title(source_lines)
    rendered: list[str] = []
    fence_marker: str | None = None
    h1_count = 0
    index = 0

    while index < len(source_lines):
        line = source_lines[index]

        if fence_marker is not None:
            if _closing_fence(line, fence_marker):
                fence_marker = None
                _append_blank(rendered)
            else:
                rendered.append(line)
            index += 1
            continue

        opening_fence = OPENING_FENCE_RE.fullmatch(line)
        if opening_fence:
            _append_blank(rendered)
            fence_marker = opening_fence.group(1)
            index += 1
            continue

        if (
            index + 1 < len(source_lines)
            and _table_cells(line)
            and _is_table_separator(source_lines[index + 1])
        ):
            table_lines = [line, source_lines[index + 1]]
            index += 2
            while index < len(source_lines) and _table_cells(source_lines[index]):
                table_lines.append(source_lines[index])
                index += 1
            _append_table(rendered, table_lines)
            continue

        if not line.strip():
            _append_blank(rendered)
            index += 1
            continue

        heading = HEADING_RE.fullmatch(line)
        if heading:
            if H1_RE.fullmatch(line):
                h1_count += 1
            _append_blank(rendered)
            rendered.append(_clean_inline(heading.group(1)))
            _append_blank(rendered)
            index += 1
            continue

        if HORIZONTAL_RULE_RE.fullmatch(line):
            _append_blank(rendered)
            index += 1
            continue

        if line.strip() in NAVER_UI_PLACEHOLDERS:
            index += 1
            continue

        task_item = TASK_ITEM_RE.match(line)
        if task_item:
            checkbox = "☑" if task_item.group(2).lower() == "x" else "□"
            line = TASK_ITEM_RE.sub(f"{task_item.group(1)}{checkbox} ", line, count=1)

        rendered.append(_clean_inline(BLOCKQUOTE_RE.sub("", line)))
        index += 1

    if fence_marker is not None:
        raise NaverRenderError("unclosed Markdown code fence")
    if h1_count != 1:
        raise NaverRenderError("canonical Markdown must contain exactly one H1 title")

    while rendered and rendered[0] == "":
        rendered.pop(0)
    while rendered and rendered[-1] == "":
        rendered.pop()
    return "\n".join(rendered) + "\n"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_name = temp_file.name
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a canonical Markdown post as Naver-friendly plain text."
    )
    parser.add_argument("input", type=Path, help="Path to post.final.md")
    parser.add_argument("output", type=Path, help="Path to post.naver.txt")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.is_file():
        raise SystemExit(f"input file not found: {args.input}")
    if args.input.resolve() == args.output.resolve():
        raise SystemExit("input and output paths must differ")

    rendered = render_naver_post(args.input.read_text(encoding="utf-8"))
    write_atomic(args.output, rendered)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
