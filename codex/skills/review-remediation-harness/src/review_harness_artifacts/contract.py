"""形式2.0の作業記録と記録間の契約を、副作用を起こさず検証する。"""

from __future__ import annotations

import datetime as dt
import posixpath
import re
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from . import SCHEMA_VERSION
from .canonical import (
    MAX_IJSON_INTEGER,
    canonicalize,
    manifest_path,
    object_path,
    sha256_hex,
)
from .errors import fail

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
REPOSITORY_ID_PATTERN = re.compile(r"sha256-[0-9a-f]{64}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
GIT_OID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
PATH_SEGMENT_PATTERN = ID_PATTERN
RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z"
)

NORMAL_STATES = {
    "CONTEXT_RESOLVING",
    "REVIEW_PENDING",
    "CHANGES_REQUESTED",
    "FIXING",
    "VERIFYING",
    "PRECOMMIT_DOCS_PENDING",
    "CANDIDATE_COMMIT_PENDING",
    "TARGET_VERIFYING",
    "GATES_PENDING",
    "REREVIEW_PENDING",
}
BLOCKER_STATES = {
    "EVALUATION_DEFERRED",
    "VERIFICATION_BLOCKED",
    "SCOPE_CHANGE_REQUIRED",
    "HUMAN_DECISION_REQUIRED",
    "INDEPENDENCE_BLOCKED",
    "BUDGET_EXHAUSTED",
}
ALL_STATES = NORMAL_STATES | BLOCKER_STATES | {"READY"}

ARTIFACT_TYPES = {
    "input_snapshot",
    "target",
    "evidence",
    "target_check",
    "review",
    "change_request",
    "remediation",
    "verification",
    "gate",
    "blind_review",
    "final_review",
    "decision",
    "run_manifest",
}
ROOT_TYPES = {"input_snapshot", "target"}
EVIDENCE_TYPES = {"evidence"}
STAGE_TYPES = ARTIFACT_TYPES - ROOT_TYPES - EVIDENCE_TYPES - {"run_manifest"}

ARTIFACT_ALLOWED_STAGES: dict[str, set[str]] = {
    "input_snapshot": ALL_STATES - {"READY"},
    "target": ALL_STATES - {"READY"},
    "evidence": ALL_STATES - {"READY"},
    "target_check": NORMAL_STATES,
    "review": {"REVIEW_PENDING"},
    "change_request": {"CHANGES_REQUESTED"},
    "remediation": {"FIXING"},
    "verification": {"VERIFYING", "TARGET_VERIFYING"},
    "gate": {"PRECOMMIT_DOCS_PENDING", "GATES_PENDING"},
    "blind_review": {"REREVIEW_PENDING"},
    "final_review": {"REREVIEW_PENDING"},
    "decision": ALL_STATES - {"READY"},
    "run_manifest": ALL_STATES,
}

COMMAND_EFFECT_ORDER = [
    "repository_read",
    "local_write",
    "repository_write",
    "external_read",
    "external_write",
]

MANIFEST_LIMIT_FIELDS = {
    "max_remediation_cycles",
    "max_same_request_attempts",
    "max_transient_stage_retries",
    "deadline_at",
    "token_budget",
    "paid_external_call_budget",
    "allowed_write_paths",
    "max_changed_files",
    "max_diff_lines",
}
MANIFEST_COUNTER_FIELDS = {
    "remediation_cycles_started",
    "remediation_attempts_by_request_id",
    "transient_retries_by_execution_key",
    "tokens_used",
    "paid_external_calls",
}
LIMIT_EVENTS = {
    "hard_exceeded",
    "next_reservation_rejected",
    "next_attempt_rejected",
}

PRODUCER_ROLES = {
    "orchestrator",
    "initial_reviewer",
    "project_reviewer",
    "implementer",
    "tester",
    "final_reviewer",
    "docs_gate",
    "security_gate",
    "ci",
    "human",
}

INPUT_KINDS = {
    "repository_identity",
    "prior_run_handoff",
    "project_rule",
    "acceptance_policy",
    "issue_bundle",
    "external_record",
    "personal_contract",
    "required_capability",
    "human_approved_run_local",
    "explicit_scope",
    "permission_set",
}
TRUST_SOURCES = {
    "runtime_observed",
    "personal_contract",
    "base",
    "human_approved_run_local",
    "external_authoritative",
    "external_observed",
}

PAYLOAD_REQUIRED_FIELDS: dict[str, set[str]] = {
    "target_check": {
        "expected_target_ref",
        "observed_target_status",
        "observed_target_ref",
        "observed_target_absence_reason",
        "expected_input_refs",
        "observed_input_refs",
        "expected_permission_set_ref",
        "observed_permission_set_ref",
        "expected_contract_ref",
        "observed_contract_ref",
        "expected_project_rule_refs",
        "observed_project_rule_refs",
        "status",
        "transition_kinds",
        "observed_components",
        "changed_components",
        "unresolved_components",
        "observation_evidence_refs",
        "transition_diff_ref",
        "checked_at",
    },
    "evidence": {
        "evidence_kind",
        "media_type",
        "content_sha256",
        "completeness",
        "redactions",
        "truncation",
    },
    "review": {
        "popr_result",
        "generic_risk_result",
        "generic_coverage_status",
        "project_results",
        "project_coverage_status",
        "blocking_finding_ids",
        "required_gates",
        "coverage_status",
    },
    "change_request": {"requests"},
    "remediation": {
        "request_id",
        "decision",
        "minimal_change",
        "planned_paths",
        "changed_paths",
        "patch_ref",
        "test_plan",
        "scope_effect",
    },
    "verification": {
        "commands",
        "status",
        "unverified_reason",
        "mutated_target",
        "mutation_patch_ref",
    },
    "gate": {
        "gate_name",
        "declared_version",
        "capability_revision",
        "content_sha256",
        "execution_status",
        "decision_status",
        "decision_policy",
        "acceptance_policy_ref",
        "evidence_ref",
        "pre_target_check_ref",
        "post_target_check_ref",
        "mutated_target",
    },
    "blind_review": {
        "blind_result",
        "generic_risk_result",
        "generic_coverage_status",
        "blind_received_artifacts",
        "project_results",
        "project_coverage_status",
        "required_gates",
        "independence_check",
    },
    "final_review": {
        "blind_review_ref",
        "reconciliation",
        "popr_result",
        "blocking_finding_ids",
        "previous_review_ref",
        "remediation_status",
        "remediation_refs",
        "independence_check",
    },
    "decision": {"decision_kind"},
}

ALLOWED_STATE_TRANSITIONS: dict[str, set[str]] = {
    "CONTEXT_RESOLVING": {
        "REVIEW_PENDING",
        "EVALUATION_DEFERRED",
        "HUMAN_DECISION_REQUIRED",
        "BUDGET_EXHAUSTED",
    },
    "REVIEW_PENDING": {
        "CHANGES_REQUESTED",
        "VERIFYING",
        "EVALUATION_DEFERRED",
        "HUMAN_DECISION_REQUIRED",
        "BUDGET_EXHAUSTED",
    },
    "CHANGES_REQUESTED": {
        "FIXING",
        "SCOPE_CHANGE_REQUIRED",
        "HUMAN_DECISION_REQUIRED",
        "BUDGET_EXHAUSTED",
    },
    "FIXING": {"VERIFYING", "HUMAN_DECISION_REQUIRED", "BUDGET_EXHAUSTED"},
    "VERIFYING": {
        "VERIFYING",
        "PRECOMMIT_DOCS_PENDING",
        "CHANGES_REQUESTED",
        "EVALUATION_DEFERRED",
        "VERIFICATION_BLOCKED",
        "BUDGET_EXHAUSTED",
    },
    "PRECOMMIT_DOCS_PENDING": {
        "CANDIDATE_COMMIT_PENDING",
        "VERIFYING",
        "CONTEXT_RESOLVING",
        "HUMAN_DECISION_REQUIRED",
        "EVALUATION_DEFERRED",
        "BUDGET_EXHAUSTED",
    },
    "CANDIDATE_COMMIT_PENDING": {
        "TARGET_VERIFYING",
        "HUMAN_DECISION_REQUIRED",
        "EVALUATION_DEFERRED",
        "BUDGET_EXHAUSTED",
    },
    "TARGET_VERIFYING": {
        "GATES_PENDING",
        "CANDIDATE_COMMIT_PENDING",
        "CONTEXT_RESOLVING",
        "CHANGES_REQUESTED",
        "EVALUATION_DEFERRED",
        "VERIFICATION_BLOCKED",
        "BUDGET_EXHAUSTED",
    },
    "GATES_PENDING": {
        "CANDIDATE_COMMIT_PENDING",
        "CONTEXT_RESOLVING",
        "REREVIEW_PENDING",
        "CHANGES_REQUESTED",
        "HUMAN_DECISION_REQUIRED",
        "EVALUATION_DEFERRED",
        "BUDGET_EXHAUSTED",
    },
    "REREVIEW_PENDING": {
        "READY",
        "GATES_PENDING",
        "CONTEXT_RESOLVING",
        "CHANGES_REQUESTED",
        "INDEPENDENCE_BLOCKED",
        "EVALUATION_DEFERRED",
        "HUMAN_DECISION_REQUIRED",
        "BUDGET_EXHAUSTED",
    },
    "EVALUATION_DEFERRED": {"CONTEXT_RESOLVING"},
    "VERIFICATION_BLOCKED": {"VERIFYING", "TARGET_VERIFYING"},
    "SCOPE_CHANGE_REQUIRED": {"CONTEXT_RESOLVING"},
    "HUMAN_DECISION_REQUIRED": {"CONTEXT_RESOLVING"},
    "INDEPENDENCE_BLOCKED": {"REREVIEW_PENDING"},
    "READY": set(),
    "BUDGET_EXHAUSTED": set(),
}

BLOCKER_RULES: dict[str, tuple[set[str], set[str | None]]] = {
    "EVALUATION_DEFERRED": (
        {
            "target_unresolved",
            "context_unresolved",
            "capability_unavailable",
            "coverage_incomplete",
            "gate_unavailable",
            "artifact_invalid",
            "input_revalidation_failed",
            "external_write_unsupported",
        },
        {"CONTEXT_RESOLVING"},
    ),
    "VERIFICATION_BLOCKED": (
        {
            "environment_unavailable",
            "permission_unavailable",
            "required_service_unavailable",
        },
        {"VERIFYING", "TARGET_VERIFYING"},
    ),
    "SCOPE_CHANGE_REQUIRED": ({"scope_expansion"}, {"CONTEXT_RESOLVING"}),
    "HUMAN_DECISION_REQUIRED": (
        {
            "specification_ambiguous",
            "risk_acceptance_required",
            "authority_pending",
            "permission_decision_required",
            "side_effect_decision_required",
        },
        {"CONTEXT_RESOLVING"},
    ),
    "INDEPENDENCE_BLOCKED": (
        {"fresh_reviewer_unavailable", "independence_unverifiable"},
        {"REREVIEW_PENDING"},
    ),
    "BUDGET_EXHAUSTED": (
        {
            "deadline_exhausted",
            "token_budget_exhausted",
            "paid_call_budget_exhausted",
            "remediation_cycle_exhausted",
            "same_request_attempt_exhausted",
            "transient_retry_exhausted",
            "diff_limit_exhausted",
        },
        {None},
    ),
}

BLOCKER_ACTIONS: dict[str, tuple[str, str]] = {
    "EVALUATION_DEFERRED": (
        "provide_or_restore_required_input_or_capability",
        "revalidate_context_and_target",
    ),
    "VERIFICATION_BLOCKED": (
        "restore_verification_environment_or_permission",
        "revalidate_same_permission_and_environment",
    ),
    "SCOPE_CHANGE_REQUIRED": (
        "approve_scope_change_or_split_issue",
        "record_scope_decision_and_revalidate_context",
    ),
    "HUMAN_DECISION_REQUIRED": (
        "record_spec_risk_or_permission_decision",
        "record_human_decision_and_revalidate_context",
    ),
    "INDEPENDENCE_BLOCKED": (
        "provide_fresh_reviewer",
        "record_fresh_reviewer_identity",
    ),
    "BUDGET_EXHAUSTED": (
        "start_new_run",
        "new_run_with_prior_run_handoff",
    ),
}

TRANSITION_KIND_ORDER = [
    "target_changed",
    "governing_input_changed",
    "permission_changed",
    "contract_changed",
    "project_rule_changed",
    "scope_changed",
    "external_revision_changed",
    "unresolved",
]

REMEDIATION_DECISIONS = {
    "fix",
    "defer_minor",
    "not_applicable",
    "human_decision",
}
READY_GATE_SUCCESS_STATUSES = {"PASS", "UPDATED"}


def require_dict(value: Any, *, artifact_id: str | None, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="field_must_be_object",
            detail=f"Expected object, got {type(value).__name__}",
        )
    return value


def require_list(value: Any, *, artifact_id: str | None, field: str) -> list[Any]:
    if not isinstance(value, list):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="field_must_be_array",
            detail=f"Expected array, got {type(value).__name__}",
        )
    return value


def require_string(
    value: Any,
    *,
    artifact_id: str | None,
    field: str,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="field_must_be_nonempty_string"
            if not allow_empty
            else "field_must_be_string",
            detail=f"Expected {'non-empty ' if not allow_empty else ''}string",
        )
    return value


def require_bool(value: Any, *, artifact_id: str | None, field: str) -> bool:
    if not isinstance(value, bool):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="field_must_be_boolean",
            detail=f"Expected boolean, got {type(value).__name__}",
        )
    return value


def require_integer(
    value: Any,
    *,
    artifact_id: str | None,
    field: str,
    minimum: int = 0,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="field_must_be_integer",
            detail=f"Expected integer, got {type(value).__name__}",
        )
    if not minimum <= value <= MAX_IJSON_INTEGER:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="integer_must_be_ijson_exact_and_in_range",
            detail=f"Expected {minimum}..{MAX_IJSON_INTEGER}, got {value}",
        )
    return value


def require_fields(
    value: Mapping[str, Any],
    required: Iterable[str],
    *,
    artifact_id: str | None,
    field: str,
) -> None:
    missing = sorted(set(required) - value.keys())
    if missing:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="required_fields_must_exist",
            detail=f"Missing required fields: {', '.join(missing)}",
        )


def require_exact_fields(
    value: Mapping[str, Any],
    allowed: Iterable[str],
    *,
    artifact_id: str | None,
    field: str,
) -> None:
    allowed_set = set(allowed)
    require_fields(value, allowed_set, artifact_id=artifact_id, field=field)
    unknown = sorted(value.keys() - allowed_set)
    if unknown:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="unknown_fields_must_be_rejected",
            detail=f"Unknown fields: {', '.join(unknown)}",
        )


def validate_identifier(
    value: Any, *, field: str, artifact_id: str | None = None
) -> str:
    text = require_string(value, artifact_id=artifact_id, field=field)
    if ID_PATTERN.fullmatch(text) is None:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="identifier_must_match_grammar",
            detail=f"Invalid identifier: {text}",
        )
    return text


def validate_repository_id(value: Any, *, field: str = "repository_id") -> str:
    text = require_string(value, artifact_id=None, field=field)
    if REPOSITORY_ID_PATTERN.fullmatch(text) is None:
        fail(
            artifact_id=None,
            field=field,
            invariant="repository_id_must_be_sha256_identifier",
            detail=f"Invalid repository ID: {text}",
        )
    return text


def validate_hash(value: Any, *, artifact_id: str | None, field: str) -> str:
    text = require_string(value, artifact_id=artifact_id, field=field)
    if HASH_PATTERN.fullmatch(text) is None:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="sha256_must_be_lowercase_hex_64",
            detail=f"Invalid SHA-256: {text}",
        )
    return text


def validate_run_relative_path(
    value: Any,
    *,
    artifact_id: str | None,
    field: str,
) -> str:
    text = require_string(value, artifact_id=artifact_id, field=field)
    if "\\" in text or "\x00" in text or text.startswith("/"):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="run_store_path_must_be_safe_relative_path",
            detail=f"Unsafe run-store path: {text!r}",
        )
    segments = text.split("/")
    if any(
        not segment
        or segment in {".", ".."}
        or PATH_SEGMENT_PATTERN.fullmatch(segment) is None
        for segment in segments
    ):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="run_store_path_segments_must_match_grammar",
            detail=f"Invalid run-store path: {text!r}",
        )
    return text


