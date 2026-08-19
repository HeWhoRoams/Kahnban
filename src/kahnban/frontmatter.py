"""Parser and canonical serializer for Kahnban's frontmatter subset."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TypeAlias

Scalar: TypeAlias = str
Value: TypeAlias = Scalar | list[Scalar]
Frontmatter: TypeAlias = dict[str, Value]


class FrontmatterError(ValueError):
    """Raised when ticket frontmatter violates the supported subset."""


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise FrontmatterError(f"invalid quoted value: {error.msg}") from error
        if not isinstance(decoded, str):
            raise FrontmatterError("quoted value must be a string")
        return decoded
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _split_inline_items(value: str, line_number: int) -> list[str]:
    items: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {'"', "'"}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "," and quote is None:
            item = value[start:index].strip()
            if not item:
                raise FrontmatterError(f"line {line_number}: empty list item")
            items.append(item)
            start = index + 1
    if quote is not None:
        raise FrontmatterError(f"line {line_number}: unterminated quoted value")
    item = value[start:].strip()
    if not item:
        raise FrontmatterError(f"line {line_number}: empty list item")
    items.append(item)
    return items


def _parse_inline_list(value: str, line_number: int) -> list[str]:
    if not value.endswith("]"):
        raise FrontmatterError(f"line {line_number}: unterminated inline list")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_unquote(item) for item in _split_inline_items(inner, line_number)]


def parse(text: str) -> tuple[Frontmatter, str]:
    normalized = normalize_newlines(text)
    if not normalized.startswith("---\n"):
        raise FrontmatterError("frontmatter must begin with '---'")

    closing_index = normalized.find("\n---\n", 3)
    if closing_index < 0:
        raise FrontmatterError("frontmatter closing delimiter is missing")

    raw_frontmatter = normalized[4:closing_index]
    body = normalized[closing_index + 5 :]
    values: Frontmatter = {}
    current_list_key: str | None = None

    for line_number, line in enumerate(raw_frontmatter.split("\n"), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() and not stripped.startswith("- "):
            raise FrontmatterError(
                f"line {line_number}: nested mappings are not supported"
            )
        if stripped.startswith("- "):
            if current_list_key is None:
                raise FrontmatterError(
                    f"line {line_number}: list item has no parent key"
                )
            list_value = values[current_list_key]
            if not isinstance(list_value, list):
                raise FrontmatterError(
                    f"line {line_number}: list item follows a scalar"
                )
            list_value.append(_unquote(stripped[2:].strip()))
            continue
        if ":" not in line:
            raise FrontmatterError(f"line {line_number}: expected 'key: value'")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise FrontmatterError(f"line {line_number}: key cannot be empty")
        if key in values:
            raise FrontmatterError(f"line {line_number}: duplicate key '{key}'")

        raw_value = raw_value.strip()
        current_list_key = None
        if not raw_value:
            values[key] = []
            current_list_key = key
        elif raw_value.startswith("["):
            values[key] = _parse_inline_list(raw_value, line_number)
        else:
            values[key] = _unquote(raw_value)

    return values, body


def _quote_scalar(value: str) -> str:
    if not value or value != value.strip() or any(char in value for char in "#[],:\n"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def serialize(frontmatter: Mapping[str, Value], body: str) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, str):
            lines.append(f"{key}: {_quote_scalar(value)}")
            continue
        if not isinstance(value, Sequence):
            raise TypeError(f"unsupported value for '{key}': {type(value).__name__}")
        rendered = ", ".join(_quote_scalar(item) for item in value)
        lines.append(f"{key}: [{rendered}]")
    lines.extend(["---", normalize_newlines(body)])
    return "\n".join(lines)


def mutate(text: str, updates: Mapping[str, Value]) -> str:
    frontmatter, body = parse(text)
    unknown = set(updates) - set(frontmatter)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise FrontmatterError(f"cannot update missing keys: {names}")
    frontmatter.update(updates)
    return serialize(frontmatter, body)


def append_log(text: str, entry: str) -> str:
    frontmatter, body = parse(text)
    lines = body.splitlines()
    try:
        heading_index = next(
            index for index, line in enumerate(lines) if line.strip() == "## Log"
        )
    except StopIteration as error:
        raise FrontmatterError("ticket is missing the '## Log' heading") from error

    section_end = next(
        (
            index
            for index in range(heading_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    insertion_index = section_end
    while insertion_index > heading_index + 1 and not lines[insertion_index - 1].strip():
        insertion_index -= 1

    entry_lines = normalize_newlines(entry).strip("\n").split("\n")
    updated_lines = lines[:insertion_index] + entry_lines
    if section_end < len(lines):
        updated_lines.append("")
    updated_lines.extend(lines[section_end:])
    updated_body = "\n".join(updated_lines)
    if body.endswith("\n"):
        updated_body += "\n"
    return serialize(frontmatter, updated_body)