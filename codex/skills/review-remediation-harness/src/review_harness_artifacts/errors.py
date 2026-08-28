"""作業記録コマンドが返す、機械的に判別可能なエラーを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def ijson_safe_text(value: str) -> str:
    """サロゲート文字を出力せず、ファイル名由来のデータを安全に表現する。

    Args:
        value: サロゲートエスケープを含む可能性がある文字列。

    Returns:
        I-JSONとして直列化できる診断用文字列。
    """

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
    """入れ子のJSON値に含まれる文字列をI-JSONで安全な形へ変換する。

    Args:
        value: 変換対象のJSON互換値。

    Returns:
        リストと辞書を再帰変換したI-JSONで安全な値。
    """

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
    """契約、パス、復旧、入出力で守るべき条件への違反を表す。"""

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
    """機械的に判別可能な契約違反を送出する。

    Args:
        artifact_id: 違反に関係する作業記録ID。
        field: 違反した項目またはパス。
        invariant: 機械判定に使う固定の条件名。
        detail: ユーザー向けの具体的な違反内容。

    Raises:
        ArtifactError: 常に送出する。
    """

    raise ArtifactError(
        artifact_id=artifact_id,
        field=field,
        invariant=invariant,
        detail=detail,
    )