def validate_repository_path(
    value: Any,
    *,
    artifact_id: str | None,
    field: str,
) -> str:
    text = require_string(value, artifact_id=artifact_id, field=field)
    if text.startswith("/") or "\\" in text or "\x00" in text:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="repository_path_must_be_safe_relative_path",
            detail=f"Unsafe repository path: {text!r}",
        )
    segments = text.split("/")
    if any(not segment or segment in {".", ".."} for segment in segments):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="repository_path_must_not_contain_dot_segments",
            detail=f"Invalid repository path: {text!r}",
        )
    return text


def validate_rfc3339(value: Any, *, artifact_id: str | None, field: str) -> str:
    text = require_string(value, artifact_id=artifact_id, field=field)
    if RFC3339_PATTERN.fullmatch(text) is None:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="timestamp_must_be_rfc3339",
            detail=f"Invalid RFC 3339 timestamp: {text}",
        )
    try:
        dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="timestamp_must_be_rfc3339",
            detail=str(error),
        )
    return text


def validate_common_ref(
    value: Any,
    *,
    field: str,
    run_id: str | None = None,
    containing_artifact_id: str | None = None,
) -> dict[str, Any]:
    """作業記録への共通参照が正しい形式か検証する。

    Args:
        value: 検証する参照値。
        field: エラー時に報告するフィールド名。
        run_id: 参照先に要求する実行ID。指定しない場合は照合しない。
        containing_artifact_id: この参照を含む作業記録ID。

    Returns:
        検証済みの共通参照。

    Raises:
        ArtifactError: 参照の形式、実行ID、パス、またはハッシュが不正な場合。
    """
    ref = require_dict(value, artifact_id=containing_artifact_id, field=field)
    require_exact_fields(
        ref,
        {"artifact_id", "artifact_path", "sha256"},
        artifact_id=containing_artifact_id,
        field=field,
    )
    ref_id = require_string(
        ref["artifact_id"],
        artifact_id=containing_artifact_id,
        field=f"{field}.artifact_id",
    )
    parts = ref_id.split("/")
    if len(parts) != 3:
        fail(
            artifact_id=containing_artifact_id,
            field=f"{field}.artifact_id",
            invariant="artifact_id_must_have_run_state_sequence",
            detail=f"Invalid artifact ID: {ref_id}",
        )
    validate_identifier(
        parts[0],
        field=f"{field}.artifact_id.run_id",
        artifact_id=containing_artifact_id,
    )
    if run_id is not None and parts[0] != run_id:
        fail(
            artifact_id=containing_artifact_id,
            field=f"{field}.artifact_id",
            invariant="artifact_ref_must_stay_in_same_run",
            detail=f"Reference run {parts[0]} differs from {run_id}",
        )
    if parts[1] not in ALL_STATES:
        fail(
            artifact_id=containing_artifact_id,
            field=f"{field}.artifact_id",
            invariant="artifact_id_state_must_be_known",
            detail=f"Unknown state in artifact ID: {parts[1]}",
        )
    if not parts[2].isdigit() or (parts[2].startswith("0") and parts[2] != "0"):
        fail(
            artifact_id=containing_artifact_id,
            field=f"{field}.artifact_id",
            invariant="artifact_id_sequence_must_be_canonical_decimal",
            detail=f"Invalid sequence in artifact ID: {parts[2]}",
        )
    require_integer(
        int(parts[2]),
        artifact_id=containing_artifact_id,
        field=f"{field}.artifact_id.sequence",
    )
    validate_run_relative_path(
        ref["artifact_path"],
        artifact_id=containing_artifact_id,
        field=f"{field}.artifact_path",
    )
    validate_hash(
        ref["sha256"], artifact_id=containing_artifact_id, field=f"{field}.sha256"
    )
    return ref


def validate_ref_array(
    value: Any,
    *,
    field: str,
    run_id: str,
    containing_artifact_id: str | None,
    allow_empty: bool = True,
) -> list[dict[str, Any]]:
    """共通参照の配列を検証し、ID順かつ重複なしであることを確認する。

    Args:
        value: 検証する参照配列。
        field: エラー時に報告するフィールド名。
        run_id: すべての参照先に要求する実行ID。
        containing_artifact_id: この配列を含む作業記録ID。
        allow_empty: 空配列を許可するかどうか。

    Returns:
        検証済みの共通参照一覧。

    Raises:
        ArtifactError: 配列の形式、並び順、重複、または参照内容が不正な場合。
    """
    values = require_list(value, artifact_id=containing_artifact_id, field=field)
    if not allow_empty and not values:
        fail(
            artifact_id=containing_artifact_id,
            field=field,
            invariant="reference_array_must_not_be_empty",
            detail="At least one reference is required",
        )
    refs = [
        validate_common_ref(
            item,
            field=f"{field}[{index}]",
            run_id=run_id,
            containing_artifact_id=containing_artifact_id,
        )
        for index, item in enumerate(values)
    ]
    ids = [ref["artifact_id"] for ref in refs]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        fail(
            artifact_id=containing_artifact_id,
            field=field,
            invariant="reference_array_must_be_sorted_and_unique",
            detail="References must be unique and sorted by artifact_id",
        )
    return refs


def _validate_producer(value: Any, *, artifact_id: str, run_id: str) -> None:
    producer = require_dict(value, artifact_id=artifact_id, field="producer")
    required = {
        "role",
        "instance_id",
        "context_id",
        "parent_context_id",
        "fresh_context",
        "model",
        "received_artifacts",
    }
    require_fields(producer, required, artifact_id=artifact_id, field="producer")
    allowed = required | {"model_unavailable_reason"}
    unknown = sorted(producer.keys() - allowed)
    if unknown:
        fail(
            artifact_id=artifact_id,
            field="producer",
            invariant="unknown_fields_must_be_rejected",
            detail=f"Unknown producer fields: {', '.join(unknown)}",
        )
    if producer["role"] not in PRODUCER_ROLES:
        fail(
            artifact_id=artifact_id,
            field="producer.role",
            invariant="producer_role_must_be_known",
            detail=f"Unknown producer role: {producer['role']}",
        )
    require_string(
        producer["instance_id"], artifact_id=artifact_id, field="producer.instance_id"
    )
    require_string(
        producer["context_id"], artifact_id=artifact_id, field="producer.context_id"
    )
    parent = producer["parent_context_id"]
    if parent is not None:
        require_string(
            parent, artifact_id=artifact_id, field="producer.parent_context_id"
        )
    require_bool(
        producer["fresh_context"],
        artifact_id=artifact_id,
        field="producer.fresh_context",
    )
    if producer["model"] is None:
        require_string(
            producer.get("model_unavailable_reason"),
            artifact_id=artifact_id,
            field="producer.model_unavailable_reason",
        )
    else:
        require_string(
            producer["model"], artifact_id=artifact_id, field="producer.model"
        )
    validate_ref_array(
        producer["received_artifacts"],
        field="producer.received_artifacts",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )


def _validate_input_snapshot(payload: dict[str, Any], *, artifact_id: str) -> None:
    """外部入力の保存内容と信頼元に応じた必須項目を検証する。

    Args:
        payload: 入力保存記録の本体。
        artifact_id: エラーに含める作業記録ID。

    Raises:
        ArtifactError: 入力種別、信頼元、内容、ハッシュ、または由来情報が不正な場合。
    """
    required = {
        "input_kind",
        "trust_source",
        "source_identifier",
        "source_sha",
        "source_object_id",
        "source_revision",
        "content_format",
        "content_sha256",
        "content",
    }
    require_fields(payload, required, artifact_id=artifact_id, field="payload")
    input_kind = require_string(
        payload["input_kind"], artifact_id=artifact_id, field="payload.input_kind"
    )
    if input_kind not in INPUT_KINDS:
        fail(
            artifact_id=artifact_id,
            field="payload.input_kind",
            invariant="input_kind_must_be_known",
            detail=f"Unknown input kind: {input_kind}",
        )
    trust_source = require_string(
        payload["trust_source"],
        artifact_id=artifact_id,
        field="payload.trust_source",
    )
    if trust_source not in TRUST_SOURCES:
        fail(
            artifact_id=artifact_id,
            field="payload.trust_source",
            invariant="trust_source_must_be_known",
            detail=f"Unknown trust source: {trust_source}",
        )
    require_string(
        payload["source_identifier"],
        artifact_id=artifact_id,
        field="payload.source_identifier",
    )
    for field_name in ("source_sha", "source_object_id", "source_revision"):
        field_value = payload[field_name]
        if field_value is not None:
            require_string(
                field_value, artifact_id=artifact_id, field=f"payload.{field_name}"
            )
    if input_kind in {"repository_identity", "prior_run_handoff"}:
        if payload["source_sha"] is not None or payload["source_object_id"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="runtime_input_locator_must_use_revision_only",
                detail="Runtime-observed inputs require null source_sha and source_object_id",
            )
        expected_revision_prefix = "sha256:"
    elif input_kind in {"project_rule", "acceptance_policy"}:
        if (
            payload["source_sha"] is None
            or payload["source_object_id"] is None
            or payload["source_revision"] is not None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="base_input_locator_must_use_git_sha_and_object_id",
                detail="Base inputs require source_sha/source_object_id and null source_revision",
            )
        for field_name in ("source_sha", "source_object_id"):
            object_id = payload[field_name]
            if (
                not isinstance(object_id, str)
                or GIT_OID_PATTERN.fullmatch(object_id) is None
            ):
                fail(
                    artifact_id=artifact_id,
                    field=f"payload.{field_name}",
                    invariant="base_input_git_object_id_must_be_lowercase_hex",
                    detail="Base input Git identifiers must be 40 or 64 lowercase hex characters",
                )
        expected_revision_prefix = None
    elif input_kind in {"issue_bundle", "external_record"}:
        if payload["source_sha"] is not None or payload["source_object_id"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="external_input_locator_must_use_revision_only",
                detail="External inputs require null source_sha and source_object_id",
            )
        expected_revision_prefix = ""
    elif input_kind in {"personal_contract", "required_capability"}:
        if payload["source_sha"] is not None or payload["source_object_id"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="capability_input_locator_must_use_revision_only",
                detail="Capability inputs require null source_sha and source_object_id",
            )
        revision = payload["source_revision"]
        if not isinstance(revision, str) or not revision.startswith(
            ("version:", "sha256:")
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.source_revision",
                invariant="capability_revision_must_be_version_or_sha256",
                detail="Expected version:<value> or sha256:<hash>",
            )
        expected_revision_prefix = None
    elif input_kind in {"human_approved_run_local", "explicit_scope"}:
        if payload["source_sha"] is not None or payload["source_object_id"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="human_input_locator_must_use_approval_revision",
                detail="Human inputs require null source_sha and source_object_id",
            )
        expected_revision_prefix = "approval:"
    else:
        if payload["source_sha"] is not None or payload["source_object_id"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="permission_input_locator_must_use_revision_only",
                detail="Permission inputs require null source_sha and source_object_id",
            )
        revision = payload["source_revision"]
        if not isinstance(revision, str) or not revision.startswith(
            ("approval:", "sha256:")
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.source_revision",
                invariant="permission_revision_must_be_approval_or_sha256",
                detail="Expected approval:<id> or sha256:<hash>",
            )
        expected_revision_prefix = None
    if expected_revision_prefix is not None:
        revision = payload["source_revision"]
        if not isinstance(revision, str) or not revision.startswith(
            expected_revision_prefix
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.source_revision",
                invariant="input_revision_must_match_kind",
                detail=f"Expected revision prefix {expected_revision_prefix!r}",
            )
    if payload["content_format"] == "utf8_text":
        content = require_string(
            payload["content"],
            artifact_id=artifact_id,
            field="payload.content",
            allow_empty=True,
        ).encode("utf-8")
    elif payload["content_format"] == "jcs_json":
        content = canonicalize(payload["content"])
    else:
        fail(
            artifact_id=artifact_id,
            field="payload.content_format",
            invariant="input_content_format_must_be_known",
            detail=f"Unknown content format: {payload['content_format']}",
        )
    expected_hash = validate_hash(
        payload["content_sha256"],
        artifact_id=artifact_id,
        field="payload.content_sha256",
    )
    if sha256_hex(content) != expected_hash:
        fail(
            artifact_id=artifact_id,
            field="payload.content_sha256",
            invariant="input_content_hash_must_match_exact_stored_content",
            detail="Input content SHA-256 does not match the stored exact content",
        )
    revision = payload["source_revision"]
    if input_kind == "required_capability":
        if payload["content_format"] != "jcs_json":
            fail(
                artifact_id=artifact_id,
                field="payload.content_format",
                invariant="required_capability_content_must_be_jcs_json",
                detail="Required capability identity must use canonical JSON",
            )
        capability = require_dict(
            payload["content"],
            artifact_id=artifact_id,
            field="payload.content",
        )
        if "sources" not in capability:
            fail(
                artifact_id=artifact_id,
                field="payload.content.sources",
                invariant="required_capability_sources_must_not_be_empty",
                detail="A required capability must preserve at least one loaded source",
            )
        require_exact_fields(
            capability,
            {"capability_name", "declared_version", "sources"},
            artifact_id=artifact_id,
            field="payload.content",
        )
        capability_name = require_string(
            capability["capability_name"],
            artifact_id=artifact_id,
            field="payload.content.capability_name",
        )
        declared_version = capability["declared_version"]
        if declared_version is not None:
            require_string(
                declared_version,
                artifact_id=artifact_id,
                field="payload.content.declared_version",
            )
        sources = require_list(
            capability["sources"],
            artifact_id=artifact_id,
            field="payload.content.sources",
        )
        if not sources:
            fail(
                artifact_id=artifact_id,
                field="payload.content.sources",
                invariant="required_capability_sources_must_not_be_empty",
                detail="A required capability must preserve at least one loaded source",
            )
        source_paths: list[str] = []
        for index, source_value in enumerate(sources):
            source_field = f"payload.content.sources[{index}]"
            source = require_dict(
                source_value, artifact_id=artifact_id, field=source_field
            )
            require_exact_fields(
                source,
                {"canonical_realpath", "content", "content_sha256"},
                artifact_id=artifact_id,
                field=source_field,
            )
            path = require_string(
                source["canonical_realpath"],
                artifact_id=artifact_id,
                field=f"{source_field}.canonical_realpath",
            )
            if (
                not path.startswith("/")
                or "\x00" in path
                or posixpath.normpath(path) != path
            ):
                fail(
                    artifact_id=artifact_id,
                    field=f"{source_field}.canonical_realpath",
                    invariant="required_capability_source_path_must_be_canonical_absolute",
                    detail=f"Source path is not a canonical absolute realpath: {path!r}",
                )
            source_paths.append(path)
            source_content = require_string(
                source["content"],
                artifact_id=artifact_id,
                field=f"{source_field}.content",
                allow_empty=True,
            )
            source_hash = validate_hash(
                source["content_sha256"],
                artifact_id=artifact_id,
                field=f"{source_field}.content_sha256",
            )
            if sha256_hex(source_content.encode("utf-8")) != source_hash:
                fail(
                    artifact_id=artifact_id,
                    field=f"{source_field}.content_sha256",
                    invariant="required_capability_source_hash_must_match_utf8_content",
                    detail="Source hash differs from the exact stored UTF-8 content",
                )
        if source_paths != sorted(
            source_paths, key=lambda item: item.encode("utf-8")
        ) or len(source_paths) != len(set(source_paths)):
            fail(
                artifact_id=artifact_id,
                field="payload.content.sources",
                invariant="required_capability_sources_must_be_path_sorted_and_unique",
                detail="Capability sources must be unique and sorted by canonical realpath",
            )
        expected_revision = (
            f"version:{declared_version}"
            if declared_version is not None
            else f"sha256:{expected_hash}"
        )
        if revision != expected_revision:
            fail(
                artifact_id=artifact_id,
                field="payload.source_revision",
                invariant="required_capability_revision_must_match_declared_identity",
                detail=f"Expected {expected_revision}, got {revision}",
            )
        expected_identifier = f"skill:{capability_name}"
        if payload["source_identifier"] != expected_identifier:
            fail(
                artifact_id=artifact_id,
                field="payload.source_identifier",
                invariant="required_capability_source_identifier_must_match_identity",
                detail=f"Expected {expected_identifier}",
            )
    if isinstance(revision, str) and revision.startswith("sha256:"):
        expected_revision = f"sha256:{expected_hash}"
        if revision != expected_revision:
            fail(
                artifact_id=artifact_id,
                field="payload.source_revision",
                invariant="sha256_revision_must_match_exact_input_content",
                detail=f"Expected {expected_revision}, got {revision}",
            )
    expected_trust_sources: dict[str, set[str]] = {
        "repository_identity": {"runtime_observed"},
        "prior_run_handoff": {"runtime_observed"},
        "project_rule": {"base"},
        "acceptance_policy": {"base"},
        "issue_bundle": {"external_authoritative"},
        "personal_contract": {"personal_contract"},
        "required_capability": {"personal_contract"},
        "human_approved_run_local": {"human_approved_run_local"},
        "explicit_scope": {"human_approved_run_local"},
        "permission_set": (
            {"human_approved_run_local"}
            if isinstance(revision, str) and revision.startswith("approval:")
            else {"personal_contract"}
        ),
    }
    allowed_trust_sources = expected_trust_sources.get(input_kind)
    if allowed_trust_sources is not None and trust_source not in allowed_trust_sources:
        fail(
            artifact_id=artifact_id,
            field="payload.trust_source",
            invariant="input_kind_must_bind_to_authorized_trust_source",
            detail=(
                f"Input kind {input_kind} requires one of "
                f"{sorted(allowed_trust_sources)}, got {trust_source}"
            ),
        )
    if input_kind == "repository_identity":
        if payload["source_identifier"] != "runtime:git-common-dir":
            fail(
                artifact_id=artifact_id,
                field="payload.source_identifier",
                invariant="repository_identity_source_identifier_must_be_runtime_git_common_dir",
                detail="Repository identity must use runtime:git-common-dir",
            )
        identity = require_dict(
            payload["content"], artifact_id=artifact_id, field="payload.content"
        )
        require_exact_fields(
            identity,
            {"identity_kind", "identity_value"},
            artifact_id=artifact_id,
            field="payload.content",
        )
        if identity["identity_kind"] != "git_common_dir_realpath":
            fail(
                artifact_id=artifact_id,
                field="payload.content.identity_kind",
                invariant="repository_identity_kind_must_be_git_common_dir_realpath",
                detail=f"Unexpected identity kind: {identity['identity_kind']}",
            )
        identity_value = require_string(
            identity["identity_value"],
            artifact_id=artifact_id,
            field="payload.content.identity_value",
        )
        if not identity_value.startswith("/"):
            fail(
                artifact_id=artifact_id,
                field="payload.content.identity_value",
                invariant="repository_identity_value_must_be_absolute_realpath",
                detail="Repository identity value must be an absolute path",
            )
    if input_kind == "external_record":
        record = require_dict(
            payload["content"], artifact_id=artifact_id, field="payload.content"
        )
        authority_status = record.get("authority_status")
        if authority_status not in {"governing", "evidence_only", "pending"}:
            fail(
                artifact_id=artifact_id,
                field="payload.content.authority_status",
                invariant="external_record_authority_status_must_be_known",
                detail=f"Unknown authority status: {authority_status!r}",
            )
        require_string(
            record.get("authority_basis"),
            artifact_id=artifact_id,
            field="payload.content.authority_basis",
        )
        expected_trust_source = (
            "external_authoritative"
            if authority_status == "governing"
            else "external_observed"
        )
        if trust_source != expected_trust_source:
            fail(
                artifact_id=artifact_id,
                field="payload.trust_source",
                invariant="external_authority_status_must_bind_to_trust_source",
                detail=(
                    f"Authority status {authority_status} requires "
                    f"{expected_trust_source}, got {trust_source}"
                ),
            )


