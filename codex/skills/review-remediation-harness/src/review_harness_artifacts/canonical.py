"""JSONを厳密に読み込み、RFC 8785 JCSとSHA-256へ変換する。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import rfc8785

from .errors import ArtifactError, fail

MAX_IJSON_INTEGER = 9_007_199_254_740_991


def sha256_hex(content: bytes) -> str:
    """bytesのSHA-256を小文字の16進数で返す。

    Args:
        content: ハッシュを計算するbytes。

    Returns:
        64文字のSHA-256。
    """

    return hashlib.sha256(content).hexdigest()


def _reject_constant(value: str) -> None:
    fail(
        field="$",
        invariant="json_number_must_be_finite",
        detail=f"有限でないJSON数値は使用できません: {value}",
        next_action="NaNまたはInfinityを有限のJSON数値へ置き換えてください。",
    )


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(
                field=f"$.{key}",
                invariant="json_object_keys_must_be_unique",
                detail=f"JSON object内でkeyが重複しています: {key}",
                next_action="重複したkeyを1つにまとめてください。",
            )
        result[key] = value
    return result


def _validate_json_value(value: Any, field: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            fail(
                field=field,
                invariant="json_string_must_be_unicode_scalar_values",
                detail="単独のUnicode surrogateはI-JSONとして保存できません。",
                next_action="正しいUnicode文字へ置き換えてください。",
            )
        return
    if isinstance(value, int):
        if abs(value) > MAX_IJSON_INTEGER:
            fail(
                field=field,
                invariant="json_integer_must_be_ijson_exact",
                detail=f"整数がI-JSONの正確な範囲を超えています: {value}",
                next_action="文字列にするか、安全な整数範囲へ変更してください。",
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _reject_constant(str(value))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                fail(
                    field=field,
                    invariant="json_object_key_must_be_string",
                    detail="JSON objectのkeyは文字列である必要があります。",
                    next_action="すべてのkeyを文字列へ変更してください。",
                )
            _validate_json_value(key, f"{field}.<key>")
            _validate_json_value(item, f"{field}.{key}")
        return
    fail(
        field=field,
        invariant="value_must_be_json",
        detail=f"JSONへ保存できない値です: {type(value).__name__}",
        next_action="null、bool、数値、文字列、配列、objectのいずれかへ変換してください。",
    )


def parse_json_bytes(content: bytes, *, field: str = "$input") -> Any:
    """重複keyや不正なUTF-8を拒否してJSONを解析する。

    Args:
        content: JSONとして解析するbytes。
        field: エラーで示す入力項目名。

    Returns:
        I-JSONとして保存可能な値。

    Raises:
        ArtifactError: JSONが曖昧または不正な場合。
    """

    if content.startswith(b"\xef\xbb\xbf"):
        fail(
            field=field,
            invariant="json_must_not_have_bom",
            detail="UTF-8 BOM付きJSONは受け付けません。",
            next_action="BOMを削除して再実行してください。",
        )
    try:
        text = content.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_constant,
        )
    except ArtifactError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(
            field=field,
            invariant="input_must_be_valid_utf8_json",
            detail=str(error),
            next_action="UTF-8の正しいJSONへ修正してください。",
        )
    _validate_json_value(value)
    return value


def canonicalize(value: Any) -> bytes:
    """JSON値をRFC 8785 JCSの一意なbytesへ変換する。

    Args:
        value: 直列化するJSON値。

    Returns:
        RFC 8785 JCSに従うUTF-8 bytes。

    Raises:
        ArtifactError: 値をJCSへ変換できない場合。
    """

    _validate_json_value(value)
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, UnicodeError, ValueError) as error:
        fail(
            field="$",
            invariant="value_must_be_jcs_canonicalizable",
            detail=str(error),
            next_action="RFC 8785 JCSで表現可能なJSON値へ修正してください。",
        )


def load_json(path: Path) -> Any:
    """fileを読み取り、厳密なJSONとして解析する。

    Args:
        path: 読み取るJSON file。

    Returns:
        解析済みのJSON値。

    Raises:
        ArtifactError: fileを読めない、またはJSONが不正な場合。
    """

    try:
        content = path.read_bytes()
    except OSError as error:
        fail(
            field=str(path),
            invariant="input_file_must_be_readable",
            detail=str(error),
            next_action="fileの存在と読み取り権限を確認してください。",
        )
    return parse_json_bytes(content, field=str(path))
