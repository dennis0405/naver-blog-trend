from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or value == "replace_me":
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load the small YAML subset used by this project without dependencies."""

    lines: list[tuple[int, str]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))

    def parse_scalar(value: str) -> Any:
        if value in {"true", "True"}:
            return True
        if value in {"false", "False"}:
            return False
        if value in {"null", "None"}:
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        if lines[index][0] < indent:
            return {}, index
        is_list = lines[index][0] == indent and lines[index][1].startswith("- ")
        if is_list:
            result: list[Any] = []
            while index < len(lines):
                current_indent, text = lines[index]
                if current_indent < indent:
                    break
                if current_indent != indent or not text.startswith("- "):
                    break
                item = text[2:].strip()
                index += 1
                if item:
                    result.append(parse_scalar(item))
                else:
                    child, index = parse_block(index, indent + 2)
                    result.append(child)
            return result, index

        result: dict[str, Any] = {}
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent < indent:
                break
            if current_indent != indent:
                break
            if ":" not in text:
                raise ConfigError(f"Invalid YAML line: {text}")
            key, remainder = text.split(":", 1)
            key = key.strip()
            remainder = remainder.strip()
            index += 1
            if remainder:
                result[key] = parse_scalar(remainder)
            else:
                child, index = parse_block(index, indent + 2)
                result[key] = child
        return result, index

    parsed, final_index = parse_block(0, 0)
    if final_index != len(lines):
        raise ConfigError(f"Could not parse YAML file completely: {path}")
    if not isinstance(parsed, dict):
        raise ConfigError(f"YAML root must be a mapping: {path}")
    return parsed


def iter_search_queries(
    config: dict[str, Any], selected_layers: str | list[str]
) -> list[dict[str, str]]:
    if selected_layers == "all":
        layers = ["discovery", "target"]
    elif isinstance(selected_layers, str):
        layers = [part.strip() for part in selected_layers.split(",") if part.strip()]
    else:
        layers = selected_layers

    entries: list[dict[str, str]] = []
    for layer_name in layers:
        layer = config.get(layer_name)
        if not isinstance(layer, dict) or not layer.get("enabled", True):
            continue
        query_groups = layer.get("query_groups", {})
        if not isinstance(query_groups, dict):
            raise ConfigError(f"{layer_name}.query_groups must be a mapping")
        for group_name, queries in query_groups.items():
            if not isinstance(queries, list):
                raise ConfigError(f"{layer_name}.{group_name} must be a list")
            for query in queries:
                entries.append(
                    {
                        "search_layer": layer_name,
                        "query_group": str(group_name),
                        "query": str(query),
                    }
                )
    return entries


def collection_config(config: dict[str, Any]) -> dict[str, Any]:
    collection = config.get("collection", {})
    if not isinstance(collection, dict):
        raise ConfigError("collection must be a mapping")
    return collection