def _validate_scope_paths(fingerprint: dict[str, Any], *, artifact_id: str) -> None:
    scope = require_dict(
        fingerprint.get("scope"),
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.scope",
    )
    require_fields(
        scope,
        {"included_paths", "excluded_paths"},
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.scope",
    )
    included = require_list(
        scope["included_paths"],
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.scope.included_paths",
    )
    if included == ["."]:
        pass
    else:
        if "." in included:
            fail(
                artifact_id=artifact_id,
                field="payload.popr_target_fingerprint.scope.included_paths",
                invariant="repository_root_sentinel_must_be_exact_singleton",
                detail="The '.' root sentinel is only valid as the exact array ['.']",
            )
        for index, path in enumerate(included):
            validate_repository_path(
                path,
                artifact_id=artifact_id,
                field=f"payload.popr_target_fingerprint.scope.included_paths[{index}]",
            )
    excluded = require_list(
        scope["excluded_paths"],
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.scope.excluded_paths",
    )
    for index, item in enumerate(excluded):
        entry = require_dict(
            item,
            artifact_id=artifact_id,
            field=f"payload.popr_target_fingerprint.scope.excluded_paths[{index}]",
        )
        require_fields(
            entry,
            {"path", "reason"},
            artifact_id=artifact_id,
            field=f"payload.popr_target_fingerprint.scope.excluded_paths[{index}]",
        )
        validate_repository_path(
            entry["path"],
            artifact_id=artifact_id,
            field=f"payload.popr_target_fingerprint.scope.excluded_paths[{index}].path",
        )
        require_string(
            entry["reason"],
            artifact_id=artifact_id,
            field=f"payload.popr_target_fingerprint.scope.excluded_paths[{index}].reason",
        )


def _validate_target(payload: dict[str, Any], *, artifact_id: str, run_id: str) -> None:
    """レビュー対象の指紋、世代、作業ツリー保存内容を検証する。

    Args:
        payload: レビュー対象記録の本体。
        artifact_id: エラーに含める作業記録ID。
        run_id: 参照先に要求する実行ID。

    Raises:
        ArtifactError: 対象の指紋、参照、世代、または保存内容が契約に反する場合。
    """
    required = {
        "popr_target_fingerprint",
        "repository_identity_ref",
        "generation",
        "transition_reason",
        "mutable_content_snapshots",
        "index_diff_snapshot",
    }
    require_exact_fields(payload, required, artifact_id=artifact_id, field="payload")
    fingerprint = require_dict(
        payload["popr_target_fingerprint"],
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint",
    )
    require_fields(
        fingerprint,
        {
            "schema_version",
            "target_source",
            "git_object_format",
            "base",
            "head",
            "working_tree",
            "index_diff",
            "pr_remote",
            "scope",
            "skill_versions",
            "project_rules",
        },
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint",
    )
    if fingerprint["git_object_format"] not in {"sha1", "sha256"}:
        fail(
            artifact_id=artifact_id,
            field="payload.popr_target_fingerprint.git_object_format",
            invariant="git_object_format_must_be_supported",
            detail=f"Unsupported object format: {fingerprint['git_object_format']}",
        )
    _validate_scope_paths(fingerprint, artifact_id=artifact_id)
    validate_common_ref(
        payload["repository_identity_ref"],
        field="payload.repository_identity_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    require_integer(
        payload["generation"], artifact_id=artifact_id, field="payload.generation"
    )
    require_string(
        payload["transition_reason"],
        artifact_id=artifact_id,
        field="payload.transition_reason",
    )
    snapshots = require_list(
        payload["mutable_content_snapshots"],
        artifact_id=artifact_id,
        field="payload.mutable_content_snapshots",
    )
    snapshot_paths: list[str] = []
    for index, item in enumerate(snapshots):
        field = f"payload.mutable_content_snapshots[{index}]"
        snapshot = require_dict(item, artifact_id=artifact_id, field=field)
        require_exact_fields(
            snapshot,
            {
                "path",
                "mode",
                "type",
                "content_oid",
                "byte_length",
                "content_sha256",
                "content_path",
            },
            artifact_id=artifact_id,
            field=field,
        )
        snapshot_paths.append(
            validate_repository_path(
                snapshot["path"], artifact_id=artifact_id, field=f"{field}.path"
            )
        )
        require_string(snapshot["mode"], artifact_id=artifact_id, field=f"{field}.mode")
        if snapshot["type"] not in {"regular", "symlink"}:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.type",
                invariant="mutable_snapshot_type_must_be_known",
                detail=f"Unknown snapshot type: {snapshot['type']}",
            )
        if (
            not isinstance(snapshot["content_oid"], str)
            or GIT_OID_PATTERN.fullmatch(snapshot["content_oid"]) is None
        ):
            fail(
                artifact_id=artifact_id,
                field=f"{field}.content_oid",
                invariant="git_object_id_must_match_repository_format",
                detail=f"Invalid Git object ID: {snapshot['content_oid']}",
            )
        require_integer(
            snapshot["byte_length"],
            artifact_id=artifact_id,
            field=f"{field}.byte_length",
        )
        validate_hash(
            snapshot["content_sha256"],
            artifact_id=artifact_id,
            field=f"{field}.content_sha256",
        )
        validate_run_relative_path(
            snapshot["content_path"],
            artifact_id=artifact_id,
            field=f"{field}.content_path",
        )
    if snapshot_paths != sorted(
        snapshot_paths, key=lambda item: item.encode("utf-8")
    ) or len(snapshot_paths) != len(set(snapshot_paths)):
        fail(
            artifact_id=artifact_id,
            field="payload.mutable_content_snapshots",
            invariant="mutable_snapshots_must_be_sorted_and_unique",
            detail="Mutable snapshots must be unique and sorted by UTF-8 path bytes",
        )
    index_diff = require_dict(
        fingerprint["index_diff"],
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.index_diff",
    )
    require_fields(
        index_diff,
        {"included", "content_oid"},
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.index_diff",
    )
    included = require_bool(
        index_diff["included"],
        artifact_id=artifact_id,
        field="payload.popr_target_fingerprint.index_diff.included",
    )
    if not included:
        if (
            payload["index_diff_snapshot"] is not None
            or index_diff["content_oid"] is not None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.index_diff_snapshot",
                invariant="excluded_index_diff_must_not_have_snapshot",
                detail="Excluded index diff requires null content_oid and snapshot",
            )
    else:
        snapshot = require_dict(
            payload["index_diff_snapshot"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot",
        )
        require_exact_fields(
            snapshot,
            {
                "byte_length",
                "content_sha256",
                "content_path",
                "capture_environment",
                "capture_argv",
            },
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot",
        )
        require_integer(
            snapshot["byte_length"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot.byte_length",
        )
        validate_hash(
            snapshot["content_sha256"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot.content_sha256",
        )
        validate_run_relative_path(
            snapshot["content_path"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot.content_path",
        )
        environment = require_dict(
            snapshot["capture_environment"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot.capture_environment",
        )
        for name, value in environment.items():
            require_string(
                name,
                artifact_id=artifact_id,
                field="payload.index_diff_snapshot.capture_environment.<key>",
            )
            require_string(
                value,
                artifact_id=artifact_id,
                field=f"payload.index_diff_snapshot.capture_environment.{name}",
                allow_empty=True,
            )
        capture_argv = require_list(
            snapshot["capture_argv"],
            artifact_id=artifact_id,
            field="payload.index_diff_snapshot.capture_argv",
        )
        if not capture_argv:
            fail(
                artifact_id=artifact_id,
                field="payload.index_diff_snapshot.capture_argv",
                invariant="capture_argv_must_not_be_empty",
                detail="Index diff capture argv must identify the exact command",
            )
        for index, argument in enumerate(capture_argv):
            require_string(
                argument,
                artifact_id=artifact_id,
                field=f"payload.index_diff_snapshot.capture_argv[{index}]",
                allow_empty=True,
            )
        if (
            not isinstance(index_diff["content_oid"], str)
            or GIT_OID_PATTERN.fullmatch(index_diff["content_oid"]) is None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.popr_target_fingerprint.index_diff.content_oid",
                invariant="included_index_diff_must_have_git_object_id",
                detail="Included index diff requires a valid Git object ID",
            )


def _validate_transition_content_source(
    value: Any, *, artifact_id: str, field: str
) -> None:
    source = require_dict(value, artifact_id=artifact_id, field=field)
    kind = require_string(
        source.get("kind"), artifact_id=artifact_id, field=f"{field}.kind"
    )
    if kind == "git_object":
        require_exact_fields(
            source,
            {"kind", "object_id"},
            artifact_id=artifact_id,
            field=field,
        )
        object_id = require_string(
            source["object_id"],
            artifact_id=artifact_id,
            field=f"{field}.object_id",
        )
        if GIT_OID_PATTERN.fullmatch(object_id) is None:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.object_id",
                invariant="git_object_id_must_match_repository_format",
                detail=f"Invalid Git object ID: {object_id}",
            )
        return
    if kind == "target_attachment":
        require_exact_fields(
            source,
            {"kind", "target_id", "content_path"},
            artifact_id=artifact_id,
            field=field,
        )
        require_string(
            source["target_id"],
            artifact_id=artifact_id,
            field=f"{field}.target_id",
        )
        validate_run_relative_path(
            source["content_path"],
            artifact_id=artifact_id,
            field=f"{field}.content_path",
        )
        return
    fail(
        artifact_id=artifact_id,
        field=f"{field}.kind",
        invariant="transition_content_source_kind_must_be_known",
        detail=f"Unknown transition content source: {kind}",
    )


def _validate_transition_file_side(value: Any, *, artifact_id: str, field: str) -> None:
    side = require_dict(value, artifact_id=artifact_id, field=field)
    status = require_string(
        side.get("status"), artifact_id=artifact_id, field=f"{field}.status"
    )
    if status == "absent":
        require_exact_fields(side, {"status"}, artifact_id=artifact_id, field=field)
        return
    if status != "present":
        fail(
            artifact_id=artifact_id,
            field=f"{field}.status",
            invariant="transition_file_status_must_be_known",
            detail=f"Unknown transition file status: {status}",
        )
    require_exact_fields(
        side,
        {
            "status",
            "mode",
            "type",
            "content_oid",
            "byte_length",
            "content_sha256",
            "content_source",
        },
        artifact_id=artifact_id,
        field=field,
    )
    require_string(side["mode"], artifact_id=artifact_id, field=f"{field}.mode")
    if side["type"] not in {"regular", "symlink"}:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.type",
            invariant="transition_file_type_must_be_known",
            detail=f"Unknown transition file type: {side['type']}",
        )
    content_oid = require_string(
        side["content_oid"], artifact_id=artifact_id, field=f"{field}.content_oid"
    )
    if GIT_OID_PATTERN.fullmatch(content_oid) is None:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.content_oid",
            invariant="git_object_id_must_match_repository_format",
            detail=f"Invalid Git object ID: {content_oid}",
        )
    require_integer(
        side["byte_length"], artifact_id=artifact_id, field=f"{field}.byte_length"
    )
    validate_hash(
        side["content_sha256"],
        artifact_id=artifact_id,
        field=f"{field}.content_sha256",
    )
    _validate_transition_content_source(
        side["content_source"], artifact_id=artifact_id, field=f"{field}.content_source"
    )


def _validate_transition_index_side(
    value: Any, *, artifact_id: str, field: str
) -> None:
    side = require_dict(value, artifact_id=artifact_id, field=field)
    status = require_string(
        side.get("status"), artifact_id=artifact_id, field=f"{field}.status"
    )
    if status == "excluded":
        require_exact_fields(side, {"status"}, artifact_id=artifact_id, field=field)
        return
    if status != "included":
        fail(
            artifact_id=artifact_id,
            field=f"{field}.status",
            invariant="transition_index_status_must_be_known",
            detail=f"Unknown transition index status: {status}",
        )
    require_exact_fields(
        side,
        {
            "status",
            "content_oid",
            "byte_length",
            "content_sha256",
            "content_source",
        },
        artifact_id=artifact_id,
        field=field,
    )
    content_oid = require_string(
        side["content_oid"], artifact_id=artifact_id, field=f"{field}.content_oid"
    )
    if GIT_OID_PATTERN.fullmatch(content_oid) is None:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.content_oid",
            invariant="git_object_id_must_match_repository_format",
            detail=f"Invalid Git object ID: {content_oid}",
        )
    require_integer(
        side["byte_length"], artifact_id=artifact_id, field=f"{field}.byte_length"
    )
    validate_hash(
        side["content_sha256"],
        artifact_id=artifact_id,
        field=f"{field}.content_sha256",
    )
    source = require_dict(
        side["content_source"],
        artifact_id=artifact_id,
        field=f"{field}.content_source",
    )
    require_exact_fields(
        source,
        {"kind", "target_id", "content_path"},
        artifact_id=artifact_id,
        field=f"{field}.content_source",
    )
    if source["kind"] != "target_attachment":
        fail(
            artifact_id=artifact_id,
            field=f"{field}.content_source.kind",
            invariant="index_diff_source_must_be_target_attachment",
            detail="Included index diff bytes must come from a target attachment",
        )
    require_string(
        source["target_id"],
        artifact_id=artifact_id,
        field=f"{field}.content_source.target_id",
    )
    validate_run_relative_path(
        source["content_path"],
        artifact_id=artifact_id,
        field=f"{field}.content_source.content_path",
    )


def _validate_transition_diff(value: Any, *, artifact_id: str, run_id: str) -> None:
    """対象変更の前後差分が再検証可能な形式で保存されているか確認する。

    Args:
        value: 前後差分の保存内容。
        artifact_id: エラーに含める作業記録ID。
        run_id: 前後の対象参照に要求する実行ID。

    Raises:
        ArtifactError: パス変更、索引差分、または前後の参照が不正な場合。
    """
    content = require_dict(value, artifact_id=artifact_id, field="payload.content")
    require_exact_fields(
        content,
        {
            "expected_target_ref",
            "observed_target_ref",
            "path_changes",
            "index_diff_change",
        },
        artifact_id=artifact_id,
        field="payload.content",
    )
    for field_name in ("expected_target_ref", "observed_target_ref"):
        validate_common_ref(
            content[field_name],
            field=f"payload.content.{field_name}",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    changes = require_list(
        content["path_changes"],
        artifact_id=artifact_id,
        field="payload.content.path_changes",
    )
    paths: list[str] = []
    for index, change_value in enumerate(changes):
        field = f"payload.content.path_changes[{index}]"
        change = require_dict(change_value, artifact_id=artifact_id, field=field)
        require_exact_fields(
            change,
            {"path", "change_kind", "before", "after"},
            artifact_id=artifact_id,
            field=field,
        )
        paths.append(
            validate_repository_path(
                change["path"], artifact_id=artifact_id, field=f"{field}.path"
            )
        )
        change_kind = require_string(
            change["change_kind"],
            artifact_id=artifact_id,
            field=f"{field}.change_kind",
        )
        _validate_transition_file_side(
            change["before"], artifact_id=artifact_id, field=f"{field}.before"
        )
        _validate_transition_file_side(
            change["after"], artifact_id=artifact_id, field=f"{field}.after"
        )
        before_status = change["before"]["status"]
        after_status = change["after"]["status"]
        if (
            (
                change_kind == "added"
                and (before_status, after_status) != ("absent", "present")
            )
            or (
                change_kind == "deleted"
                and (before_status, after_status) != ("present", "absent")
            )
            or change["before"] == change["after"]
        ):
            fail(
                artifact_id=artifact_id,
                field=field,
                invariant="path_change_kind_and_sides_must_describe_a_real_change",
                detail=f"Invalid {change_kind!r} transition for {change['path']}",
            )
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")) or len(
        paths
    ) != len(set(paths)):
        fail(
            artifact_id=artifact_id,
            field="payload.content.path_changes",
            invariant="transition_paths_must_be_sorted_and_unique",
            detail="Transition paths must be unique and sorted by UTF-8 path bytes",
        )
    index_change = content["index_diff_change"]
    if index_change is not None:
        index_change = require_dict(
            index_change,
            artifact_id=artifact_id,
            field="payload.content.index_diff_change",
        )
        require_exact_fields(
            index_change,
            {"before", "after"},
            artifact_id=artifact_id,
            field="payload.content.index_diff_change",
        )
        _validate_transition_index_side(
            index_change["before"],
            artifact_id=artifact_id,
            field="payload.content.index_diff_change.before",
        )
        _validate_transition_index_side(
            index_change["after"],
            artifact_id=artifact_id,
            field="payload.content.index_diff_change.after",
        )
        if index_change["before"] == index_change["after"]:
            fail(
                artifact_id=artifact_id,
                field="payload.content.index_diff_change",
                invariant="index_diff_change_must_describe_a_real_change",
                detail="Index diff before and after sides are identical",
            )
    if not changes and index_change is None:
        fail(
            artifact_id=artifact_id,
            field="payload.content",
            invariant="target_transition_diff_must_not_be_empty",
            detail="A target transition diff requires a path or index diff change",
        )


def _validate_evidence(
    payload: dict[str, Any], *, artifact_id: str, run_id: str
) -> None:
    require_fields(
        payload,
        PAYLOAD_REQUIRED_FIELDS["evidence"],
        artifact_id=artifact_id,
        field="payload",
    )
    has_path = "content_path" in payload and payload["content_path"] is not None
    has_inline = "content" in payload
    if has_path == has_inline:
        fail(
            artifact_id=artifact_id,
            field="payload",
            invariant="evidence_must_have_exactly_one_content_source",
            detail="Evidence requires exactly one of content_path or inline content",
        )
    validate_hash(
        payload["content_sha256"],
        artifact_id=artifact_id,
        field="payload.content_sha256",
    )
    if has_path:
        validate_run_relative_path(
            payload["content_path"],
            artifact_id=artifact_id,
            field="payload.content_path",
        )
    else:
        inline = payload["content"]
        if isinstance(inline, str):
            content = inline.encode("utf-8")
        else:
            content = canonicalize(inline)
        if sha256_hex(content) != payload["content_sha256"]:
            fail(
                artifact_id=artifact_id,
                field="payload.content_sha256",
                invariant="inline_evidence_hash_must_match_content",
                detail="Evidence content SHA-256 does not match inline content",
            )
    if payload["completeness"] not in {"full", "redacted", "truncated"}:
        fail(
            artifact_id=artifact_id,
            field="payload.completeness",
            invariant="evidence_completeness_must_be_known",
            detail=f"Unknown completeness: {payload['completeness']}",
        )
    require_list(
        payload["redactions"], artifact_id=artifact_id, field="payload.redactions"
    )
    if payload["completeness"] == "truncated":
        if payload["truncation"] is None:
            fail(
                artifact_id=artifact_id,
                field="payload.truncation",
                invariant="truncated_evidence_must_describe_truncation",
                detail="Truncated evidence requires truncation metadata",
            )
    elif payload["truncation"] is not None:
        fail(
            artifact_id=artifact_id,
            field="payload.truncation",
            invariant="nontruncated_evidence_must_not_have_truncation",
            detail="Only truncated evidence can have truncation metadata",
        )
    if payload["evidence_kind"] == "target_transition_diff":
        if has_path:
            fail(
                artifact_id=artifact_id,
                field="payload.content_path",
                invariant="target_transition_diff_must_be_inline_jcs",
                detail="Target transition diff must be inspectable canonical JSON",
            )
        _validate_transition_diff(
            payload["content"], artifact_id=artifact_id, run_id=run_id
        )


def _validate_sorted_unique_strings(
    value: Any, *, artifact_id: str, field: str, allow_empty: bool = True
) -> list[str]:
    values = require_list(value, artifact_id=artifact_id, field=field)
    if not allow_empty and not values:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="string_array_must_not_be_empty",
            detail="At least one string is required",
        )
    strings = [
        require_string(
            item,
            artifact_id=artifact_id,
            field=f"{field}[{index}]",
        )
        for index, item in enumerate(values)
    ]
    if strings != sorted(strings, key=lambda item: item.encode("utf-8")) or len(
        strings
    ) != len(set(strings)):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="string_array_must_be_sorted_and_unique",
            detail="Strings must be unique and sorted by UTF-8 bytes",
        )
    return strings


