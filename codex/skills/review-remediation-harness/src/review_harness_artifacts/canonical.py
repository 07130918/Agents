"""Strict JSON parsing, RFC 8785 serialization, and content hashing."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import rfc8785

from .errors import ArtifactError, fail

MAX_IJSON_INTEGER = 9_007_199_254_740_991
SHA256_HEX_LENGTH = 64


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reject_constant(value: str) -> None:
    fail(
        artifact_id=None,
        field="$",
        invariant="json_number_must_be_finite",
        detail=f"Non-finite JSON number is not allowed: {value}",
    )


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(
                artifact_id=None,
                field=f"$.{key}",
                invariant="json_object_keys_must_be_unique",
                detail=f"Duplicate object key: {key}",
            )
        result[key] = value
    return result


def _validate_json_value(value: Any, field: str = "$") -> None:
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str):
            for character in value:
                codepoint = ord(character)
                if 0xD800 <= codepoint <= 0xDFFF:
                    fail(
                        artifact_id=None,
                        field=field,
                        invariant="json_string_must_not_contain_lone_surrogate",
                        detail="Lone Unicode surrogate is not valid I-JSON",
                    )
        return
    if isinstance(value, int):
        if abs(value) > MAX_IJSON_INTEGER:
            fail(
                artifact_id=None,
                field=field,
                invariant="json_integer_must_be_ijson_exact",
                detail=f"Integer is outside the exact I-JSON range: {value}",
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            fail(
                artifact_id=None,
                field=field,
                invariant="json_number_must_be_finite",
                detail="NaN and Infinity are not valid I-JSON numbers",
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                fail(
                    artifact_id=None,
                    field=field,
                    invariant="json_object_key_must_be_string",
                    detail="JSON object keys must be strings",
                )
            _validate_json_value(key, f"{field}.<key>")
            _validate_json_value(item, f"{field}.{key}")
        return
    fail(
        artifact_id=None,
        field=field,
        invariant="value_must_be_json",
        detail=f"Unsupported JSON value type: {type(value).__name__}",
    )


def parse_json_bytes(content: bytes, *, field: str = "$") -> Any:
    """Parse JSON without losing duplicate keys or accepting non-I-JSON values."""

    if content.startswith(b"\xef\xbb\xbf"):
        fail(
            artifact_id=None,
            field=field,
            invariant="json_must_not_have_bom",
            detail="UTF-8 BOM is not allowed",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ArtifactError(
            artifact_id=None,
            field=field,
            invariant="json_must_be_utf8",
            detail=str(error),
        ) from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_constant,
        )
    except ArtifactError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ArtifactError(
            artifact_id=None,
            field=field,
            invariant="json_must_parse",
            detail=str(error),
        ) from error
    _validate_json_value(value, field)
    return value


def load_json(path: Path) -> Any:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ArtifactError(
            artifact_id=None,
            field=str(path),
            invariant="input_file_must_be_readable",
            detail=str(error),
        ) from error
    return parse_json_bytes(content, field=str(path))


def canonicalize(value: Any) -> bytes:
    _validate_json_value(value)
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, UnicodeError, ValueError) as error:
        raise ArtifactError(
            artifact_id=None,
            field="$",
            invariant="value_must_be_rfc8785_canonicalizable",
            detail=str(error),
        ) from error


def require_canonical_json(content: bytes, *, field: str) -> Any:
    value = parse_json_bytes(content, field=field)
    canonical = canonicalize(value)
    if content != canonical:
        fail(
            artifact_id=value.get("artifact_id") if isinstance(value, dict) else None,
            field=field,
            invariant="stored_json_must_be_exact_jcs",
            detail="Stored bytes differ from RFC 8785 canonical bytes",
        )
    return value


def decode_base64(value: str, *, field: str, artifact_id: str | None = None) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ArtifactError(
            artifact_id=artifact_id,
            field=field,
            invariant="content_base64_must_be_canonical_base64",
            detail=str(error),
        ) from error
    if base64.b64encode(decoded).decode("ascii") != value:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="content_base64_must_be_canonical_base64",
            detail="Base64 spelling has non-canonical padding bits or form",
        )
    return decoded


def encode_base64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def object_path(content_hash: str) -> str:
    if len(content_hash) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in content_hash
    ):
        fail(
            artifact_id=None,
            field="sha256",
            invariant="sha256_must_be_lowercase_hex_64",
            detail=f"Invalid SHA-256 value: {content_hash}",
        )
    return f"objects/sha256/{content_hash[:2]}/{content_hash[2:]}"


def manifest_path(revision: int) -> str:
    if not isinstance(revision, int) or isinstance(revision, bool):
        fail(
            artifact_id=None,
            field="payload.revision",
            invariant="manifest_revision_must_be_integer",
            detail="Manifest revision must be an integer",
        )
    if not 0 <= revision <= MAX_IJSON_INTEGER:
        fail(
            artifact_id=None,
            field="payload.revision",
            invariant="manifest_revision_must_be_ijson_exact",
            detail=f"Manifest revision is outside the supported range: {revision}",
        )
    return f"manifests/{revision}.json"


def git_blob_oid(content: bytes, object_format: str) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    if object_format == "sha1":
        return hashlib.sha1(header + content).hexdigest()
    if object_format == "sha256":
        return hashlib.sha256(header + content).hexdigest()
    fail(
        artifact_id=None,
        field="git_object_format",
        invariant="git_object_format_must_be_supported",
        detail=f"Unsupported Git object format: {object_format}",
    )
    raise AssertionError("unreachable")
