"""Structured failures returned by the artifact CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def ijson_safe_text(value: str) -> str:
    """Represent surrogateescaped filesystem bytes without emitting surrogates."""

    parts: list[str] = []
    filesystem_bytes = bytearray()

    def flush_filesystem_bytes() -> None:
        if filesystem_bytes:
            parts.append(f"<filesystem-bytes-hex:{filesystem_bytes.hex()}>")
            filesystem_bytes.clear()

    for character in value:
        codepoint = ord(character)
        if 0xDC80 <= codepoint <= 0xDCFF:
            filesystem_bytes.append(codepoint - 0xDC00)
            continue
        flush_filesystem_bytes()
        if 0xD800 <= codepoint <= 0xDFFF:
            parts.append(f"<unicode-surrogate-hex:{codepoint:04x}>")
        else:
            parts.append(character)
    flush_filesystem_bytes()
    return "".join(parts)


def ijson_safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return ijson_safe_text(value)
    if isinstance(value, list):
        return [ijson_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {
            ijson_safe_text(key) if isinstance(key, str) else key: ijson_safe_value(
                item
            )
            for key, item in value.items()
        }
    return value


@dataclass(slots=True)
class ArtifactError(Exception):
    """A contract, path, recovery, or I/O invariant violation."""

    artifact_id: str | None
    field: str
    invariant: str
    detail: str

    def __post_init__(self) -> None:
        if self.artifact_id is not None:
            self.artifact_id = ijson_safe_text(self.artifact_id)
        self.field = ijson_safe_text(self.field)
        self.invariant = ijson_safe_text(self.invariant)
        self.detail = ijson_safe_text(self.detail)

    def __str__(self) -> str:
        return f"{self.invariant} at {self.field}: {self.detail}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "field": self.field,
            "invariant": self.invariant,
            "detail": self.detail,
        }


def fail(
    *,
    artifact_id: str | None,
    field: str,
    invariant: str,
    detail: str,
) -> None:
    """Raise a structured contract failure."""

    raise ArtifactError(
        artifact_id=artifact_id,
        field=field,
        invariant=invariant,
        detail=detail,
    )