def _validate_required_gates(
    value: Any, *, artifact_id: str, field: str, run_id: str
) -> None:
    declarations = require_list(value, artifact_id=artifact_id, field=field)
    keys: list[tuple[str, str]] = []
    for index, declaration_value in enumerate(declarations):
        item_field = f"{field}[{index}]"
        declaration = require_dict(
            declaration_value, artifact_id=artifact_id, field=item_field
        )
        require_exact_fields(
            declaration,
            {
                "gate_name",
                "trigger_reason",
                "accepted_decision_statuses",
                "target_ref",
            },
            artifact_id=artifact_id,
            field=item_field,
        )
        gate_name = require_string(
            declaration["gate_name"],
            artifact_id=artifact_id,
            field=f"{item_field}.gate_name",
        )
        require_string(
            declaration["trigger_reason"],
            artifact_id=artifact_id,
            field=f"{item_field}.trigger_reason",
        )
        accepted_statuses = _validate_sorted_unique_strings(
            declaration["accepted_decision_statuses"],
            artifact_id=artifact_id,
            field=f"{item_field}.accepted_decision_statuses",
            allow_empty=False,
        )
        unsupported_statuses = sorted(
            set(accepted_statuses) - READY_GATE_SUCCESS_STATUSES
        )
        if unsupported_statuses:
            fail(
                artifact_id=artifact_id,
                field=f"{item_field}.accepted_decision_statuses",
                invariant="required_gate_accepted_status_must_be_success",
                detail=(
                    "Required gates may accept only PASS or UPDATED, got "
                    f"{unsupported_statuses}"
                ),
            )
        target_ref = validate_common_ref(
            declaration["target_ref"],
            field=f"{item_field}.target_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        keys.append((gate_name, target_ref["artifact_id"]))
    if keys != sorted(keys, key=lambda item: (item[0].encode("utf-8"), item[1])) or len(
        keys
    ) != len(set(keys)):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="required_gate_declarations_must_be_sorted_and_unique",
            detail="Required gates must be unique and sorted by gate name and target",
        )


def _validate_independence_check(value: Any, *, artifact_id: str, field: str) -> None:
    check = require_dict(value, artifact_id=artifact_id, field=field)
    require_exact_fields(
        check,
        {
            "status",
            "compared_instance_ids",
            "compared_context_ids",
            "conflicting_instance_ids",
            "conflicting_context_ids",
        },
        artifact_id=artifact_id,
        field=field,
    )
    status = require_string(
        check["status"], artifact_id=artifact_id, field=f"{field}.status"
    )
    if status not in {"passed", "failed", "unverifiable"}:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.status",
            invariant="independence_status_must_be_known",
            detail=f"Unknown independence status: {status}",
        )
    for field_name in (
        "compared_instance_ids",
        "compared_context_ids",
        "conflicting_instance_ids",
        "conflicting_context_ids",
    ):
        _validate_sorted_unique_strings(
            check[field_name],
            artifact_id=artifact_id,
            field=f"{field}.{field_name}",
        )


def _validate_reconciliation(
    value: Any, *, artifact_id: str, field: str, run_id: str
) -> None:
    reconciliation = require_dict(value, artifact_id=artifact_id, field=field)
    require_exact_fields(
        reconciliation,
        {"previous_findings", "current_findings"},
        artifact_id=artifact_id,
        field=field,
    )
    allowed_statuses = {
        "previous_findings": {"Fixed", "Remaining", "Regressed", "Not applicable"},
        "current_findings": {"New", "Residual"},
    }
    all_finding_ids: list[str] = []
    for collection_name, statuses in allowed_statuses.items():
        collection_field = f"{field}.{collection_name}"
        items = require_list(
            reconciliation[collection_name],
            artifact_id=artifact_id,
            field=collection_field,
        )
        finding_ids: list[str] = []
        for index, item_value in enumerate(items):
            item_field = f"{collection_field}[{index}]"
            item = require_dict(item_value, artifact_id=artifact_id, field=item_field)
            item_fields = {"finding_id", "status", "evidence_refs"}
            if collection_name == "current_findings":
                item_fields.add("blocking")
            require_exact_fields(
                item,
                item_fields,
                artifact_id=artifact_id,
                field=item_field,
            )
            finding_ids.append(
                require_string(
                    item["finding_id"],
                    artifact_id=artifact_id,
                    field=f"{item_field}.finding_id",
                )
            )
            all_finding_ids.append(finding_ids[-1])
            status = require_string(
                item["status"],
                artifact_id=artifact_id,
                field=f"{item_field}.status",
            )
            if status not in statuses:
                fail(
                    artifact_id=artifact_id,
                    field=f"{item_field}.status",
                    invariant="reconciliation_status_must_match_finding_collection",
                    detail=f"Invalid {collection_name} status: {status}",
                )
            if collection_name == "current_findings":
                require_bool(
                    item["blocking"],
                    artifact_id=artifact_id,
                    field=f"{item_field}.blocking",
                )
            validate_ref_array(
                item["evidence_refs"],
                field=f"{item_field}.evidence_refs",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        if finding_ids != sorted(
            finding_ids, key=lambda item: item.encode("utf-8")
        ) or len(finding_ids) != len(set(finding_ids)):
            fail(
                artifact_id=artifact_id,
                field=collection_field,
                invariant="reconciliation_findings_must_be_sorted_and_unique",
                detail="Reconciliation finding IDs must be unique and sorted",
            )
    if len(all_finding_ids) != len(set(all_finding_ids)):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="reconciliation_finding_ids_must_be_unique_across_collections",
            detail="A finding cannot be both previous and current",
        )


def _validate_context_grounding(
    value: Any, *, artifact_id: str, field: str, run_id: str
) -> None:
    if isinstance(value, list):
        if not value:
            fail(
                artifact_id=artifact_id,
                field=field,
                invariant="resolved_context_field_must_not_be_bare_empty_array",
                detail="Use a grounded not_required_reason object for an empty field",
            )
        for index, item in enumerate(value):
            _validate_context_grounding(
                item,
                artifact_id=artifact_id,
                field=f"{field}[{index}]",
                run_id=run_id,
            )
        return
    item = require_dict(value, artifact_id=artifact_id, field=field)
    refs = list(iter_common_refs(item, field=field))
    if not refs:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="resolved_context_item_requires_grounding_ref",
            detail="Resolved context item has no input/Evidence ref",
        )
    for ref_field, ref in refs:
        validate_common_ref(
            ref,
            field=ref_field,
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    content_hashes = [
        nested_value
        for nested_key, nested_value in item.items()
        if nested_key == "content_sha256"
    ]
    if not content_hashes:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="resolved_context_item_requires_content_hash",
            detail="Resolved context item has no content_sha256",
        )
    for content_hash in content_hashes:
        validate_hash(
            content_hash, artifact_id=artifact_id, field=f"{field}.content_sha256"
        )


def _validate_resolved_lenses(
    value: Any, *, artifact_id: str, field: str, run_id: str
) -> None:
    lenses = require_dict(value, artifact_id=artifact_id, field=field)
    require_exact_fields(
        lenses,
        {
            "project_review_status",
            "required_lens_ids",
            "source_ref",
            "content_sha256",
        },
        artifact_id=artifact_id,
        field=field,
    )
    project_review_status = require_string(
        lenses["project_review_status"],
        artifact_id=artifact_id,
        field=f"{field}.project_review_status",
    )
    if project_review_status not in {"required", "not_required"}:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.project_review_status",
            invariant="project_review_status_must_be_known",
            detail=f"Unknown project review status: {project_review_status}",
        )
    required_lens_ids = _validate_sorted_unique_strings(
        lenses["required_lens_ids"],
        artifact_id=artifact_id,
        field=f"{field}.required_lens_ids",
    )
    if project_review_status == "required" and not required_lens_ids:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.required_lens_ids",
            invariant="required_project_review_requires_lens_ids",
            detail="Required project review must identify at least one lens",
        )
    if project_review_status == "not_required" and required_lens_ids:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.required_lens_ids",
            invariant="not_required_project_review_must_not_name_lenses",
            detail="A not-required project review cannot name required lenses",
        )
    validate_common_ref(
        lenses["source_ref"],
        field=f"{field}.source_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    validate_hash(
        lenses["content_sha256"],
        artifact_id=artifact_id,
        field=f"{field}.content_sha256",
    )


