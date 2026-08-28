"""初期版の作業記録envelopeと根拠参照だけを検証する。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from . import SCHEMA_VERSION
from .errors import fail

IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z"
)
REQUEST_FIELDS = {
    "record_id",
    "record_type",
    "created_at",
    "references",
    "payload",
}
RECORD_FIELDS = {
    "schema_version",
    "repository_id",
    "run_id",
    "sequence",
    "record_id",
    "record_type",
    "created_at",
    "references",
    "evidence",
    "payload",
}
REFERENCE_FIELDS = {"record_id", "sequence", "content_sha256"}
EVIDENCE_FIELDS = {"label", "content_sha256", "byte_length", "object_path"}
RECORD_TYPES = {
    "input_snapshot",
    "target",
    "target_check",
    "review",
    "change_request",
    "remediation",
    "verification",
    "gate",
    "blind_review",
    "final_review",
    "decision",
}
REQUIRED_EVIDENCE: dict[str, set[str]] = {
    "input_snapshot": {"content"},
    "remediation": {"patch"},
    "verification": {"stderr", "stdout"},
    "gate": {"stderr", "stdout"},
}


def require_identifier(value: Any, *, field: str) -> str:
    """保存先の階層へ安全に使える識別子を返す。

    Args:
        value: 検証する値。
        field: エラーで示す項目名。

    Returns:
        検証済みの識別子。
    """

    if not isinstance(value, str) or IDENTIFIER_PATTERN.fullmatch(value) is None:
        fail(
            field=field,
            invariant="identifier_must_be_path_safe",
            detail="識別子は英数字で始まる128文字以内の英数字、点、下線、hyphenに限定します。",
            next_action="slash、空文字、..を含まない安定した識別子へ変更してください。",
        )
    return value


def require_sha256(value: Any, *, field: str, record_id: str | None = None) -> str:
    """小文字16進数のSHA-256を返す。

    Args:
        value: 検証する値。
        field: エラーで示す項目名。
        record_id: 関連する作業記録ID。

    Returns:
        検証済みのSHA-256。
    """

    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        fail(
            record_id=record_id,
            field=field,
            invariant="sha256_must_be_lowercase_hex",
            detail="SHA-256は64文字の小文字16進数である必要があります。",
            next_action="toolが生成したハッシュを使用してください。",
        )
    return value


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    *,
    field: str,
    record_id: str | None = None,
) -> None:
    missing = sorted(expected - value.keys())
    extra = sorted(value.keys() - expected)
    if missing or extra:
        fail(
            record_id=record_id,
            field=field,
            invariant="object_fields_must_match_schema",
            detail=f"不足項目: {missing}; 未知の項目: {extra}",
            next_action="不足項目を追加し、未知の項目をpayloadへ移してください。",
        )


def _require_rfc3339(value: Any, *, field: str, record_id: str | None = None) -> str:
    if not isinstance(value, str) or RFC3339_PATTERN.fullmatch(value) is None:
        fail(
            record_id=record_id,
            field=field,
            invariant="created_at_must_be_rfc3339",
            detail="日時はtimezone付きRFC 3339文字列である必要があります。",
            next_action="例: 2026-08-28T12:34:56Z の形式へ変更してください。",
        )
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        fail(
            record_id=record_id,
            field=field,
            invariant="created_at_must_be_rfc3339",
            detail=str(error),
            next_action="実在する日付と時刻へ修正してください。",
        )
    return value


def validate_request(value: Any) -> dict[str, Any]:
    """appendへ渡す小さな作業記録要求を検証する。

    Args:
        value: JSONから読み込んだ要求。

    Returns:
        schemaに一致する要求。
    """

    if not isinstance(value, dict):
        fail(
            field="$request",
            invariant="request_must_be_object",
            detail="作業記録要求はJSON objectである必要があります。",
            next_action="top-levelをJSON objectへ変更してください。",
        )
    _require_exact_fields(value, REQUEST_FIELDS, field="$request")
    record_id = require_identifier(value["record_id"], field="record_id")
    record_type = require_identifier(value["record_type"], field="record_type")
    if record_type not in RECORD_TYPES:
        fail(
            record_id=record_id,
            field="record_type",
            invariant="record_type_must_be_known",
            detail=f"未対応の作業記録種別です: {record_type}",
            next_action=f"次のいずれかを使用してください: {sorted(RECORD_TYPES)}",
        )
    _require_rfc3339(value["created_at"], field="created_at", record_id=record_id)
    references = value["references"]
    if not isinstance(references, list):
        fail(
            record_id=record_id,
            field="references",
            invariant="references_must_be_array",
            detail="referencesは作業記録IDの配列である必要があります。",
            next_action="参照がない場合は空配列を使用してください。",
        )
    reference_ids = [
        require_identifier(item, field=f"references[{index}]")
        for index, item in enumerate(references)
    ]
    if len(reference_ids) != len(set(reference_ids)):
        fail(
            record_id=record_id,
            field="references",
            invariant="reference_ids_must_be_unique",
            detail="同じ作業記録を複数回参照しています。",
            next_action="重複した参照を1件にまとめてください。",
        )
    if record_id in reference_ids:
        fail(
            record_id=record_id,
            field="references",
            invariant="record_must_not_reference_itself",
            detail="作業記録は自分自身を参照できません。",
            next_action="自分自身への参照を削除してください。",
        )
    if not isinstance(value["payload"], dict):
        fail(
            record_id=record_id,
            field="payload",
            invariant="payload_must_be_object",
            detail="payloadはJSON objectである必要があります。",
            next_action="工程固有の値をJSON objectへまとめてください。",
        )
    return value


def validate_record(value: Any) -> dict[str, Any]:
    """保存済み作業記録のenvelopeと根拠項目を検証する。

    状態遷移やREADY条件など、工程の意味は判断しない。

    Args:
        value: 保存済みJSONから読み込んだ値。

    Returns:
        初期版schemaに一致する作業記録。
    """

    if not isinstance(value, dict):
        fail(
            field="$record",
            invariant="record_must_be_object",
            detail="保存済み作業記録はJSON objectである必要があります。",
            next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
        )
    record_id_value = value.get("record_id")
    record_id = record_id_value if isinstance(record_id_value, str) else None
    _require_exact_fields(value, RECORD_FIELDS, field="$record", record_id=record_id)
    if value["schema_version"] != SCHEMA_VERSION:
        fail(
            record_id=record_id,
            field="schema_version",
            invariant="schema_version_must_be_supported",
            detail=f"対応版は{SCHEMA_VERSION}です: {value['schema_version']}",
            next_action="対応するtool版で検証するか、新しいrunを開始してください。",
        )
    require_identifier(value["repository_id"], field="repository_id")
    require_identifier(value["run_id"], field="run_id")
    checked_id = require_identifier(value["record_id"], field="record_id")
    record_type = require_identifier(value["record_type"], field="record_type")
    if record_type not in RECORD_TYPES:
        fail(
            record_id=checked_id,
            field="record_type",
            invariant="record_type_must_be_known",
            detail=f"未対応の作業記録種別です: {record_type}",
            next_action="対応するtool版で検証するか、新しいrunを開始してください。",
        )
    sequence = value["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        fail(
            record_id=checked_id,
            field="sequence",
            invariant="sequence_must_be_non_negative_integer",
            detail="通し番号は0以上の整数である必要があります。",
            next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
        )
    _require_rfc3339(value["created_at"], field="created_at", record_id=checked_id)
    if not isinstance(value["payload"], dict):
        fail(
            record_id=checked_id,
            field="payload",
            invariant="payload_must_be_object",
            detail="payloadはJSON objectである必要があります。",
            next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
        )
    _validate_references(value["references"], checked_id)
    _validate_evidence(value["evidence"], record_type, checked_id)
    return value


def _validate_references(value: Any, record_id: str) -> None:
    if not isinstance(value, list):
        fail(
            record_id=record_id,
            field="references",
            invariant="references_must_be_array",
            detail="referencesは配列である必要があります。",
            next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
        )
    ids: list[str] = []
    for index, reference in enumerate(value):
        field = f"references[{index}]"
        if not isinstance(reference, dict):
            fail(
                record_id=record_id,
                field=field,
                invariant="reference_must_be_object",
                detail="参照はID、通し番号、内容ハッシュを持つobjectである必要があります。",
                next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
            )
        _require_exact_fields(
            reference, REFERENCE_FIELDS, field=field, record_id=record_id
        )
        ids.append(
            require_identifier(reference["record_id"], field=f"{field}.record_id")
        )
        sequence = reference["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            fail(
                record_id=record_id,
                field=f"{field}.sequence",
                invariant="reference_sequence_must_be_non_negative_integer",
                detail="参照先の通し番号は0以上の整数である必要があります。",
                next_action="toolが生成した参照を使用してください。",
            )
        require_sha256(
            reference["content_sha256"],
            field=f"{field}.content_sha256",
            record_id=record_id,
        )
    if ids != sorted(set(ids), key=lambda item: item.encode("utf-8")):
        fail(
            record_id=record_id,
            field="references",
            invariant="references_must_be_sorted_and_unique",
            detail="参照はrecord_idのUTF-8順で重複なく保存する必要があります。",
            next_action="toolが生成した参照を使用してください。",
        )


def _validate_evidence(value: Any, record_type: str, record_id: str) -> None:
    if not isinstance(value, list):
        fail(
            record_id=record_id,
            field="evidence",
            invariant="evidence_must_be_array",
            detail="evidenceは根拠参照の配列である必要があります。",
            next_action="根拠がない場合は空配列を使用してください。",
        )
    labels: list[str] = []
    for index, evidence in enumerate(value):
        field = f"evidence[{index}]"
        if not isinstance(evidence, dict):
            fail(
                record_id=record_id,
                field=field,
                invariant="evidence_ref_must_be_object",
                detail="根拠参照はlabel、hash、長さ、保存先を持つobjectである必要があります。",
                next_action="toolが生成した根拠参照を使用してください。",
            )
        _require_exact_fields(
            evidence, EVIDENCE_FIELDS, field=field, record_id=record_id
        )
        label = require_identifier(evidence["label"], field=f"{field}.label")
        labels.append(label)
        content_hash = require_sha256(
            evidence["content_sha256"],
            field=f"{field}.content_sha256",
            record_id=record_id,
        )
        length = evidence["byte_length"]
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            fail(
                record_id=record_id,
                field=f"{field}.byte_length",
                invariant="evidence_length_must_be_non_negative_integer",
                detail="根拠の長さは0以上の整数である必要があります。",
                next_action="toolが計算した長さを使用してください。",
            )
        expected_path = f"objects/sha256/{content_hash}"
        if evidence["object_path"] != expected_path:
            fail(
                record_id=record_id,
                field=f"{field}.object_path",
                invariant="evidence_path_must_match_hash",
                detail=f"根拠の保存先は{expected_path}である必要があります。",
                next_action="toolが生成した保存先を使用してください。",
            )
    if labels != sorted(set(labels), key=lambda item: item.encode("utf-8")):
        fail(
            record_id=record_id,
            field="evidence",
            invariant="evidence_labels_must_be_sorted_and_unique",
            detail="根拠labelはUTF-8順で重複なく保存する必要があります。",
            next_action="toolが生成した根拠参照を使用してください。",
        )
    missing = sorted(REQUIRED_EVIDENCE.get(record_type, set()) - set(labels))
    if missing:
        fail(
            record_id=record_id,
            field="evidence",
            invariant="required_evidence_must_be_present",
            detail=f"{record_type}に必要な根拠が不足しています: {missing}",
            next_action="不足した根拠fileを--evidenceで指定してください。",
        )