def _validate_resolved_commands(
    value: Any, *, artifact_id: str, field: str, run_id: str
) -> None:
    """解決済みの検証コマンドと、その選定根拠を検証する。

    Args:
        value: 解決済みコマンドの一覧。
        artifact_id: エラーに含める作業記録ID。
        field: エラー時に報告するフィールド名。
        run_id: 根拠参照に要求する実行ID。

    Raises:
        ArtifactError: コマンド、由来、根拠参照、または並び順が不正な場合。
    """
    resolved = require_dict(value, artifact_id=artifact_id, field=field)
    expected_fields = {"commands", "source_ref", "content_sha256"}
    if set(resolved) != expected_fields:
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="resolved_commands_must_define_required_commands",
            detail=f"Expected exact fields {sorted(expected_fields)}",
        )
    commands = require_list(
        resolved["commands"], artifact_id=artifact_id, field=f"{field}.commands"
    )
    if not commands:
        fail(
            artifact_id=artifact_id,
            field=f"{field}.commands",
            invariant="resolved_commands_must_define_required_commands",
            detail="At least one required command must be resolved",
        )
    command_ids: list[str] = []
    for index, command_value in enumerate(commands):
        command_field = f"{field}.commands[{index}]"
        command = require_dict(
            command_value, artifact_id=artifact_id, field=command_field
        )
        require_exact_fields(
            command,
            {
                "command_id",
                "argv",
                "effects",
                "timeout_seconds",
                "required_services",
            },
            artifact_id=artifact_id,
            field=command_field,
        )
        command_id = require_string(
            command["command_id"],
            artifact_id=artifact_id,
            field=f"{command_field}.command_id",
        )
        command_ids.append(command_id)
        argv = require_list(
            command["argv"], artifact_id=artifact_id, field=f"{command_field}.argv"
        )
        if not argv:
            fail(
                artifact_id=artifact_id,
                field=f"{command_field}.argv",
                invariant="resolved_command_argv_must_not_be_empty",
                detail="A resolved command requires an executable argv entry",
            )
        for argv_index, argument in enumerate(argv):
            require_string(
                argument,
                artifact_id=artifact_id,
                field=f"{command_field}.argv[{argv_index}]",
            )
        effect_values = require_list(
            command["effects"],
            artifact_id=artifact_id,
            field=f"{command_field}.effects",
        )
        effects = [
            require_string(
                effect,
                artifact_id=artifact_id,
                field=f"{command_field}.effects[{effect_index}]",
            )
            for effect_index, effect in enumerate(effect_values)
        ]
        if (
            not effects
            or len(effects) != len(set(effects))
            or effects
            != [effect for effect in COMMAND_EFFECT_ORDER if effect in effects]
        ):
            fail(
                artifact_id=artifact_id,
                field=f"{command_field}.effects",
                invariant="resolved_command_effects_must_use_contract_order",
                detail=f"Effects must be nonempty, unique, and follow {COMMAND_EFFECT_ORDER}",
            )
        unknown_effects = sorted(set(effects) - set(COMMAND_EFFECT_ORDER))
        if unknown_effects:
            fail(
                artifact_id=artifact_id,
                field=f"{command_field}.effects",
                invariant="resolved_command_effect_must_be_known",
                detail=f"Unknown command effects: {unknown_effects}",
            )
        require_integer(
            command["timeout_seconds"],
            artifact_id=artifact_id,
            field=f"{command_field}.timeout_seconds",
            minimum=1,
        )
        _validate_sorted_unique_strings(
            command["required_services"],
            artifact_id=artifact_id,
            field=f"{command_field}.required_services",
        )
    if command_ids != sorted(command_ids, key=lambda item: item.encode("utf-8")) or len(
        command_ids
    ) != len(set(command_ids)):
        fail(
            artifact_id=artifact_id,
            field=f"{field}.commands",
            invariant="resolved_command_ids_must_be_sorted_and_unique",
            detail="Resolved command IDs must be unique and sorted by UTF-8 bytes",
        )
    validate_common_ref(
        resolved["source_ref"],
        field=f"{field}.source_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    validate_hash(
        resolved["content_sha256"],
        artifact_id=artifact_id,
        field=f"{field}.content_sha256",
    )


def _validate_context_resolution_payload(
    payload: dict[str, Any], *, artifact_id: str, run_id: str
) -> None:
    """プロジェクト専用設定なしで解決した規約、観点、コマンドを検証する。

    Args:
        payload: 実行環境から解決した情報の本体。
        artifact_id: エラーに含める作業記録ID。
        run_id: 参照先に要求する実行ID。

    Raises:
        ArtifactError: 解決方法、根拠、競合、観点、またはコマンドが不正な場合。
    """
    fields = {
        "decision_kind",
        "resolution_mode",
        "contract_status",
        "contract_ref",
        "considered_sources",
        "selected_sources",
        "authority_decisions",
        "resolved_source_of_truth",
        "resolved_scope",
        "resolved_lenses",
        "resolved_commands",
        "resolved_gates",
        "resolved_risk_triggers",
        "resolved_permissions",
        "resolved_limits",
        "unresolved_inputs",
    }
    require_exact_fields(payload, fields, artifact_id=artifact_id, field="payload")
    if payload["resolution_mode"] not in {
        "repository_baseline",
        "human_approved_run_local",
        "mixed",
    }:
        fail(
            artifact_id=artifact_id,
            field="payload.resolution_mode",
            invariant="context_resolution_mode_must_be_known",
            detail=f"Unknown resolution mode: {payload['resolution_mode']}",
        )
    if payload["contract_status"] not in {"resolved", "unavailable", "drifted"}:
        fail(
            artifact_id=artifact_id,
            field="payload.contract_status",
            invariant="contract_status_must_be_known",
            detail=f"Unknown contract status: {payload['contract_status']}",
        )
    if payload["contract_ref"] is not None:
        validate_common_ref(
            payload["contract_ref"],
            field="payload.contract_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    considered = require_list(
        payload["considered_sources"],
        artifact_id=artifact_id,
        field="payload.considered_sources",
    )
    for index, item in enumerate(considered):
        require_dict(
            item,
            artifact_id=artifact_id,
            field=f"payload.considered_sources[{index}]",
        )
    for field_name in ("selected_sources", "authority_decisions"):
        values = require_list(
            payload[field_name], artifact_id=artifact_id, field=f"payload.{field_name}"
        )
        if not values:
            fail(
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
                invariant="resolved_context_collection_must_not_be_empty",
                detail=f"{field_name} requires grounded entries",
            )
        for index, item in enumerate(values):
            _validate_context_grounding(
                item,
                artifact_id=artifact_id,
                field=f"payload.{field_name}[{index}]",
                run_id=run_id,
            )
    for field_name in (
        "resolved_source_of_truth",
        "resolved_scope",
        "resolved_gates",
        "resolved_risk_triggers",
        "resolved_permissions",
        "resolved_limits",
    ):
        _validate_context_grounding(
            payload[field_name],
            artifact_id=artifact_id,
            field=f"payload.{field_name}",
            run_id=run_id,
        )
    _validate_resolved_commands(
        payload["resolved_commands"],
        artifact_id=artifact_id,
        field="payload.resolved_commands",
        run_id=run_id,
    )
    _validate_resolved_lenses(
        payload["resolved_lenses"],
        artifact_id=artifact_id,
        field="payload.resolved_lenses",
        run_id=run_id,
    )
    unresolved = require_list(
        payload["unresolved_inputs"],
        artifact_id=artifact_id,
        field="payload.unresolved_inputs",
    )
    for index, item in enumerate(unresolved):
        require_dict(
            item,
            artifact_id=artifact_id,
            field=f"payload.unresolved_inputs[{index}]",
        )


def _validate_limit_observation_payload(
    payload: dict[str, Any], *, artifact_id: str, run_id: str
) -> None:
    """再試行回数や費用などの上限観測結果を検証する。

    Args:
        payload: 上限観測記録の本体。
        artifact_id: エラーに含める作業記録ID。
        run_id: 根拠参照に要求する実行ID。

    Raises:
        ArtifactError: 観測値、上限、超過理由、または根拠参照が不正な場合。
    """
    fields = {
        "decision_kind",
        "blocked_state",
        "target_ref",
        "failure_classification",
        "observed_evidence_refs",
        "required_human_action",
        "resume_requirement",
        "resume_state",
        "limit_name",
        "limit_value",
        "limit_event",
        "observed_value",
        "counter_key",
        "counter_snapshot",
        "previous_manifest_revision",
        "previous_manifest_sha256",
    }
    require_exact_fields(payload, fields, artifact_id=artifact_id, field="payload")
    if payload["blocked_state"] != "BUDGET_EXHAUSTED":
        fail(
            artifact_id=artifact_id,
            field="payload.blocked_state",
            invariant="limit_observation_must_block_budget_exhausted",
            detail="A limit observation can only cause BUDGET_EXHAUSTED",
        )
    if payload["target_ref"] is not None:
        validate_common_ref(
            payload["target_ref"],
            field="payload.target_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    for field_name in (
        "failure_classification",
        "required_human_action",
        "resume_requirement",
        "limit_name",
        "limit_event",
    ):
        require_string(
            payload[field_name],
            artifact_id=artifact_id,
            field=f"payload.{field_name}",
        )
    if payload["failure_classification"] not in BLOCKER_RULES["BUDGET_EXHAUSTED"][0]:
        fail(
            artifact_id=artifact_id,
            field="payload.failure_classification",
            invariant="limit_observation_classification_must_be_budget_exhausted",
            detail=(
                "A limit observation requires a BUDGET_EXHAUSTED failure classification"
            ),
        )
    if payload["limit_name"] not in MANIFEST_LIMIT_FIELDS:
        fail(
            artifact_id=artifact_id,
            field="payload.limit_name",
            invariant="limit_observation_limit_name_must_be_known",
            detail=f"Unknown limit: {payload['limit_name']}",
        )
    if payload["limit_event"] not in LIMIT_EVENTS:
        fail(
            artifact_id=artifact_id,
            field="payload.limit_event",
            invariant="limit_observation_event_must_be_known",
            detail=f"Unknown limit event: {payload['limit_event']}",
        )
    if payload["counter_key"] is not None:
        require_string(
            payload["counter_key"],
            artifact_id=artifact_id,
            field="payload.counter_key",
        )
    for field_name in ("limit_value", "observed_value"):
        value = payload[field_name]
        if not isinstance(value, (int, str)) or isinstance(value, bool):
            fail(
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
                invariant="limit_observation_value_must_be_integer_or_string",
                detail="Limit observations preserve exact integer or string values",
            )
    counters = require_dict(
        payload["counter_snapshot"],
        artifact_id=artifact_id,
        field="payload.counter_snapshot",
    )
    if set(counters) != MANIFEST_COUNTER_FIELDS:
        fail(
            artifact_id=artifact_id,
            field="payload.counter_snapshot",
            invariant="limit_observation_counters_must_use_manifest_schema",
            detail=f"Expected exact fields {sorted(MANIFEST_COUNTER_FIELDS)}",
        )
    require_integer(
        counters["remediation_cycles_started"],
        artifact_id=artifact_id,
        field="payload.counter_snapshot.remediation_cycles_started",
    )
    for counter_field in (
        "remediation_attempts_by_request_id",
        "transient_retries_by_execution_key",
    ):
        counter_map = require_dict(
            counters[counter_field],
            artifact_id=artifact_id,
            field=f"payload.counter_snapshot.{counter_field}",
        )
        for counter_key, counter_value in counter_map.items():
            require_string(
                counter_key,
                artifact_id=artifact_id,
                field=f"payload.counter_snapshot.{counter_field}.key",
            )
            require_integer(
                counter_value,
                artifact_id=artifact_id,
                field=f"payload.counter_snapshot.{counter_field}.{counter_key}",
            )
    tokens_used = counters["tokens_used"]
    if tokens_used != "unsupported":
        require_integer(
            tokens_used,
            artifact_id=artifact_id,
            field="payload.counter_snapshot.tokens_used",
        )
    require_integer(
        counters["paid_external_calls"],
        artifact_id=artifact_id,
        field="payload.counter_snapshot.paid_external_calls",
    )
    validate_ref_array(
        payload["observed_evidence_refs"],
        field="payload.observed_evidence_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
        allow_empty=False,
    )
    if payload["resume_state"] is not None:
        fail(
            artifact_id=artifact_id,
            field="payload.resume_state",
            invariant="budget_exhausted_resume_state_must_be_null",
            detail="BUDGET_EXHAUSTED is terminal for this run",
        )
    require_integer(
        payload["previous_manifest_revision"],
        artifact_id=artifact_id,
        field="payload.previous_manifest_revision",
    )
    validate_hash(
        payload["previous_manifest_sha256"],
        artifact_id=artifact_id,
        field="payload.previous_manifest_sha256",
    )


def _validate_project_results(value: Any, *, artifact_id: str, field: str) -> list[str]:
    results = require_list(value, artifact_id=artifact_id, field=field)
    lens_ids: list[str] = []
    for index, result_value in enumerate(results):
        result_field = f"{field}[{index}]"
        result = require_dict(result_value, artifact_id=artifact_id, field=result_field)
        lens_ids.append(
            require_string(
                result.get("lens_id"),
                artifact_id=artifact_id,
                field=f"{result_field}.lens_id",
            )
        )
    if len(lens_ids) != len(set(lens_ids)):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="project_result_lens_ids_must_be_unique",
            detail="Each project lens may appear at most once",
        )
    if lens_ids != sorted(lens_ids, key=lambda item: item.encode("utf-8")):
        fail(
            artifact_id=artifact_id,
            field=field,
            invariant="project_result_lens_ids_must_be_sorted",
            detail="Project results must be sorted by lens_id UTF-8 bytes",
        )
    return lens_ids


def _validate_stage_payload(
    artifact_type: str,
    payload: dict[str, Any],
    *,
    artifact_id: str,
    run_id: str,
) -> None:
    """工程別の作業記録本体を種別ごとの契約で検証する。

    レビュー、修正、試験、外部確認、判断などの各記録に対し、必須項目、
    状態値、参照関係の形状を一つの入口で確認する。

    Args:
        artifact_type: 作業記録の種別。
        payload: 工程別の作業記録本体。
        artifact_id: エラーに含める作業記録ID。
        run_id: 参照先に要求する実行ID。

    Raises:
        ArtifactError: 種別固有の必須項目や値が契約に反する場合。
    """
    require_fields(
        payload,
        PAYLOAD_REQUIRED_FIELDS[artifact_type],
        artifact_id=artifact_id,
        field="payload",
    )
    if artifact_type == "target_check":
        status = require_string(
            payload["status"], artifact_id=artifact_id, field="payload.status"
        )
        if status not in {"unchanged", "changed", "unresolved"}:
            fail(
                artifact_id=artifact_id,
                field="payload.status",
                invariant="target_check_status_must_be_known",
                detail=f"Unknown target check status: {payload['status']}",
            )
        transition_kinds = require_list(
            payload["transition_kinds"],
            artifact_id=artifact_id,
            field="payload.transition_kinds",
        )
        for index, transition_kind in enumerate(transition_kinds):
            require_string(
                transition_kind,
                artifact_id=artifact_id,
                field=f"payload.transition_kinds[{index}]",
            )
        expected_kinds = sorted(
            transition_kinds,
            key=lambda item: (
                (-1 if item == "none" else TRANSITION_KIND_ORDER.index(item))
                if item == "none" or item in TRANSITION_KIND_ORDER
                else len(TRANSITION_KIND_ORDER)
            ),
        )
        if (
            len(transition_kinds) != len(set(transition_kinds))
            or transition_kinds != expected_kinds
            or any(
                item not in {"none", *TRANSITION_KIND_ORDER}
                for item in transition_kinds
            )
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.transition_kinds",
                invariant="transition_kinds_must_be_known_ordered_and_unique",
                detail=f"Invalid transition kinds: {transition_kinds!r}",
            )
        if (
            (status == "unchanged" and transition_kinds != ["none"])
            or (
                status == "changed"
                and (
                    not transition_kinds
                    or "none" in transition_kinds
                    or "unresolved" in transition_kinds
                )
            )
            or (status == "unresolved" and "unresolved" not in transition_kinds)
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.transition_kinds",
                invariant="transition_kinds_must_match_target_check_status",
                detail=f"Status {status} is inconsistent with {transition_kinds!r}",
            )
        for field_name in (
            "observed_components",
            "changed_components",
            "unresolved_components",
        ):
            require_list(
                payload[field_name],
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
            )
        validate_common_ref(
            payload["expected_target_ref"],
            field="payload.expected_target_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        validate_ref_array(
            payload["expected_input_refs"],
            field="payload.expected_input_refs",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        validate_ref_array(
            payload["observed_input_refs"],
            field="payload.observed_input_refs",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        for field_name in (
            "expected_permission_set_ref",
            "observed_permission_set_ref",
            "expected_contract_ref",
            "observed_contract_ref",
            "transition_diff_ref",
        ):
            ref = payload[field_name]
            if ref is not None:
                validate_common_ref(
                    ref,
                    field=f"payload.{field_name}",
                    run_id=run_id,
                    containing_artifact_id=artifact_id,
                )
        for field_name in (
            "expected_project_rule_refs",
            "observed_project_rule_refs",
            "observation_evidence_refs",
        ):
            validate_ref_array(
                payload[field_name],
                field=f"payload.{field_name}",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        validate_rfc3339(
            payload["checked_at"], artifact_id=artifact_id, field="payload.checked_at"
        )
        if status == "unresolved":
            if (
                payload["observed_target_status"] != "unresolved"
                or payload["observed_target_ref"] is not None
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.observed_target_ref",
                    invariant="unresolved_target_check_must_not_invent_target",
                    detail="Unresolved target check requires null observed target ref",
                )
            require_string(
                payload["observed_target_absence_reason"],
                artifact_id=artifact_id,
                field="payload.observed_target_absence_reason",
            )
        else:
            if (
                payload["observed_target_status"] != "resolved"
                or payload["observed_target_ref"] is None
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.observed_target_ref",
                    invariant="resolved_target_check_must_have_observed_target",
                    detail="Resolved target check requires an observed target ref",
                )
            validate_common_ref(
                payload["observed_target_ref"],
                field="payload.observed_target_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
            if payload["observed_target_absence_reason"] is not None:
                fail(
                    artifact_id=artifact_id,
                    field="payload.observed_target_absence_reason",
                    invariant="resolved_target_check_must_not_have_absence_reason",
                    detail="Resolved target check requires null absence reason",
                )
    elif artifact_type == "review":
        for field_name in (
            "generic_coverage_status",
            "project_coverage_status",
            "coverage_status",
        ):
            require_string(
                payload[field_name],
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
            )
        if payload["generic_coverage_status"] not in {"Complete", "Incomplete"}:
            fail(
                artifact_id=artifact_id,
                field="payload.generic_coverage_status",
                invariant="generic_coverage_status_must_be_known",
                detail=f"Unknown generic coverage: {payload['generic_coverage_status']}",
            )
        if payload["project_coverage_status"] not in {
            "Complete",
            "Incomplete",
            "not_required",
        }:
            fail(
                artifact_id=artifact_id,
                field="payload.project_coverage_status",
                invariant="project_coverage_status_must_be_known",
                detail=f"Unknown project coverage: {payload['project_coverage_status']}",
            )
        if payload["coverage_status"] not in {"Complete", "Incomplete"}:
            fail(
                artifact_id=artifact_id,
                field="payload.coverage_status",
                invariant="review_coverage_status_must_be_known",
                detail=f"Unknown review coverage: {payload['coverage_status']}",
            )
        require_dict(
            payload["popr_result"],
            artifact_id=artifact_id,
            field="payload.popr_result",
        )
        require_dict(
            payload["generic_risk_result"],
            artifact_id=artifact_id,
            field="payload.generic_risk_result",
        )
        _validate_project_results(
            payload["project_results"],
            artifact_id=artifact_id,
            field="payload.project_results",
        )
        _validate_sorted_unique_strings(
            payload["blocking_finding_ids"],
            artifact_id=artifact_id,
            field="payload.blocking_finding_ids",
        )
        _validate_required_gates(
            payload["required_gates"],
            artifact_id=artifact_id,
            field="payload.required_gates",
            run_id=run_id,
        )
    elif artifact_type == "change_request":
        requests = require_list(
            payload["requests"], artifact_id=artifact_id, field="payload.requests"
        )
        if not requests:
            fail(
                artifact_id=artifact_id,
                field="payload.requests",
                invariant="change_request_must_not_be_empty",
                detail="At least one change request is required",
            )
        request_ids: list[str] = []
        for index, request_value in enumerate(requests):
            field = f"payload.requests[{index}]"
            request = require_dict(request_value, artifact_id=artifact_id, field=field)
            source_type = require_string(
                request.get("source_type"),
                artifact_id=artifact_id,
                field=f"{field}.source_type",
            )
            fields_by_source = {
                "review_finding": {
                    "source_type",
                    "id",
                    "source_ref",
                    "source_item_id",
                },
                "verification_failure": {
                    "source_type",
                    "id",
                    "source_ref",
                    "command_id",
                    "expected_behavior_ref",
                    "observed_failure",
                    "output_ref",
                },
                "gate_failure": {
                    "source_type",
                    "id",
                    "source_ref",
                    "expected_behavior_ref",
                    "evidence_ref",
                },
            }
            if source_type not in fields_by_source:
                fail(
                    artifact_id=artifact_id,
                    field=f"{field}.source_type",
                    invariant="change_request_source_type_must_be_known",
                    detail=f"Unknown request source type: {source_type}",
                )
            require_exact_fields(
                request,
                fields_by_source[source_type],
                artifact_id=artifact_id,
                field=field,
            )
            request_id = require_string(
                request["id"], artifact_id=artifact_id, field=f"{field}.id"
            )
            request_ids.append(request_id)
            validate_common_ref(
                request["source_ref"],
                field=f"{field}.source_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
            if source_type == "review_finding":
                source_item_id = require_string(
                    request["source_item_id"],
                    artifact_id=artifact_id,
                    field=f"{field}.source_item_id",
                )
                if request_id != source_item_id:
                    fail(
                        artifact_id=artifact_id,
                        field=field,
                        invariant="review_request_id_must_match_source_finding_id",
                        detail=f"Request {request_id!r} differs from {source_item_id!r}",
                    )
            elif source_type == "verification_failure":
                require_string(
                    request["command_id"],
                    artifact_id=artifact_id,
                    field=f"{field}.command_id",
                )
                require_string(
                    request["observed_failure"],
                    artifact_id=artifact_id,
                    field=f"{field}.observed_failure",
                )
                for ref_name in ("expected_behavior_ref", "output_ref"):
                    validate_common_ref(
                        request[ref_name],
                        field=f"{field}.{ref_name}",
                        run_id=run_id,
                        containing_artifact_id=artifact_id,
                    )
            else:
                for ref_name in ("expected_behavior_ref", "evidence_ref"):
                    validate_common_ref(
                        request[ref_name],
                        field=f"{field}.{ref_name}",
                        run_id=run_id,
                        containing_artifact_id=artifact_id,
                    )
        if len(request_ids) != len(set(request_ids)):
            fail(
                artifact_id=artifact_id,
                field="payload.requests",
                invariant="change_request_ids_must_be_unique",
                detail="Change request IDs must be unique",
            )
    elif artifact_type == "verification":
        commands = require_list(
            payload["commands"], artifact_id=artifact_id, field="payload.commands"
        )
        for index, command_value in enumerate(commands):
            command = require_dict(
                command_value,
                artifact_id=artifact_id,
                field=f"payload.commands[{index}]",
            )
            require_exact_fields(
                command,
                {
                    "command_id",
                    "argv",
                    "exit_code",
                    "started_at",
                    "finished_at",
                    "stdout_ref",
                    "stderr_ref",
                    "environment_snapshot_ref",
                },
                artifact_id=artifact_id,
                field=f"payload.commands[{index}]",
            )
            require_string(
                command["command_id"],
                artifact_id=artifact_id,
                field=f"payload.commands[{index}].command_id",
            )
            argv = require_list(
                command["argv"],
                artifact_id=artifact_id,
                field=f"payload.commands[{index}].argv",
            )
            if not argv:
                fail(
                    artifact_id=artifact_id,
                    field=f"payload.commands[{index}].argv",
                    invariant="verification_command_argv_must_not_be_empty",
                    detail="Verification command requires exact argv",
                )
            for argument_index, argument in enumerate(argv):
                require_string(
                    argument,
                    artifact_id=artifact_id,
                    field=f"payload.commands[{index}].argv[{argument_index}]",
                )
            if not isinstance(command["exit_code"], int) or isinstance(
                command["exit_code"], bool
            ):
                fail(
                    artifact_id=artifact_id,
                    field=f"payload.commands[{index}].exit_code",
                    invariant="field_must_be_integer",
                    detail="Command exit code must be an integer",
                )
            validate_rfc3339(
                command["started_at"],
                artifact_id=artifact_id,
                field=f"payload.commands[{index}].started_at",
            )
            validate_rfc3339(
                command["finished_at"],
                artifact_id=artifact_id,
                field=f"payload.commands[{index}].finished_at",
            )
            validate_common_ref(
                command["stdout_ref"],
                field=f"payload.commands[{index}].stdout_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
            validate_common_ref(
                command["stderr_ref"],
                field=f"payload.commands[{index}].stderr_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
            validate_common_ref(
                command["environment_snapshot_ref"],
                field=f"payload.commands[{index}].environment_snapshot_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        status = require_string(
            payload["status"], artifact_id=artifact_id, field="payload.status"
        )
        if status not in {"passed", "failed", "unverified"}:
            fail(
                artifact_id=artifact_id,
                field="payload.status",
                invariant="verification_status_must_be_known",
                detail=f"Unknown verification status: {status}",
            )
        if status == "passed":
            if (
                not commands
                or payload["unverified_reason"] is not None
                or any(command["exit_code"] != 0 for command in commands)
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.unverified_reason",
                    invariant="passed_verification_must_not_have_unverified_reason",
                    detail="Passed verification requires commands, zero exits, and no reason",
                )
        elif status == "failed":
            if (
                not commands
                or payload["unverified_reason"] is not None
                or all(command["exit_code"] == 0 for command in commands)
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.commands",
                    invariant="failed_verification_requires_observed_failure",
                    detail=(
                        "Failed verification requires a nonzero command exit and a "
                        "null unverified reason"
                    ),
                )
        else:
            require_string(
                payload["unverified_reason"],
                artifact_id=artifact_id,
                field="payload.unverified_reason",
            )
        mutated_target = require_bool(
            payload["mutated_target"],
            artifact_id=artifact_id,
            field="payload.mutated_target",
        )
        if mutated_target:
            if payload["mutation_patch_ref"] is None:
                fail(
                    artifact_id=artifact_id,
                    field="payload.mutation_patch_ref",
                    invariant="mutated_stage_must_have_patch_evidence",
                    detail="Target mutation requires mutation patch evidence",
                )
            validate_common_ref(
                payload["mutation_patch_ref"],
                field="payload.mutation_patch_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        elif payload["mutation_patch_ref"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload.mutation_patch_ref",
                invariant="unmutated_stage_must_not_have_mutation_patch",
                detail="Unmutated verification requires null mutation patch ref",
            )
    elif artifact_type == "remediation":
        require_string(
            payload["request_id"],
            artifact_id=artifact_id,
            field="payload.request_id",
        )
        decision = require_string(
            payload["decision"], artifact_id=artifact_id, field="payload.decision"
        )
        if decision not in REMEDIATION_DECISIONS:
            fail(
                artifact_id=artifact_id,
                field="payload.decision",
                invariant="remediation_decision_must_be_known",
                detail=f"Unknown remediation decision: {decision}",
            )
        require_string(
            payload["minimal_change"],
            artifact_id=artifact_id,
            field="payload.minimal_change",
        )
        for field_name in ("planned_paths", "changed_paths", "test_plan"):
            values = require_list(
                payload[field_name],
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
            )
            for index, value in enumerate(values):
                require_string(
                    value,
                    artifact_id=artifact_id,
                    field=f"payload.{field_name}[{index}]",
                )
        require_string(
            payload["scope_effect"],
            artifact_id=artifact_id,
            field="payload.scope_effect",
        )
        if payload["patch_ref"] is not None:
            validate_common_ref(
                payload["patch_ref"],
                field="payload.patch_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        if (
            payload["decision"] == "fix"
            and payload["changed_paths"]
            and payload["patch_ref"] is None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.patch_ref",
                invariant="fixed_remediation_must_have_patch_evidence",
                detail="A remediation that changed paths requires patch evidence",
            )
    elif artifact_type == "gate":
        for field_name in (
            "gate_name",
            "capability_revision",
            "execution_status",
            "decision_status",
        ):
            require_string(
                payload[field_name],
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
            )
        declared_version = payload["declared_version"]
        if declared_version is not None:
            require_string(
                declared_version,
                artifact_id=artifact_id,
                field="payload.declared_version",
            )
        content_sha256 = validate_hash(
            payload["content_sha256"],
            artifact_id=artifact_id,
            field="payload.content_sha256",
        )
        expected_capability_revision = (
            f"version:{declared_version}"
            if declared_version is not None
            else f"sha256:{content_sha256}"
        )
        if payload["capability_revision"] != expected_capability_revision:
            fail(
                artifact_id=artifact_id,
                field="payload.capability_revision",
                invariant="gate_capability_revision_must_match_declared_identity",
                detail=f"Expected {expected_capability_revision}",
            )
        if payload["execution_status"] not in {"succeeded", "failed", "unavailable"}:
            fail(
                artifact_id=artifact_id,
                field="payload.execution_status",
                invariant="gate_execution_status_must_be_known",
                detail=f"Unknown execution status: {payload['execution_status']}",
            )
        if payload["decision_status"] not in {
            "PASS",
            "UPDATED",
            "BLOCKED",
            "HUMAN_DECISION_REQUIRED",
        }:
            fail(
                artifact_id=artifact_id,
                field="payload.decision_status",
                invariant="gate_decision_status_must_be_known",
                detail=f"Unknown decision status: {payload['decision_status']}",
            )
        if payload["execution_status"] != "succeeded" and payload[
            "decision_status"
        ] in {"PASS", "UPDATED"}:
            fail(
                artifact_id=artifact_id,
                field="payload.decision_status",
                invariant="unsuccessful_gate_execution_cannot_pass",
                detail="Failed or unavailable execution cannot be PASS/UPDATED",
            )
        require_bool(
            payload["mutated_target"],
            artifact_id=artifact_id,
            field="payload.mutated_target",
        )
        for field_name in (
            "acceptance_policy_ref",
            "evidence_ref",
            "pre_target_check_ref",
            "post_target_check_ref",
        ):
            ref = payload[field_name]
            if ref is not None:
                validate_common_ref(
                    ref,
                    field=f"payload.{field_name}",
                    run_id=run_id,
                    containing_artifact_id=artifact_id,
                )
        if payload["decision_policy"] not in {"native_status", "project_or_human"}:
            fail(
                artifact_id=artifact_id,
                field="payload.decision_policy",
                invariant="gate_decision_policy_must_be_known",
                detail=f"Unknown gate decision policy: {payload['decision_policy']}",
            )
        if (
            payload["decision_policy"] == "project_or_human"
            and payload["acceptance_policy_ref"] is None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.acceptance_policy_ref",
                invariant="project_or_human_gate_must_reference_policy",
                detail="Project or Human gate requires an acceptance policy ref",
            )
    elif artifact_type == "blind_review":
        validate_ref_array(
            payload["blind_received_artifacts"],
            field="payload.blind_received_artifacts",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        require_dict(
            payload["blind_result"],
            artifact_id=artifact_id,
            field="payload.blind_result",
        )
        require_dict(
            payload["generic_risk_result"],
            artifact_id=artifact_id,
            field="payload.generic_risk_result",
        )
        for field_name in ("generic_coverage_status", "project_coverage_status"):
            require_string(
                payload[field_name],
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
            )
        if payload["generic_coverage_status"] not in {"Complete", "Incomplete"}:
            fail(
                artifact_id=artifact_id,
                field="payload.generic_coverage_status",
                invariant="generic_coverage_status_must_be_known",
                detail=f"Unknown generic coverage: {payload['generic_coverage_status']}",
            )
        if payload["project_coverage_status"] not in {
            "Complete",
            "Incomplete",
            "not_required",
        }:
            fail(
                artifact_id=artifact_id,
                field="payload.project_coverage_status",
                invariant="project_coverage_status_must_be_known",
                detail=f"Unknown project coverage: {payload['project_coverage_status']}",
            )
        _validate_project_results(
            payload["project_results"],
            artifact_id=artifact_id,
            field="payload.project_results",
        )
        _validate_required_gates(
            payload["required_gates"],
            artifact_id=artifact_id,
            field="payload.required_gates",
            run_id=run_id,
        )
        _validate_independence_check(
            payload["independence_check"],
            artifact_id=artifact_id,
            field="payload.independence_check",
        )
    elif artifact_type == "final_review":
        validate_common_ref(
            payload["blind_review_ref"],
            field="payload.blind_review_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        if payload["previous_review_ref"] is not None:
            validate_common_ref(
                payload["previous_review_ref"],
                field="payload.previous_review_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        if payload["remediation_status"] not in {"required", "not_required"}:
            fail(
                artifact_id=artifact_id,
                field="payload.remediation_status",
                invariant="remediation_status_must_be_known",
                detail=f"Unknown remediation status: {payload['remediation_status']}",
            )
        refs = validate_ref_array(
            payload["remediation_refs"],
            field="payload.remediation_refs",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        if payload["remediation_status"] == "not_required" and refs:
            fail(
                artifact_id=artifact_id,
                field="payload.remediation_refs",
                invariant="not_required_remediation_must_have_no_refs",
                detail="No remediation refs are allowed when remediation was not required",
            )
        _validate_reconciliation(
            payload["reconciliation"],
            artifact_id=artifact_id,
            field="payload.reconciliation",
            run_id=run_id,
        )
        blocking_ids = _validate_sorted_unique_strings(
            payload["blocking_finding_ids"],
            artifact_id=artifact_id,
            field="payload.blocking_finding_ids",
        )
        current_blocking_ids = [
            item["finding_id"]
            for item in payload["reconciliation"]["current_findings"]
            if item["blocking"]
        ]
        if blocking_ids != current_blocking_ids:
            fail(
                artifact_id=artifact_id,
                field="payload.blocking_finding_ids",
                invariant="final_blocking_findings_must_match_current_findings",
                detail=(
                    "Final blocking finding IDs must equal current findings marked "
                    "blocking"
                ),
            )
        require_dict(
            payload["popr_result"],
            artifact_id=artifact_id,
            field="payload.popr_result",
        )
        _validate_independence_check(
            payload["independence_check"],
            artifact_id=artifact_id,
            field="payload.independence_check",
        )
    elif artifact_type == "decision":
        decision_kind = require_string(
            payload["decision_kind"],
            artifact_id=artifact_id,
            field="payload.decision_kind",
        )
        if decision_kind == "context_resolution":
            _validate_context_resolution_payload(
                payload, artifact_id=artifact_id, run_id=run_id
            )
        elif decision_kind == "blocker_observation":
            require_exact_fields(
                payload,
                {
                    "decision_kind",
                    "blocked_state",
                    "target_ref",
                    "failure_classification",
                    "attempt",
                    "command_or_tool",
                    "exit_code",
                    "observed_evidence_refs",
                    "required_human_action",
                    "resume_requirement",
                    "resume_state",
                },
                artifact_id=artifact_id,
                field="payload",
            )
            if payload["target_ref"] is not None:
                validate_common_ref(
                    payload["target_ref"],
                    field="payload.target_ref",
                    run_id=run_id,
                    containing_artifact_id=artifact_id,
                )
            if payload["attempt"] is not None:
                require_integer(
                    payload["attempt"],
                    artifact_id=artifact_id,
                    field="payload.attempt",
                )
            if payload["command_or_tool"] is not None:
                require_string(
                    payload["command_or_tool"],
                    artifact_id=artifact_id,
                    field="payload.command_or_tool",
                )
            if payload["exit_code"] is not None and (
                not isinstance(payload["exit_code"], int)
                or isinstance(payload["exit_code"], bool)
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.exit_code",
                    invariant="field_must_be_integer",
                    detail="Process exit code must be an integer or null",
                )
            validate_ref_array(
                payload["observed_evidence_refs"],
                field="payload.observed_evidence_refs",
                run_id=run_id,
                containing_artifact_id=artifact_id,
                allow_empty=False,
            )
            for field_name in (
                "blocked_state",
                "failure_classification",
                "required_human_action",
                "resume_requirement",
            ):
                require_string(
                    payload[field_name],
                    artifact_id=artifact_id,
                    field=f"payload.{field_name}",
                )
            if payload["resume_state"] is not None:
                require_string(
                    payload["resume_state"],
                    artifact_id=artifact_id,
                    field="payload.resume_state",
                )
        elif decision_kind == "limit_observation":
            _validate_limit_observation_payload(
                payload, artifact_id=artifact_id, run_id=run_id
            )
        else:
            fail(
                artifact_id=artifact_id,
                field="payload.decision_kind",
                invariant="decision_kind_must_be_known",
                detail=f"Unknown decision kind: {decision_kind}",
            )


def _validate_blocker(
    payload: dict[str, Any],
    *,
    artifact_id: str,
    run_id: str,
) -> None:
    state = payload["state"]
    resume_state = payload["resume_state"]
    blocker = payload["blocker"]
    if state in NORMAL_STATES or state == "READY":
        if resume_state is not None or blocker is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="nonblocker_state_must_not_have_resume_or_blocker",
                detail=f"State {state} requires null resume_state and blocker",
            )
        return
    if state not in BLOCKER_RULES:
        fail(
            artifact_id=artifact_id,
            field="payload.state",
            invariant="manifest_state_must_be_known",
            detail=f"Unknown state: {state}",
        )
    allowed_classifications, allowed_resume = BLOCKER_RULES[state]
    if resume_state not in allowed_resume:
        fail(
            artifact_id=artifact_id,
            field="payload.resume_state",
            invariant="resume_state_must_match_blocker_state",
            detail=f"Invalid resume state {resume_state!r} for {state}",
        )
    blocker_value = require_dict(
        blocker, artifact_id=artifact_id, field="payload.blocker"
    )
    require_exact_fields(
        blocker_value,
        {
            "failure_classification",
            "cause_ref",
            "observed_evidence_refs",
            "required_human_action",
            "resume_requirement",
        },
        artifact_id=artifact_id,
        field="payload.blocker",
    )
    if blocker_value["failure_classification"] not in allowed_classifications:
        fail(
            artifact_id=artifact_id,
            field="payload.blocker.failure_classification",
            invariant="failure_classification_must_match_blocker_state",
            detail=f"Invalid classification for {state}: {blocker_value['failure_classification']}",
        )
    validate_common_ref(
        blocker_value["cause_ref"],
        field="payload.blocker.cause_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    validate_ref_array(
        blocker_value["observed_evidence_refs"],
        field="payload.blocker.observed_evidence_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
        allow_empty=False,
    )
    required_human_action = require_string(
        blocker_value["required_human_action"],
        artifact_id=artifact_id,
        field="payload.blocker.required_human_action",
    )
    resume_requirement = require_string(
        blocker_value["resume_requirement"],
        artifact_id=artifact_id,
        field="payload.blocker.resume_requirement",
    )
    expected_action, expected_requirement = BLOCKER_ACTIONS[state]
    if (
        required_human_action != expected_action
        or resume_requirement != expected_requirement
    ):
        fail(
            artifact_id=artifact_id,
            field="payload.blocker",
            invariant="blocker_action_and_resume_requirement_must_match_state",
            detail=(
                f"Expected action {expected_action!r} and requirement "
                f"{expected_requirement!r}"
            ),
        )
    if blocker_value["cause_ref"] != payload["transition_cause_ref"]:
        fail(
            artifact_id=artifact_id,
            field="payload.blocker.cause_ref",
            invariant="blocker_cause_must_match_transition_cause",
            detail="Blocker cause ref differs from Manifest transition cause ref",
        )


def _validate_manifest(
    payload: dict[str, Any], *, artifact_id: str, run_id: str
) -> None:
    """実行状態の記録が状態遷移と再開契約を満たすか検証する。

    Args:
        payload: 実行状態の記録本体。
        artifact_id: エラーに含める作業記録ID。
        run_id: 参照先に要求する実行ID。

    Raises:
        ArtifactError: 改訂番号、状態、対象、参照、上限、再開情報が不正な場合。
    """
    required = {
        "revision",
        "previous_manifest_ref",
        "state",
        "previous_state",
        "transition_id",
        "transition_cause_ref",
        "repository_identity_ref",
        "target_status",
        "target_absence_reason",
        "current_target_generation",
        "current_target_ref",
        "input_refs",
        "permission_set_ref",
        "artifact_refs",
        "limits",
        "counters",
        "input_source",
        "issue_ref",
        "scope_input_ref",
        "contract_status",
        "contract_ref",
        "context_status",
        "resolution_mode",
        "pending_reason_refs",
        "conflict_refs",
        "project_context_refs",
        "context_resolution_ref",
        "last_completed_stage",
        "resume_state",
        "blocker",
    }
    require_exact_fields(payload, required, artifact_id=artifact_id, field="payload")
    revision = require_integer(
        payload["revision"], artifact_id=artifact_id, field="payload.revision"
    )
    if revision == 0:
        if (
            payload["previous_manifest_ref"] is not None
            or payload["previous_state"] is not None
            or payload["state"] != "CONTEXT_RESOLVING"
        ):
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="initial_manifest_must_start_context_resolution",
                detail="Revision 0 requires null previous manifest/state and CONTEXT_RESOLVING",
            )
    else:
        validate_common_ref(
            payload["previous_manifest_ref"],
            field="payload.previous_manifest_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        if payload["previous_state"] not in ALL_STATES:
            fail(
                artifact_id=artifact_id,
                field="payload.previous_state",
                invariant="previous_state_must_be_known",
                detail=f"Unknown previous state: {payload['previous_state']}",
            )
    if payload["state"] not in ALL_STATES:
        fail(
            artifact_id=artifact_id,
            field="payload.state",
            invariant="manifest_state_must_be_known",
            detail=f"Unknown state: {payload['state']}",
        )
    require_string(
        payload["transition_id"], artifact_id=artifact_id, field="payload.transition_id"
    )
    if payload["transition_cause_ref"] is not None:
        validate_common_ref(
            payload["transition_cause_ref"],
            field="payload.transition_cause_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    validate_common_ref(
        payload["repository_identity_ref"],
        field="payload.repository_identity_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    envelope_inputs = validate_ref_array(
        payload["input_refs"],
        field="payload.input_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    validate_common_ref(
        payload["permission_set_ref"],
        field="payload.permission_set_ref",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    if payload["target_status"] == "resolved":
        if (
            payload["target_absence_reason"] is not None
            or payload["current_target_ref"] is None
            or payload["current_target_generation"] is None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="resolved_manifest_target_fields_must_be_present",
                detail="Resolved target requires ref/generation and null absence reason",
            )
        validate_common_ref(
            payload["current_target_ref"],
            field="payload.current_target_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        require_integer(
            payload["current_target_generation"],
            artifact_id=artifact_id,
            field="payload.current_target_generation",
        )
    elif payload["target_status"] == "unresolved":
        require_string(
            payload["target_absence_reason"],
            artifact_id=artifact_id,
            field="payload.target_absence_reason",
        )
        if (
            payload["current_target_ref"] is not None
            or payload["current_target_generation"] is not None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="unresolved_manifest_must_not_invent_target",
                detail="Unresolved target requires null target ref and generation",
            )
    else:
        fail(
            artifact_id=artifact_id,
            field="payload.target_status",
            invariant="target_status_must_be_known",
            detail=f"Unknown target status: {payload['target_status']}",
        )
    wrappers = require_list(
        payload["artifact_refs"], artifact_id=artifact_id, field="payload.artifact_refs"
    )
    wrapper_ids: list[str] = []
    for index, wrapper_value in enumerate(wrappers):
        field = f"payload.artifact_refs[{index}]"
        wrapper = require_dict(wrapper_value, artifact_id=artifact_id, field=field)
        require_exact_fields(
            wrapper,
            {"ref", "lifecycle_status", "invalidation_reason_ref"},
            artifact_id=artifact_id,
            field=field,
        )
        ref = validate_common_ref(
            wrapper["ref"],
            field=f"{field}.ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
        wrapper_ids.append(ref["artifact_id"])
        status = wrapper["lifecycle_status"]
        if status not in {"current", "historical", "invalidated"}:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.lifecycle_status",
                invariant="lifecycle_status_must_be_known",
                detail=f"Unknown lifecycle status: {status}",
            )
        reason_ref = wrapper["invalidation_reason_ref"]
        if status == "invalidated":
            validate_common_ref(
                reason_ref,
                field=f"{field}.invalidation_reason_ref",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
        elif reason_ref is not None:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.invalidation_reason_ref",
                invariant="noninvalidated_artifact_must_not_have_invalidation_reason",
                detail="Only invalidated artifacts may have an invalidation reason ref",
            )
    if wrapper_ids != sorted(wrapper_ids) or len(wrapper_ids) != len(set(wrapper_ids)):
        fail(
            artifact_id=artifact_id,
            field="payload.artifact_refs",
            invariant="artifact_refs_must_be_sorted_and_unique",
            detail="Manifest artifact refs must be unique and sorted by artifact_id",
        )
    if payload["input_source"] == "issue":
        if payload["issue_ref"] is None or payload["scope_input_ref"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="issue_input_source_must_have_issue_ref_only",
                detail="Issue input source requires issue_ref and null scope_input_ref",
            )
    elif payload["input_source"] == "explicit_scope":
        if payload["scope_input_ref"] is None or payload["issue_ref"] is not None:
            fail(
                artifact_id=artifact_id,
                field="payload",
                invariant="explicit_scope_input_source_must_have_scope_ref_only",
                detail="Explicit scope requires scope_input_ref and null issue_ref",
            )
    else:
        fail(
            artifact_id=artifact_id,
            field="payload.input_source",
            invariant="input_source_must_be_known",
            detail=f"Unknown input source: {payload['input_source']}",
        )
    if payload["contract_status"] not in {"resolved", "unavailable", "drifted"}:
        fail(
            artifact_id=artifact_id,
            field="payload.contract_status",
            invariant="contract_status_must_be_known",
            detail=f"Unknown contract status: {payload['contract_status']}",
        )
    for field_name in (
        "issue_ref",
        "scope_input_ref",
        "contract_ref",
        "context_resolution_ref",
        "last_completed_stage",
    ):
        ref = payload[field_name]
        if ref is not None:
            validate_common_ref(
                ref,
                field=f"payload.{field_name}",
                run_id=run_id,
                containing_artifact_id=artifact_id,
            )
    pending_reason_refs = validate_ref_array(
        payload["pending_reason_refs"],
        field="payload.pending_reason_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    conflict_refs = validate_ref_array(
        payload["conflict_refs"],
        field="payload.conflict_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    project_context_refs = validate_ref_array(
        payload["project_context_refs"],
        field="payload.project_context_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    if payload["contract_status"] == "resolved":
        if payload["contract_ref"] is None:
            fail(
                artifact_id=artifact_id,
                field="payload.contract_ref",
                invariant="resolved_contract_must_have_contract_ref",
                detail="Resolved contract status requires a contract ref",
            )
    elif payload["contract_ref"] is not None:
        fail(
            artifact_id=artifact_id,
            field="payload.contract_ref",
            invariant="unresolved_contract_must_have_null_contract_ref",
            detail=f"Contract status {payload['contract_status']} requires null contract_ref",
        )
    if payload["context_status"] not in {"resolved", "pending", "conflicted"}:
        fail(
            artifact_id=artifact_id,
            field="payload.context_status",
            invariant="context_status_must_be_known",
            detail=f"Unknown context status: {payload['context_status']}",
        )
    if payload["context_status"] == "resolved":
        if (
            payload["contract_status"] != "resolved"
            or payload["resolution_mode"]
            not in {"repository_baseline", "human_approved_run_local", "mixed"}
            or pending_reason_refs
            or conflict_refs
            or not project_context_refs
            or payload["context_resolution_ref"] is None
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.context_status",
                invariant="resolved_context_must_have_complete_resolution_evidence",
                detail=(
                    "Resolved context requires a resolved contract, allowed resolution mode, "
                    "project context and resolution refs, and no pending/conflict refs"
                ),
            )
    elif payload["context_status"] == "pending":
        if (
            payload["resolution_mode"] is not None
            or not pending_reason_refs
            or conflict_refs
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.context_status",
                invariant="pending_context_must_have_pending_reasons_only",
                detail="Pending context requires null mode, pending refs, and no conflict refs",
            )
    elif (
        payload["resolution_mode"] is not None
        or pending_reason_refs
        or not conflict_refs
    ):
        fail(
            artifact_id=artifact_id,
            field="payload.context_status",
            invariant="conflicted_context_must_have_conflict_refs_only",
            detail="Conflicted context requires null mode, conflict refs, and no pending refs",
        )
    _validate_manifest_limits(payload["limits"], artifact_id=artifact_id)
    _validate_manifest_counters(
        payload["counters"],
        limits=payload["limits"],
        artifact_id=artifact_id,
    )
    _validate_blocker(payload, artifact_id=artifact_id, run_id=run_id)
    if not envelope_inputs:
        fail(
            artifact_id=artifact_id,
            field="payload.input_refs",
            invariant="manifest_input_refs_must_not_be_empty",
            detail="Manifest must bind at least the repository identity input",
        )


def _validate_manifest_limits(value: Any, *, artifact_id: str) -> None:
    limits = require_dict(value, artifact_id=artifact_id, field="payload.limits")
    if set(limits) != MANIFEST_LIMIT_FIELDS:
        fail(
            artifact_id=artifact_id,
            field="payload.limits",
            invariant="manifest_limits_must_use_exact_schema",
            detail=f"Expected exact fields {sorted(MANIFEST_LIMIT_FIELDS)}",
        )
    for field_name in (
        "max_remediation_cycles",
        "max_same_request_attempts",
        "max_transient_stage_retries",
        "paid_external_call_budget",
        "max_changed_files",
        "max_diff_lines",
    ):
        require_integer(
            limits[field_name],
            artifact_id=artifact_id,
            field=f"payload.limits.{field_name}",
        )
    validate_rfc3339(
        limits["deadline_at"],
        artifact_id=artifact_id,
        field="payload.limits.deadline_at",
    )
    token_budget = limits["token_budget"]
    if token_budget != "unsupported":
        require_integer(
            token_budget,
            artifact_id=artifact_id,
            field="payload.limits.token_budget",
        )
    path_values = require_list(
        limits["allowed_write_paths"],
        artifact_id=artifact_id,
        field="payload.limits.allowed_write_paths",
    )
    paths = [
        validate_repository_path(
            path,
            artifact_id=artifact_id,
            field=f"payload.limits.allowed_write_paths[{index}]",
        )
        for index, path in enumerate(path_values)
    ]
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")) or len(
        paths
    ) != len(set(paths)):
        fail(
            artifact_id=artifact_id,
            field="payload.limits.allowed_write_paths",
            invariant="manifest_allowed_write_paths_must_be_sorted_and_unique",
            detail="Allowed write paths must be unique and sorted by UTF-8 bytes",
        )


def _validate_counter_map(
    value: Any,
    *,
    artifact_id: str,
    field: str,
    maximum: int,
) -> None:
    counters = require_dict(value, artifact_id=artifact_id, field=field)
    for key, counter in counters.items():
        require_string(key, artifact_id=artifact_id, field=f"{field}.key")
        count = require_integer(
            counter,
            artifact_id=artifact_id,
            field=f"{field}.{key}",
        )
        if count > maximum:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.{key}",
                invariant="manifest_counter_must_not_exceed_limit",
                detail=f"Counter {count} exceeds limit {maximum}",
            )


def _validate_manifest_counters(value: Any, *, limits: Any, artifact_id: str) -> None:
    counters = require_dict(value, artifact_id=artifact_id, field="payload.counters")
    if set(counters) != MANIFEST_COUNTER_FIELDS:
        fail(
            artifact_id=artifact_id,
            field="payload.counters",
            invariant="manifest_counters_must_use_exact_schema",
            detail=f"Expected exact fields {sorted(MANIFEST_COUNTER_FIELDS)}",
        )
    typed_limits = require_dict(limits, artifact_id=artifact_id, field="payload.limits")
    remediation_cycles = require_integer(
        counters["remediation_cycles_started"],
        artifact_id=artifact_id,
        field="payload.counters.remediation_cycles_started",
    )
    if remediation_cycles > typed_limits["max_remediation_cycles"]:
        fail(
            artifact_id=artifact_id,
            field="payload.counters.remediation_cycles_started",
            invariant="manifest_counter_must_not_exceed_limit",
            detail="Remediation cycle counter exceeds its limit",
        )
    _validate_counter_map(
        counters["remediation_attempts_by_request_id"],
        artifact_id=artifact_id,
        field="payload.counters.remediation_attempts_by_request_id",
        maximum=typed_limits["max_same_request_attempts"],
    )
    _validate_counter_map(
        counters["transient_retries_by_execution_key"],
        artifact_id=artifact_id,
        field="payload.counters.transient_retries_by_execution_key",
        maximum=typed_limits["max_transient_stage_retries"],
    )
    tokens_used = counters["tokens_used"]
    token_budget = typed_limits["token_budget"]
    if (tokens_used == "unsupported") != (token_budget == "unsupported"):
        fail(
            artifact_id=artifact_id,
            field="payload.counters.tokens_used",
            invariant="token_counter_and_budget_support_must_match",
            detail="Token usage and budget must both be integers or both unsupported",
        )
    if tokens_used != "unsupported":
        token_count = require_integer(
            tokens_used,
            artifact_id=artifact_id,
            field="payload.counters.tokens_used",
        )
        if token_count > token_budget:
            fail(
                artifact_id=artifact_id,
                field="payload.counters.tokens_used",
                invariant="manifest_counter_must_not_exceed_limit",
                detail="Token usage exceeds its budget",
            )
    paid_calls = require_integer(
        counters["paid_external_calls"],
        artifact_id=artifact_id,
        field="payload.counters.paid_external_calls",
    )
    if paid_calls > typed_limits["paid_external_call_budget"]:
        fail(
            artifact_id=artifact_id,
            field="payload.counters.paid_external_calls",
            invariant="manifest_counter_must_not_exceed_limit",
            detail="Paid external call count exceeds its budget",
        )


def validate_artifact_shape(
    value: Any, *, expected_path: str | None = None
) -> dict[str, Any]:
    """作業記録全体を共通形式と種別固有契約の両方で検証する。

    Args:
        value: 検証する作業記録。
        expected_path: 記録IDから導くパスと照合する保存先。指定時のみ照合する。

    Returns:
        検証済みの作業記録。

    Raises:
        ArtifactError: 共通項目、種別固有項目、参照、または保存先が不正な場合。
    """
    artifact = require_dict(value, artifact_id=None, field="$")
    envelope_fields = {
        "schema_version",
        "artifact_type",
        "artifact_id",
        "run_id",
        "monotonic_sequence",
        "stage",
        "target_ref",
        "producer",
        "input_refs",
        "created_at",
        "payload",
    }
    artifact_id_hint = (
        artifact.get("artifact_id")
        if isinstance(artifact.get("artifact_id"), str)
        else None
    )
    require_exact_fields(
        artifact, envelope_fields, artifact_id=artifact_id_hint, field="$"
    )
    if artifact["schema_version"] != SCHEMA_VERSION:
        fail(
            artifact_id=artifact_id_hint,
            field="schema_version",
            invariant="artifact_schema_version_must_match_contract",
            detail=f"Expected {SCHEMA_VERSION}, got {artifact['schema_version']}",
        )
    artifact_type = artifact["artifact_type"]
    if artifact_type not in ARTIFACT_TYPES:
        fail(
            artifact_id=artifact_id_hint,
            field="artifact_type",
            invariant="artifact_type_must_be_known",
            detail=f"Unknown artifact type: {artifact_type}",
        )
    run_id = validate_identifier(
        artifact["run_id"], field="run_id", artifact_id=artifact_id_hint
    )
    sequence = require_integer(
        artifact["monotonic_sequence"],
        artifact_id=artifact_id_hint,
        field="monotonic_sequence",
    )
    artifact_id = require_string(
        artifact["artifact_id"], artifact_id=artifact_id_hint, field="artifact_id"
    )
    expected_id = f"{run_id}/{artifact['stage']}/{sequence}"
    if artifact_id != expected_id:
        fail(
            artifact_id=artifact_id,
            field="artifact_id",
            invariant="artifact_id_must_match_run_stage_sequence",
            detail=f"Expected {expected_id}, got {artifact_id}",
        )
    if artifact["stage"] not in ALL_STATES:
        fail(
            artifact_id=artifact_id,
            field="stage",
            invariant="artifact_stage_must_be_known_state",
            detail=f"Unknown stage: {artifact['stage']}",
        )
    if artifact["stage"] not in ARTIFACT_ALLOWED_STAGES[artifact_type]:
        fail(
            artifact_id=artifact_id,
            field="stage",
            invariant="artifact_type_must_use_allowed_stage",
            detail=f"{artifact_type} cannot be created in {artifact['stage']}",
        )
    _validate_producer(artifact["producer"], artifact_id=artifact_id, run_id=run_id)
    input_refs = validate_ref_array(
        artifact["input_refs"],
        field="input_refs",
        run_id=run_id,
        containing_artifact_id=artifact_id,
    )
    validate_rfc3339(
        artifact["created_at"], artifact_id=artifact_id, field="created_at"
    )
    payload = require_dict(
        artifact["payload"], artifact_id=artifact_id, field="payload"
    )
    target_ref = artifact["target_ref"]
    if artifact_type in ROOT_TYPES:
        if target_ref is not None:
            fail(
                artifact_id=artifact_id,
                field="target_ref",
                invariant="root_artifact_target_ref_must_be_null",
                detail=f"{artifact_type} must not have a target ref",
            )
    elif target_ref is None:
        unresolved_allowed = (
            artifact_type in {"decision", "run_manifest"}
            and payload.get("target_status") == "unresolved"
            and bool(payload.get("target_absence_reason"))
        )
        if not unresolved_allowed:
            fail(
                artifact_id=artifact_id,
                field="target_ref",
                invariant="target_dependent_artifact_must_have_target_ref",
                detail=f"{artifact_type} requires a target ref",
            )
    else:
        validate_common_ref(
            target_ref,
            field="target_ref",
            run_id=run_id,
            containing_artifact_id=artifact_id,
        )
    if artifact_type == "input_snapshot":
        if input_refs:
            fail(
                artifact_id=artifact_id,
                field="input_refs",
                invariant="input_snapshot_must_not_reference_other_artifacts",
                detail="Input snapshots are Root artifacts and require empty input_refs",
            )
        _validate_input_snapshot(payload, artifact_id=artifact_id)
    elif artifact_type == "target":
        if len(input_refs) != 1:
            fail(
                artifact_id=artifact_id,
                field="input_refs",
                invariant="target_must_reference_repository_identity_only",
                detail="Target requires exactly one repository identity input ref",
            )
        _validate_target(payload, artifact_id=artifact_id, run_id=run_id)
        if payload["repository_identity_ref"] != input_refs[0]:
            fail(
                artifact_id=artifact_id,
                field="payload.repository_identity_ref",
                invariant="target_repository_identity_ref_must_match_input_refs",
                detail="Target repository identity ref differs from its single input ref",
            )
    elif artifact_type == "evidence":
        _validate_evidence(payload, artifact_id=artifact_id, run_id=run_id)
    elif artifact_type == "run_manifest":
        _validate_manifest(payload, artifact_id=artifact_id, run_id=run_id)
        if artifact["stage"] != payload["state"]:
            fail(
                artifact_id=artifact_id,
                field="stage",
                invariant="manifest_stage_must_match_payload_state",
                detail=f"Stage {artifact['stage']} differs from state {payload['state']}",
            )
        if artifact["input_refs"] != payload["input_refs"]:
            fail(
                artifact_id=artifact_id,
                field="input_refs",
                invariant="manifest_envelope_and_payload_input_refs_must_match",
                detail="Manifest input refs differ between envelope and payload",
            )
        if (
            payload["target_status"] == "resolved"
            and artifact["target_ref"] != payload["current_target_ref"]
        ):
            fail(
                artifact_id=artifact_id,
                field="target_ref",
                invariant="manifest_envelope_and_payload_target_ref_must_match",
                detail="Manifest target refs differ between envelope and payload",
            )
    else:
        _validate_stage_payload(
            artifact_type, payload, artifact_id=artifact_id, run_id=run_id
        )
    canonical_bytes = canonicalize(artifact)
    expected = (
        manifest_path(payload["revision"])
        if artifact_type == "run_manifest"
        else object_path(sha256_hex(canonical_bytes))
    )
    if expected_path is not None and expected_path != expected:
        fail(
            artifact_id=artifact_id,
            field="artifact_path",
            invariant="artifact_path_must_match_canonical_destination",
            detail=f"Expected {expected}, got {expected_path}",
        )
    return artifact


def artifact_common_ref(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """検証済みの作業記録から共通参照を生成する。

    Args:
        artifact: 共通参照へ変換する作業記録。

    Returns:
        ID、保存先、内容ハッシュを持つ共通参照。
    """
    content = canonicalize(dict(artifact))
    content_hash = sha256_hex(content)
    payload = require_dict(
        artifact.get("payload"),
        artifact_id=artifact.get("artifact_id"),
        field="payload",
    )
    path = (
        manifest_path(payload["revision"])
        if artifact.get("artifact_type") == "run_manifest"
        else object_path(content_hash)
    )
    return {
        "artifact_id": artifact["artifact_id"],
        "artifact_path": path,
        "sha256": content_hash,
    }


def iter_common_refs(
    value: Any, *, field: str = "$"
) -> Iterator[tuple[str, dict[str, Any]]]:
    """入れ子構造から共通参照と同じ形の辞書を場所付きで順に返す。

    Args:
        value: 探索する値。
        field: 探索開始位置を表すフィールド名。

    Yields:
        見つかった位置と、ID、保存先、内容ハッシュだけを持つ辞書の組。
    """

    if isinstance(value, dict):
        if set(value) == {"artifact_id", "artifact_path", "sha256"}:
            yield field, value
            return
        for key, item in value.items():
            yield from iter_common_refs(item, field=f"{field}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_common_refs(item, field=f"{field}[{index}]")


def lifecycle_map(
    manifest: Mapping[str, Any],
) -> dict[str, tuple[str, dict[str, Any] | None]]:
    """実行状態の記録から各作業記録の有効状態を取り出す。

    Args:
        manifest: `artifact_lifecycle`を含む実行状態の記録。

    Returns:
        作業記録IDを有効状態と無効化原因の組へ対応付けた辞書。
    """
    payload = manifest["payload"]
    return {
        wrapper["ref"]["artifact_id"]: (
            wrapper["lifecycle_status"],
            wrapper["invalidation_reason_ref"],
        )
        for wrapper in payload["artifact_refs"]
    }


def state_transition_is_allowed(previous: str, current: str) -> bool:
    """指定した状態遷移が許可一覧に含まれるか返す。

    Args:
        previous: 遷移前の状態。
        current: 遷移後の状態。

    Returns:
        許可された遷移なら`True`。
    """
    if previous == current and previous not in {"READY", "BUDGET_EXHAUSTED"}:
        return True
    return current in ALLOWED_STATE_TRANSITIONS.get(previous, set())
