"""Read-only validation for one canonical Harness run ledger."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import Any

from .canonical import (
    canonicalize,
    git_blob_oid,
    manifest_path,
    object_path,
    require_canonical_json,
    sha256_hex,
)
from .contract import (
    EVIDENCE_TYPES,
    READY_GATE_SUCCESS_STATUSES,
    ROOT_TYPES,
    STAGE_TYPES,
    artifact_common_ref,
    iter_common_refs,
    lifecycle_map,
    require_dict,
    require_exact_fields,
    require_integer,
    require_list,
    require_string,
    state_transition_is_allowed,
    validate_artifact_shape,
    validate_common_ref,
    validate_identifier,
    validate_repository_id,
)
from .errors import fail
from .safe_fs import SafeDirectory

MANIFEST_FILE_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.json\Z")
SECURITY_CATEGORY_WEIGHTS = [
    ("authentication_session", 25),
    ("authorization_access_control", 20),
    ("csrf_transport", 15),
    ("input_validation_injection", 20),
    ("infrastructure_server_configuration", 10),
    ("logging_monitoring_information_disclosure", 10),
]
SECURITY_SEVERITIES = {"Critical", "High", "Medium", "Low"}


@dataclass(slots=True)
class LedgerSnapshot:
    repository_id: str
    run_id: str
    head: dict[str, Any]
    head_bytes: bytes
    manifests: list[dict[str, Any]]
    manifest_bytes: dict[int, bytes]
    artifacts: dict[str, dict[str, Any]]
    artifact_bytes: dict[str, bytes]
    artifact_refs: dict[str, dict[str, Any]]
    max_sequence: int
    diagnostics: list[str] = field(default_factory=list)


def initial_head() -> dict[str, Any]:
    return {"revision": -1, "manifest_ref": None}


def initial_head_bytes() -> bytes:
    return canonicalize(initial_head())


def validate_head(value: Any) -> dict[str, Any]:
    head = require_dict(value, artifact_id=None, field="HEAD.json")
    require_exact_fields(
        head,
        {"revision", "manifest_ref"},
        artifact_id=None,
        field="HEAD.json",
    )
    revision = head["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < -1:
        fail(
            artifact_id=None,
            field="HEAD.json.revision",
            invariant="head_revision_must_be_minus_one_or_nonnegative_integer",
            detail=f"Invalid HEAD revision: {revision!r}",
        )
    if revision == -1:
        if head["manifest_ref"] is not None:
            fail(
                artifact_id=None,
                field="HEAD.json.manifest_ref",
                invariant="initial_head_must_have_null_manifest_ref",
                detail="HEAD revision -1 requires a null manifest ref",
            )
    else:
        validate_common_ref(head["manifest_ref"], field="HEAD.json.manifest_ref")
    return head


class _LedgerReader:
    def __init__(
        self, store: SafeDirectory, overlay: dict[str, bytes] | None = None
    ) -> None:
        self.store = store
        self.overlay = overlay or {}

    def read(self, path: str) -> bytes:
        if path in self.overlay:
            return self.overlay[path]
        return self.store.read_bytes(path)

    def manifest_names(self) -> list[str]:
        names = set(self.store.list_names("manifests"))
        names.update(
            path.removeprefix("manifests/")
            for path in self.overlay
            if path.startswith("manifests/")
            and "/" not in path.removeprefix("manifests/")
        )
        return sorted(names)


def active_transaction_ids(store: SafeDirectory) -> list[str]:
    active: list[str] = []
    for transaction_id in store.list_names("transactions"):
        validate_identifier(transaction_id, field="transactions.transaction_id")
        descriptor = f"transactions/{transaction_id}/descriptor.json"
        marker = f"transactions/{transaction_id}/committed.json"
        if store.exists(descriptor) and not store.exists(marker):
            active.append(transaction_id)
    return active


def descriptorless_transaction_ids(store: SafeDirectory) -> list[str]:
    transaction_ids: list[str] = []
    for transaction_id in store.list_names("transactions"):
        validate_identifier(transaction_id, field="transactions.transaction_id")
        descriptor_path = f"transactions/{transaction_id}/descriptor.json"
        if not store.exists(descriptor_path):
            transaction_ids.append(transaction_id)
    return transaction_ids


def _validate_transaction_records(
    store: SafeDirectory,
    *,
    repository_id: str,
    run_id: str,
) -> dict[int, tuple[dict[str, Any], bool, str]]:
    """Validate immutable descriptors and commit markers without changing the store."""

    from .writer import validate_descriptor, validate_descriptor_files, validate_marker

    descriptorless = descriptorless_transaction_ids(store)
    if descriptorless:
        fail(
            artifact_id=None,
            field="transactions",
            invariant="transaction_directory_requires_published_descriptor",
            detail=(
                f"Transaction directories without descriptor.json: {descriptorless}"
            ),
        )
    revision_records: dict[int, tuple[dict[str, Any], bool, str]] = {}
    for transaction_id in store.list_names("transactions"):
        validate_identifier(transaction_id, field="transactions.transaction_id")
        descriptor_path = f"transactions/{transaction_id}/descriptor.json"
        marker_path = f"transactions/{transaction_id}/committed.json"
        has_descriptor = store.exists(descriptor_path)
        has_marker = store.exists(marker_path)
        if has_marker and not has_descriptor:
            fail(
                artifact_id=None,
                field=marker_path,
                invariant="commit_marker_requires_immutable_descriptor",
                detail="Commit marker exists without descriptor.json",
            )
        if not has_descriptor:
            continue
        descriptor_bytes = store.read_bytes(descriptor_path)
        descriptor = validate_descriptor(
            require_canonical_json(descriptor_bytes, field=descriptor_path)
        )
        if descriptor["transaction_id"] != transaction_id:
            fail(
                artifact_id=None,
                field=f"{descriptor_path}.transaction_id",
                invariant="descriptor_transaction_id_must_match_directory",
                detail=f"Expected {transaction_id}, got {descriptor['transaction_id']}",
            )
        if (
            descriptor["repository_id"] != repository_id
            or descriptor["run_id"] != run_id
        ):
            fail(
                artifact_id=None,
                field=descriptor_path,
                invariant="descriptor_scope_must_match_run_directory",
                detail="Descriptor repository_id/run_id differs from its run directory",
            )
        validate_descriptor_files(store, descriptor)
        revision = descriptor["next_manifest_revision"]
        prior_record = revision_records.get(revision)
        if prior_record is not None:
            fail(
                artifact_id=None,
                field="transactions",
                invariant="manifest_revision_must_have_one_transaction_descriptor",
                detail=f"Revision {revision} appears in {prior_record[2]} and {transaction_id}",
            )
        revision_records[revision] = (descriptor, has_marker, transaction_id)
        if not has_marker:
            continue
        marker = validate_marker(
            require_canonical_json(store.read_bytes(marker_path), field=marker_path),
            descriptor=descriptor,
            descriptor_bytes=descriptor_bytes,
        )
        del marker
        for write in descriptor["writes"]:
            installed = store.read_bytes(write["destination_path"])
            if (
                len(installed) != write["byte_length"]
                or sha256_hex(installed) != write["sha256"]
            ):
                fail(
                    artifact_id=write["artifact_id"],
                    field=write["destination_path"],
                    invariant="committed_destination_must_match_descriptor",
                    detail="Installed bytes differ from committed descriptor",
                )
    return revision_records


def _validate_manifest_transaction_correspondence(
    manifests: list[dict[str, Any]],
    records: dict[int, tuple[dict[str, Any], bool, str]],
    *,
    overlay: dict[str, bytes] | None,
) -> None:
    for revision, manifest in enumerate(manifests):
        record = records.get(revision)
        if record is None:
            is_unrecorded_append_preflight = (
                overlay is not None
                and revision == len(manifests) - 1
                and manifest_path(revision) in overlay
            )
            if is_unrecorded_append_preflight:
                continue
            fail(
                artifact_id=manifest["artifact_id"],
                field=manifest_path(revision),
                invariant="manifest_must_have_transaction_descriptor",
                detail=f"Revision {revision} is not explained by an immutable descriptor",
            )
        descriptor, committed, transaction_id = record
        expected_head = (
            initial_head()
            if revision == 0
            else {
                "revision": revision - 1,
                "manifest_ref": artifact_common_ref(manifests[revision - 1]),
            }
        )
        proposed_head = {
            "revision": revision,
            "manifest_ref": artifact_common_ref(manifest),
        }
        if (
            descriptor["expected_head"] != expected_head
            or descriptor["proposed_head"] != proposed_head
        ):
            fail(
                artifact_id=manifest["artifact_id"],
                field=f"transactions/{transaction_id}/descriptor.json",
                invariant="transaction_heads_must_match_manifest_chain",
                detail=f"Descriptor heads do not explain revision {revision}",
            )
        if not committed and overlay is None:
            fail(
                artifact_id=manifest["artifact_id"],
                field=f"transactions/{transaction_id}/committed.json",
                invariant="visible_manifest_requires_commit_marker",
                detail=f"Revision {revision} is visible without a commit marker",
            )
    extra_revisions = sorted(set(records) - set(range(len(manifests))))
    if extra_revisions:
        fail(
            artifact_id=None,
            field="transactions",
            invariant="transaction_descriptor_revision_must_be_in_manifest_chain",
            detail=f"Descriptor revisions are outside the proposed chain: {extra_revisions}",
        )


def _load_manifest_chain(
    reader: _LedgerReader,
    *,
    run_id: str,
    head: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, bytes]]:
    names = reader.manifest_names()
    for name in names:
        if MANIFEST_FILE_PATTERN.fullmatch(name) is None:
            fail(
                artifact_id=None,
                field=f"manifests/{name}",
                invariant="manifest_filename_must_be_canonical_revision",
                detail=f"Unexpected manifest filename: {name}",
            )
    revisions = sorted(int(name.removesuffix(".json")) for name in names)
    if head["revision"] == -1:
        if revisions:
            fail(
                artifact_id=None,
                field="manifests",
                invariant="empty_head_must_not_have_manifests",
                detail=f"Found manifests with initial HEAD: {revisions}",
            )
        return [], {}
    expected_revisions = list(range(head["revision"] + 1))
    if revisions != expected_revisions:
        fail(
            artifact_id=None,
            field="manifests",
            invariant="manifest_revisions_must_be_unique_contiguous_and_match_head",
            detail=f"Expected revisions {expected_revisions}, found {revisions}",
        )
    manifests: list[dict[str, Any]] = []
    manifest_bytes: dict[int, bytes] = {}
    for revision in revisions:
        path = manifest_path(revision)
        content = reader.read(path)
        manifest = validate_artifact_shape(
            require_canonical_json(content, field=path),
            expected_path=path,
        )
        if manifest["artifact_type"] != "run_manifest":
            fail(
                artifact_id=manifest["artifact_id"],
                field="artifact_type",
                invariant="manifest_file_must_contain_run_manifest",
                detail=f"Found {manifest['artifact_type']} in {path}",
            )
        if manifest["run_id"] != run_id:
            fail(
                artifact_id=manifest["artifact_id"],
                field="run_id",
                invariant="manifest_run_id_must_match_run_directory",
                detail=f"Expected {run_id}, got {manifest['run_id']}",
            )
        if manifest["payload"]["revision"] != revision:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.revision",
                invariant="manifest_payload_revision_must_match_filename",
                detail=f"Expected {revision}, got {manifest['payload']['revision']}",
            )
        manifests.append(manifest)
        manifest_bytes[revision] = content
    latest_ref = artifact_common_ref(manifests[-1])
    if head["manifest_ref"] != latest_ref:
        fail(
            artifact_id=manifests[-1]["artifact_id"],
            field="HEAD.json.manifest_ref",
            invariant="head_must_reference_latest_manifest_exactly",
            detail=f"Expected {latest_ref}, got {head['manifest_ref']}",
        )
    for revision, manifest in enumerate(manifests):
        if revision == 0:
            continue
        previous_ref = artifact_common_ref(manifests[revision - 1])
        if manifest["payload"]["previous_manifest_ref"] != previous_ref:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.previous_manifest_ref",
                invariant="manifest_must_reference_immediate_previous_revision",
                detail=f"Expected {previous_ref}, got {manifest['payload']['previous_manifest_ref']}",
            )
        previous_state = manifests[revision - 1]["payload"]["state"]
        if manifest["payload"]["previous_state"] != previous_state:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.previous_state",
                invariant="manifest_previous_state_must_match_previous_manifest",
                detail=f"Expected {previous_state}, got {manifest['payload']['previous_state']}",
            )
        current_state = manifest["payload"]["state"]
        if not state_transition_is_allowed(previous_state, current_state):
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.state",
                invariant="manifest_state_transition_must_be_allowed",
                detail=f"Transition {previous_state} -> {current_state} is not allowed",
            )
    return manifests, manifest_bytes


def _load_artifacts(
    reader: _LedgerReader,
    manifests: list[dict[str, Any]],
    *,
    run_id: str,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, bytes],
    dict[str, dict[str, Any]],
]:
    artifacts: dict[str, dict[str, Any]] = {}
    artifact_bytes: dict[str, bytes] = {}
    artifact_refs: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        for wrapper in manifest["payload"]["artifact_refs"]:
            ref = wrapper["ref"]
            artifact_id = ref["artifact_id"]
            existing_ref = artifact_refs.get(artifact_id)
            if existing_ref is not None and existing_ref != ref:
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.artifact_refs",
                    invariant="artifact_id_must_have_one_immutable_common_ref",
                    detail=f"Artifact {artifact_id} changed common ref",
                )
            if existing_ref is not None:
                continue
            content = reader.read(ref["artifact_path"])
            actual_hash = sha256_hex(content)
            if actual_hash != ref["sha256"]:
                fail(
                    artifact_id=artifact_id,
                    field="sha256",
                    invariant="artifact_ref_hash_must_match_saved_bytes",
                    detail=f"Expected {ref['sha256']}, got {actual_hash}",
                )
            artifact = validate_artifact_shape(
                require_canonical_json(content, field=ref["artifact_path"]),
                expected_path=ref["artifact_path"],
            )
            if artifact["artifact_id"] != artifact_id:
                fail(
                    artifact_id=artifact_id,
                    field="artifact_id",
                    invariant="artifact_ref_id_must_match_saved_artifact",
                    detail=f"Saved artifact ID is {artifact['artifact_id']}",
                )
            if artifact["artifact_type"] == "run_manifest":
                fail(
                    artifact_id=artifact_id,
                    field="artifact_type",
                    invariant="manifest_must_not_appear_in_artifact_refs",
                    detail="Run manifests are linked only by previous_manifest_ref",
                )
            if artifact["run_id"] != run_id:
                fail(
                    artifact_id=artifact_id,
                    field="run_id",
                    invariant="artifact_run_id_must_match_run_directory",
                    detail=f"Expected {run_id}, got {artifact['run_id']}",
                )
            artifacts[artifact_id] = artifact
            artifact_bytes[artifact_id] = content
            artifact_refs[artifact_id] = ref
    return artifacts, artifact_bytes, artifact_refs


def _require_counter_map_non_decreasing(
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
    manifest: dict[str, Any],
    field: str,
) -> None:
    missing_keys = sorted(previous.keys() - current.keys())
    decreased_keys = sorted(
        key for key in previous.keys() & current.keys() if current[key] < previous[key]
    )
    if missing_keys or decreased_keys:
        fail(
            artifact_id=manifest["artifact_id"],
            field=field,
            invariant="manifest_counter_maps_must_be_append_only_and_non_decreasing",
            detail=f"Missing keys {missing_keys}; decreased keys {decreased_keys}",
        )


def _validate_manifest_limits_and_counters(
    manifests: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    if not manifests:
        return
    initial_payload = manifests[0]["payload"]
    try:
        deadline_at = datetime.fromisoformat(
            initial_payload["limits"]["deadline_at"].replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as error:
        fail(
            artifact_id=manifests[0]["artifact_id"],
            field="payload.limits.deadline_at",
            invariant="manifest_deadline_must_be_rfc3339",
            detail=str(error),
        )
    for manifest in manifests:
        try:
            created_at = datetime.fromisoformat(
                manifest["created_at"].replace("Z", "+00:00")
            )
            deadline_reached = created_at >= deadline_at
        except (AttributeError, TypeError, ValueError) as error:
            fail(
                artifact_id=manifest["artifact_id"],
                field="created_at",
                invariant="manifest_created_at_must_be_rfc3339",
                detail=str(error),
            )
        payload = manifest["payload"]
        blocker = payload["blocker"]
        if deadline_reached and (
            payload["state"] != "BUDGET_EXHAUSTED"
            or blocker is None
            or blocker["failure_classification"] != "deadline_exhausted"
        ):
            fail(
                artifact_id=manifest["artifact_id"],
                field="created_at",
                invariant="manifest_after_deadline_must_stop_for_deadline",
                detail=(
                    f"Manifest created at {manifest['created_at']} reached deadline "
                    f"{initial_payload['limits']['deadline_at']} without a deadline stop"
                ),
            )
    if initial_payload["counters"]["remediation_cycles_started"] != 0:
        fail(
            artifact_id=manifests[0]["artifact_id"],
            field="payload.counters.remediation_cycles_started",
            invariant="initial_manifest_counters_must_start_at_zero",
            detail="Initial remediation cycle counter must be zero",
        )
    initial_counters = initial_payload["counters"]
    if (
        initial_counters["remediation_attempts_by_request_id"]
        or initial_counters["transient_retries_by_execution_key"]
        or initial_counters["paid_external_calls"] != 0
        or initial_counters["tokens_used"] not in {0, "unsupported"}
    ):
        fail(
            artifact_id=manifests[0]["artifact_id"],
            field="payload.counters",
            invariant="initial_manifest_counters_must_start_at_zero",
            detail="Initial run counters and reservation maps must be empty or zero",
        )
    fixed_limits = canonicalize(initial_payload["limits"])
    for previous, current in pairwise(manifests):
        previous_payload = previous["payload"]
        current_payload = current["payload"]
        if canonicalize(current_payload["limits"]) != fixed_limits:
            fail(
                artifact_id=current["artifact_id"],
                field="payload.limits",
                invariant="manifest_limits_must_remain_fixed_for_run",
                detail="Run limits changed after the initial manifest",
            )
        previous_counters = previous_payload["counters"]
        current_counters = current_payload["counters"]
        entering_fixing = (
            current_payload["state"] == "FIXING"
            and previous_payload["state"] != "FIXING"
        )
        expected_cycles = previous_counters["remediation_cycles_started"] + (
            1 if entering_fixing else 0
        )
        if current_counters["remediation_cycles_started"] != expected_cycles:
            fail(
                artifact_id=current["artifact_id"],
                field="payload.counters.remediation_cycles_started",
                invariant="remediation_cycle_must_be_reserved_on_fixing_entry_only",
                detail=f"Expected remediation cycle counter {expected_cycles}",
            )
        for field_name in (
            "paid_external_calls",
            "tokens_used",
        ):
            previous_value = previous_counters[field_name]
            current_value = current_counters[field_name]
            if previous_value == "unsupported" or current_value == "unsupported":
                if previous_value != current_value:
                    fail(
                        artifact_id=current["artifact_id"],
                        field=f"payload.counters.{field_name}",
                        invariant="manifest_scalar_counters_must_be_non_decreasing",
                        detail="Counter support mode changed during the run",
                    )
            elif current_value < previous_value:
                fail(
                    artifact_id=current["artifact_id"],
                    field=f"payload.counters.{field_name}",
                    invariant="manifest_scalar_counters_must_be_non_decreasing",
                    detail=f"Counter decreased from {previous_value} to {current_value}",
                )
        for field_name in (
            "remediation_attempts_by_request_id",
            "transient_retries_by_execution_key",
        ):
            _require_counter_map_non_decreasing(
                previous=previous_counters[field_name],
                current=current_counters[field_name],
                manifest=current,
                field=f"payload.counters.{field_name}",
            )
        previous_attempts = previous_counters["remediation_attempts_by_request_id"]
        current_attempts = current_counters["remediation_attempts_by_request_id"]
        increased_request_ids = [
            request_id
            for request_id, count in current_attempts.items()
            if count > previous_attempts.get(request_id, 0)
        ]
        cause_ref = current_payload["transition_cause_ref"]
        cause = artifacts.get(cause_ref["artifact_id"]) if cause_ref else None
        cause_is_change_request = (
            cause is not None and cause["artifact_type"] == "change_request"
        )
        required_request_ids = (
            {request["id"] for request in cause["payload"]["requests"]}
            if cause_is_change_request
            else set()
        )
        invalid_increases = [
            request_id
            for request_id in increased_request_ids
            if current_attempts[request_id] != previous_attempts.get(request_id, 0) + 1
            or request_id not in required_request_ids
        ]
        if (
            entering_fixing
            and cause_is_change_request
            and (
                set(increased_request_ids) != required_request_ids or invalid_increases
            )
        ) or (not entering_fixing and increased_request_ids):
            fail(
                artifact_id=current["artifact_id"],
                field="payload.counters.remediation_attempts_by_request_id",
                invariant="request_attempt_must_be_reserved_once_for_fixing_cause",
                detail=(
                    "FIXING entry must increment every request in its change_request "
                    f"cause exactly once; required {sorted(required_request_ids)}, "
                    f"increased {sorted(increased_request_ids)}, invalid "
                    f"{sorted(invalid_increases)}"
                ),
            )
        if current_payload["state"] == "BUDGET_EXHAUSTED":
            cause_ref = current_payload["transition_cause_ref"]
            cause = artifacts.get(cause_ref["artifact_id"]) if cause_ref else None
            if (
                cause is None
                or cause["artifact_type"] != "decision"
                or cause["payload"].get("decision_kind") != "limit_observation"
            ):
                fail(
                    artifact_id=current["artifact_id"],
                    field="payload.transition_cause_ref",
                    invariant="budget_exhausted_requires_limit_observation",
                    detail="BUDGET_EXHAUSTED must be caused by a limit observation",
                )
            observation = cause["payload"]
            previous_ref = artifact_common_ref(previous)
            if (
                observation["previous_manifest_revision"]
                != previous_payload["revision"]
                or observation["previous_manifest_sha256"] != previous_ref["sha256"]
                or canonicalize(observation["counter_snapshot"])
                != canonicalize(previous_counters)
                or canonicalize(current_counters) != canonicalize(previous_counters)
            ):
                fail(
                    artifact_id=current["artifact_id"],
                    field="payload.transition_cause_ref",
                    invariant="limit_observation_must_bind_previous_manifest_counters",
                    detail="Limit observation does not bind the immediate counter snapshot",
                )
            limit_name = observation["limit_name"]
            if observation["limit_value"] != current_payload["limits"][limit_name]:
                fail(
                    artifact_id=cause["artifact_id"],
                    field="payload.limit_value",
                    invariant="limit_observation_value_must_match_manifest_limit",
                    detail=f"Observed limit differs from Manifest {limit_name}",
                )
            classification_contract: dict[str, tuple[set[str], str]] = {
                "deadline_exhausted": ({"deadline_at"}, "hard_exceeded"),
                "token_budget_exhausted": ({"token_budget"}, "hard_exceeded"),
                "paid_call_budget_exhausted": (
                    {"paid_external_call_budget"},
                    "next_reservation_rejected",
                ),
                "remediation_cycle_exhausted": (
                    {"max_remediation_cycles"},
                    "next_attempt_rejected",
                ),
                "same_request_attempt_exhausted": (
                    {"max_same_request_attempts"},
                    "next_attempt_rejected",
                ),
                "transient_retry_exhausted": (
                    {"max_transient_stage_retries"},
                    "next_attempt_rejected",
                ),
                "diff_limit_exhausted": (
                    {"max_changed_files", "max_diff_lines"},
                    "hard_exceeded",
                ),
            }
            classification = observation.get("failure_classification")
            contract = classification_contract.get(classification)
            if contract is None:
                fail(
                    artifact_id=cause["artifact_id"],
                    field="payload.failure_classification",
                    invariant="limit_observation_must_match_failure_classification",
                    detail=f"Unknown budget classification: {classification!r}",
                )
            allowed_names, expected_event = contract
            if (
                limit_name not in allowed_names
                or observation["limit_event"] != expected_event
            ):
                fail(
                    artifact_id=cause["artifact_id"],
                    field="payload.limit_event",
                    invariant="limit_observation_must_match_failure_classification",
                    detail="Limit name/event differs from the blocker classification",
                )
            keyed_limits = {
                "max_same_request_attempts": "remediation_attempts_by_request_id",
                "max_transient_stage_retries": "transient_retries_by_execution_key",
            }
            counter_field = keyed_limits.get(limit_name)
            if counter_field is None:
                if observation["counter_key"] is not None:
                    fail(
                        artifact_id=cause["artifact_id"],
                        field="payload.counter_key",
                        invariant="limit_observation_counter_key_must_match_limit",
                        detail="This limit does not use a keyed counter",
                    )
                observed_value = observation["observed_value"]
                expected_observed_value = {
                    "max_remediation_cycles": previous_counters[
                        "remediation_cycles_started"
                    ],
                    "paid_external_call_budget": previous_counters[
                        "paid_external_calls"
                    ],
                }.get(limit_name)
                if (
                    expected_observed_value is not None
                    and observed_value != expected_observed_value
                ):
                    fail(
                        artifact_id=cause["artifact_id"],
                        field="payload.observed_value",
                        invariant="limit_observation_value_must_match_counter",
                        detail=f"Observed value differs from the {limit_name} counter",
                    )
                if (
                    limit_name
                    in {
                        "max_remediation_cycles",
                        "paid_external_call_budget",
                    }
                    and observed_value < observation["limit_value"]
                ):
                    fail(
                        artifact_id=cause["artifact_id"],
                        field="payload.observed_value",
                        invariant="limit_observation_must_show_exhausted_limit",
                        detail="Attempt or reservation limit has not been exhausted",
                    )
                if limit_name in {
                    "token_budget",
                    "max_changed_files",
                    "max_diff_lines",
                } and (
                    not isinstance(observed_value, int)
                    or isinstance(observed_value, bool)
                    or not isinstance(observation["limit_value"], int)
                    or isinstance(observation["limit_value"], bool)
                    or observed_value <= observation["limit_value"]
                ):
                    fail(
                        artifact_id=cause["artifact_id"],
                        field="payload.observed_value",
                        invariant="limit_observation_must_show_exhausted_limit",
                        detail="Immediate numeric limit requires observed value above limit",
                    )
                if limit_name == "deadline_at":
                    try:
                        observed_at = datetime.fromisoformat(
                            observation["observed_value"].replace("Z", "+00:00")
                        )
                        deadline_at = datetime.fromisoformat(
                            observation["limit_value"].replace("Z", "+00:00")
                        )
                        deadline_reached = observed_at >= deadline_at
                    except (AttributeError, TypeError, ValueError):
                        fail(
                            artifact_id=cause["artifact_id"],
                            field="payload.observed_value",
                            invariant="limit_observation_must_show_exhausted_limit",
                            detail="Deadline observation requires RFC 3339 timestamps",
                        )
                    if not deadline_reached:
                        fail(
                            artifact_id=cause["artifact_id"],
                            field="payload.observed_value",
                            invariant="limit_observation_must_show_exhausted_limit",
                            detail="Observed time is earlier than the run deadline",
                        )
            else:
                counter_key = observation["counter_key"]
                if (
                    counter_key is None
                    or previous_counters[counter_field].get(counter_key)
                    != observation["observed_value"]
                    or observation["observed_value"] < observation["limit_value"]
                ):
                    fail(
                        artifact_id=cause["artifact_id"],
                        field="payload.counter_key",
                        invariant="limit_observation_counter_key_must_match_limit",
                        detail="Keyed limit observation does not match its counter",
                    )


def _validate_stage_checkpoints(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    checkpointed_types = {
        "target_check",
        "review",
        "change_request",
        "remediation",
        "verification",
        "gate",
        "blind_review",
        "final_review",
    }
    ordered_manifests = sorted(manifests, key=lambda item: item["monotonic_sequence"])
    for artifact in artifacts.values():
        if artifact["artifact_type"] not in checkpointed_types:
            continue
        preceding = [
            manifest
            for manifest in ordered_manifests
            if manifest["monotonic_sequence"] < artifact["monotonic_sequence"]
        ]
        checkpoint = preceding[-1] if preceding else None
        if checkpoint is None or checkpoint["payload"]["state"] != artifact["stage"]:
            observed_state = (
                checkpoint["payload"]["state"] if checkpoint is not None else None
            )
            fail(
                artifact_id=artifact["artifact_id"],
                field="stage",
                invariant="stage_artifact_requires_preceding_matching_manifest",
                detail=(
                    f"Artifact stage {artifact['stage']} has preceding state "
                    f"{observed_state}"
                ),
            )


def _validate_sequences(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> int:
    values = list(artifacts.values()) + manifests
    sequences = [value["monotonic_sequence"] for value in values]
    ids = [value["artifact_id"] for value in values]
    if len(ids) != len(set(ids)):
        fail(
            artifact_id=None,
            field="artifact_id",
            invariant="artifact_ids_must_be_run_global_unique",
            detail="Duplicate artifact ID found across objects and manifests",
        )
    if not sequences:
        return -1
    expected = list(range(max(sequences) + 1))
    if sorted(sequences) != expected:
        fail(
            artifact_id=None,
            field="monotonic_sequence",
            invariant="artifact_sequences_must_be_unique_and_contiguous_from_zero",
            detail=f"Expected {expected}, got {sorted(sequences)}",
        )
    return max(sequences)


def _validate_graph(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    all_by_id = {value["artifact_id"]: value for value in manifests}
    all_by_id.update(artifacts)
    manifest_ids = {manifest["artifact_id"] for manifest in manifests}
    for artifact in list(artifacts.values()) + manifests:
        artifact_id = artifact["artifact_id"]
        artifact_type = artifact["artifact_type"]
        for ref_field, ref in iter_common_refs(artifact):
            ref_id = ref["artifact_id"]
            if ref_field.endswith("previous_manifest_ref"):
                continue
            referenced = all_by_id.get(ref_id)
            if referenced is None:
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="artifact_ref_must_resolve_to_committed_artifact",
                    detail=f"Missing referenced artifact: {ref_id}",
                )
            expected_ref = artifact_common_ref(referenced)
            if ref != expected_ref:
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="artifact_ref_must_match_exact_saved_ref",
                    detail=f"Expected {expected_ref}, got {ref}",
                )
            if ref_id == artifact_id:
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="artifact_must_not_reference_itself",
                    detail="Self-reference is not allowed",
                )
            if referenced["monotonic_sequence"] >= artifact["monotonic_sequence"]:
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="artifact_refs_must_point_to_earlier_sequence",
                    detail=(
                        f"Reference sequence {referenced['monotonic_sequence']} is not earlier "
                        f"than {artifact['monotonic_sequence']}"
                    ),
                )
            if artifact_type != "run_manifest" and ref_id in manifest_ids:
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="nonmanifest_artifact_must_not_reference_manifest",
                    detail="Only previous_manifest_ref may point to a manifest",
                )
            if artifact_type == "input_snapshot":
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="root_artifact_must_not_reference_nonroot_artifact",
                    detail="Root artifact contains an unexpected artifact ref",
                )
            if artifact_type == "target" and (
                referenced["artifact_type"] != "input_snapshot"
                or referenced["payload"]["input_kind"] != "repository_identity"
            ):
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="target_may_only_reference_repository_identity_input",
                    detail=f"Target references {referenced['artifact_type']}",
                )
            if (
                artifact_type in EVIDENCE_TYPES
                and referenced["artifact_type"] not in ROOT_TYPES
            ):
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="evidence_may_only_reference_root_artifacts",
                    detail=f"Evidence references {referenced['artifact_type']}",
                )
            if (
                artifact_type in STAGE_TYPES
                and referenced["artifact_type"] == "run_manifest"
            ):
                fail(
                    artifact_id=artifact_id,
                    field=ref_field,
                    invariant="stage_must_not_reference_manifest",
                    detail="Stage references a manifest",
                )


def _require_referenced_type(
    *,
    owner_id: str,
    field: str,
    ref: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    artifact_types: set[str],
    input_kinds: set[str] | None = None,
) -> dict[str, Any]:
    referenced = artifacts[ref["artifact_id"]]
    if referenced["artifact_type"] not in artifact_types:
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="artifact_ref_must_point_to_expected_artifact_type",
            detail=(
                f"Expected {sorted(artifact_types)}, got {referenced['artifact_type']}"
            ),
        )
    if (
        input_kinds is not None
        and referenced["payload"]["input_kind"] not in input_kinds
    ):
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="input_ref_must_point_to_expected_input_kind",
            detail=(
                f"Expected {sorted(input_kinds)}, got "
                f"{referenced['payload']['input_kind']}"
            ),
        )
    return referenced


def _reachable_artifact_ids(
    origin: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> set[str]:
    reachable: set[str] = set()
    pending = [origin]
    while pending:
        current = pending.pop()
        for _, ref in iter_common_refs(current):
            ref_id = ref["artifact_id"]
            if ref_id in reachable or ref_id not in artifacts:
                continue
            reachable.add(ref_id)
            pending.append(artifacts[ref_id])
    return reachable


def _working_entry_map(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    target_id = target["artifact_id"]
    working_tree = require_dict(
        target["payload"]["popr_target_fingerprint"]["working_tree"],
        artifact_id=target_id,
        field="payload.popr_target_fingerprint.working_tree",
    )
    entries = working_tree.get("entries")
    if not isinstance(entries, list):
        fail(
            artifact_id=target_id,
            field="payload.popr_target_fingerprint.working_tree.entries",
            invariant="working_tree_entries_must_be_array",
            detail="Working tree entries are required for transition comparison",
        )
    result: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(entries):
        field = f"payload.popr_target_fingerprint.working_tree.entries[{index}]"
        entry = require_dict(value, artifact_id=target_id, field=field)
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            fail(
                artifact_id=target_id,
                field=f"{field}.path",
                invariant="working_tree_entry_path_must_be_nonempty_string",
                detail="Working tree transition entries require a path",
            )
        if path in result:
            fail(
                artifact_id=target_id,
                field=field,
                invariant="working_tree_entry_paths_must_be_unique",
                detail=f"Duplicate working tree path: {path}",
            )
        result[path] = entry
    return result


def _transition_file_side_for_target(
    *,
    owner_id: str,
    field: str,
    side: dict[str, Any],
    path: str,
    target: dict[str, Any],
) -> None:
    entry = _working_entry_map(target).get(path)
    if side["status"] == "absent":
        if entry is not None and entry.get("status") == "present":
            fail(
                artifact_id=owner_id,
                field=field,
                invariant="transition_file_side_must_match_target_fingerprint",
                detail=f"{path} is present in target {target['artifact_id']}",
            )
        return
    source = side["content_source"]
    if entry is None:
        if (
            source["kind"] == "git_object"
            and source["object_id"] == side["content_oid"]
        ):
            return
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="unlisted_tracked_file_side_requires_git_object_source",
            detail=(
                f"{path} is not a mutable working-tree entry; its side must bind "
                "an immutable Git object"
            ),
        )
    if entry.get("status") != "present" or any(
        side[name] != entry.get(name) for name in ("mode", "type", "content_oid")
    ):
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="transition_file_side_must_match_target_fingerprint",
            detail=f"Present side does not match target entry for {path}",
        )
    if source["kind"] == "git_object":
        if source["object_id"] != side["content_oid"]:
            fail(
                artifact_id=owner_id,
                field=f"{field}.content_source.object_id",
                invariant="transition_git_object_must_match_content_oid",
                detail="Git object source differs from the transition side OID",
            )
        return
    if source["target_id"] != target["artifact_id"]:
        fail(
            artifact_id=owner_id,
            field=f"{field}.content_source.target_id",
            invariant="transition_attachment_must_belong_to_side_target",
            detail="Transition attachment names the wrong target",
        )
    matching = [
        snapshot
        for snapshot in target["payload"]["mutable_content_snapshots"]
        if snapshot["path"] == path
        and snapshot["mode"] == side["mode"]
        and snapshot["type"] == side["type"]
    ]
    if len(matching) != 1:
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="transition_attachment_must_match_one_target_snapshot",
            detail=f"Expected one attachment snapshot for {path}, got {len(matching)}",
        )
    snapshot = matching[0]
    if any(
        (
            source["content_path"] != snapshot["content_path"],
            side["content_oid"] != snapshot["content_oid"],
            side["byte_length"] != snapshot["byte_length"],
            side["content_sha256"] != snapshot["content_sha256"],
        )
    ):
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="transition_attachment_metadata_must_match_target_snapshot",
            detail=f"Transition attachment metadata differs for {path}",
        )


def _transition_index_side_for_target(
    *, owner_id: str, field: str, side: dict[str, Any], target: dict[str, Any]
) -> None:
    fingerprint_side = target["payload"]["popr_target_fingerprint"]["index_diff"]
    if side["status"] == "excluded":
        if fingerprint_side["included"]:
            fail(
                artifact_id=owner_id,
                field=field,
                invariant="transition_index_side_must_match_target",
                detail="Transition says excluded but target includes index diff",
            )
        return
    snapshot = target["payload"]["index_diff_snapshot"]
    source = side["content_source"]
    if (
        not fingerprint_side["included"]
        or snapshot is None
        or source["target_id"] != target["artifact_id"]
        or source["content_path"] != snapshot["content_path"]
        or side["content_oid"] != fingerprint_side["content_oid"]
        or side["byte_length"] != snapshot["byte_length"]
        or side["content_sha256"] != snapshot["content_sha256"]
    ):
        fail(
            artifact_id=owner_id,
            field=field,
            invariant="transition_index_side_must_match_target",
            detail="Transition index side does not bind the target index snapshot",
        )


def _validate_transition_diff_binding(
    *,
    target_check: dict[str, Any],
    transition_diff: dict[str, Any],
    expected_target: dict[str, Any],
    observed_target: dict[str, Any],
) -> None:
    owner_id = target_check["artifact_id"]
    content = transition_diff["payload"]["content"]
    if (
        content["expected_target_ref"] != target_check["payload"]["expected_target_ref"]
        or content["observed_target_ref"]
        != target_check["payload"]["observed_target_ref"]
    ):
        fail(
            artifact_id=owner_id,
            field="payload.transition_diff_ref",
            invariant="transition_diff_targets_must_match_target_check",
            detail="Transition diff target refs differ from the target check",
        )
    expected_entries = _working_entry_map(expected_target)
    observed_entries = _working_entry_map(observed_target)
    changed_paths = sorted(
        {
            path
            for path in expected_entries.keys() | observed_entries.keys()
            if expected_entries.get(path, {"path": path, "status": "absent"})
            != observed_entries.get(path, {"path": path, "status": "absent"})
        },
        key=lambda item: item.encode("utf-8"),
    )
    recorded_paths = [change["path"] for change in content["path_changes"]]
    if recorded_paths != changed_paths:
        fail(
            artifact_id=owner_id,
            field="payload.transition_diff_ref",
            invariant="transition_diff_paths_must_exactly_cover_target_delta",
            detail=f"Expected changed paths {changed_paths}, got {recorded_paths}",
        )
    for index, change in enumerate(content["path_changes"]):
        _transition_file_side_for_target(
            owner_id=owner_id,
            field=f"payload.transition_diff_ref.path_changes[{index}].before",
            side=change["before"],
            path=change["path"],
            target=expected_target,
        )
        _transition_file_side_for_target(
            owner_id=owner_id,
            field=f"payload.transition_diff_ref.path_changes[{index}].after",
            side=change["after"],
            path=change["path"],
            target=observed_target,
        )
    expected_index = expected_target["payload"]["popr_target_fingerprint"]["index_diff"]
    observed_index = observed_target["payload"]["popr_target_fingerprint"]["index_diff"]
    index_changed = expected_index != observed_index
    index_change = content["index_diff_change"]
    if index_changed != (index_change is not None):
        fail(
            artifact_id=owner_id,
            field="payload.transition_diff_ref",
            invariant="transition_index_diff_must_exactly_match_target_delta",
            detail="Transition index diff presence differs from target delta",
        )
    if index_change is not None:
        _transition_index_side_for_target(
            owner_id=owner_id,
            field="payload.transition_diff_ref.index_diff_change.before",
            side=index_change["before"],
            target=expected_target,
        )
        _transition_index_side_for_target(
            owner_id=owner_id,
            field="payload.transition_diff_ref.index_diff_change.after",
            side=index_change["after"],
            target=observed_target,
        )


def _validate_target_check_transition_kinds(
    target_check: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> None:
    artifact_id = target_check["artifact_id"]
    payload = target_check["payload"]
    kinds = set(payload["transition_kinds"])
    if payload["status"] == "unresolved":
        return
    expected_target = artifacts[payload["expected_target_ref"]["artifact_id"]]
    observed_target = artifacts[payload["observed_target_ref"]["artifact_id"]]
    target_fingerprint_fields = (
        "target_source",
        "base",
        "head",
        "working_tree",
        "index_diff",
        "pr_remote",
    )
    expected_fingerprint = expected_target["payload"]["popr_target_fingerprint"]
    observed_fingerprint = observed_target["payload"]["popr_target_fingerprint"]
    comparisons = {
        "target_changed": any(
            expected_fingerprint[field_name] != observed_fingerprint[field_name]
            for field_name in target_fingerprint_fields
        ),
        "permission_changed": payload["expected_permission_set_ref"]
        != payload["observed_permission_set_ref"],
        "contract_changed": False,
        "project_rule_changed": payload["expected_project_rule_refs"]
        != payload["observed_project_rule_refs"],
        "scope_changed": expected_target["payload"]["popr_target_fingerprint"]["scope"]
        != observed_target["payload"]["popr_target_fingerprint"]["scope"],
    }
    specialized_kinds = {
        "permission_set",
        "personal_contract",
        "required_capability",
        "project_rule",
        "acceptance_policy",
    }

    def capability_inputs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            ref
            for ref in refs
            if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
            in {"personal_contract", "required_capability"}
        ]

    comparisons["contract_changed"] = payload["expected_contract_ref"] != payload[
        "observed_contract_ref"
    ] or capability_inputs(payload["expected_input_refs"]) != capability_inputs(
        payload["observed_input_refs"]
    )

    def general_inputs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            ref
            for ref in refs
            if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
            not in specialized_kinds
        ]

    comparisons["governing_input_changed"] = general_inputs(
        payload["expected_input_refs"]
    ) != general_inputs(payload["observed_input_refs"])

    def external_inputs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            ref
            for ref in refs
            if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
            == "external_record"
        ]

    comparisons["external_revision_changed"] = external_inputs(
        payload["expected_input_refs"]
    ) != external_inputs(payload["observed_input_refs"])
    for kind, changed in comparisons.items():
        if changed != (kind in kinds):
            fail(
                artifact_id=artifact_id,
                field="payload.transition_kinds",
                invariant="transition_kind_must_match_observed_ref_delta",
                detail=f"{kind} presence does not match the observed refs",
            )
    working_changed = _working_entry_map(expected_target) != _working_entry_map(
        observed_target
    )
    index_changed = (
        expected_target["payload"]["popr_target_fingerprint"]["index_diff"]
        != observed_target["payload"]["popr_target_fingerprint"]["index_diff"]
    )
    diff_ref = payload["transition_diff_ref"]
    if (working_changed or index_changed) != (diff_ref is not None):
        fail(
            artifact_id=artifact_id,
            field="payload.transition_diff_ref",
            invariant="mutable_target_delta_requires_exact_transition_diff",
            detail="Transition diff presence does not match mutable target changes",
        )
    if diff_ref is not None:
        _validate_transition_diff_binding(
            target_check=target_check,
            transition_diff=artifacts[diff_ref["artifact_id"]],
            expected_target=expected_target,
            observed_target=observed_target,
        )


def _validate_security_audit_adapter(
    gate: dict[str, Any], evidence: dict[str, Any]
) -> None:
    artifact_id = gate["artifact_id"]
    evidence_payload = evidence["payload"]
    if evidence_payload["completeness"] != "full":
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref",
            invariant="security_audit_requires_full_report_evidence",
            detail="Security audit Evidence must preserve the full report",
        )
    content = require_dict(
        evidence_payload.get("content"),
        artifact_id=artifact_id,
        field="payload.evidence_ref.content",
    )
    require_exact_fields(
        content,
        {
            "audit_contract_revision",
            "audit_status",
            "rounds_completed",
            "category_results",
            "findings",
            "overall_score",
            "raw_report",
            "raw_report_sha256",
        },
        artifact_id=artifact_id,
        field="payload.evidence_ref.content",
    )
    require_string(
        content["audit_contract_revision"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.audit_contract_revision",
    )
    audit_status = require_string(
        content["audit_status"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.audit_status",
    )
    if audit_status not in {"complete", "incomplete"}:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.audit_status",
            invariant="security_audit_status_must_be_known",
            detail=f"Unknown security audit status: {audit_status}",
        )
    rounds_completed = require_integer(
        content["rounds_completed"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.rounds_completed",
    )
    if rounds_completed > 10:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.rounds_completed",
            invariant="security_audit_rounds_must_be_between_zero_and_ten",
            detail=f"Invalid rounds completed: {rounds_completed}",
        )
    category_results = require_list(
        content["category_results"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.category_results",
    )
    expected_by_id = dict(SECURITY_CATEGORY_WEIGHTS)
    category_ids: list[str] = []
    for index, item_value in enumerate(category_results):
        field = f"payload.evidence_ref.content.category_results[{index}]"
        item = require_dict(item_value, artifact_id=artifact_id, field=field)
        require_exact_fields(
            item,
            {"category_id", "weight_percent", "score"},
            artifact_id=artifact_id,
            field=field,
        )
        category_id = require_string(
            item["category_id"],
            artifact_id=artifact_id,
            field=f"{field}.category_id",
        )
        category_ids.append(category_id)
        weight = require_integer(
            item["weight_percent"],
            artifact_id=artifact_id,
            field=f"{field}.weight_percent",
        )
        score = require_integer(
            item["score"], artifact_id=artifact_id, field=f"{field}.score"
        )
        if category_id not in expected_by_id or weight != expected_by_id.get(
            category_id
        ):
            fail(
                artifact_id=artifact_id,
                field=field,
                invariant="security_category_id_and_weight_must_match_contract",
                detail=f"Invalid category/weight: {category_id!r}/{weight}",
            )
        if score > 100:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.score",
                invariant="security_category_score_must_be_zero_to_one_hundred",
                detail=f"Invalid category score: {score}",
            )
    ordered_ids = [category_id for category_id, _ in SECURITY_CATEGORY_WEIGHTS]
    expected_relative_order = [
        category_id for category_id in ordered_ids if category_id in category_ids
    ]
    if category_ids != expected_relative_order or len(category_ids) != len(
        set(category_ids)
    ):
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.category_results",
            invariant="security_categories_must_be_unique_and_in_fixed_order",
            detail=f"Invalid category order: {category_ids}",
        )
    findings = require_list(
        content["findings"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.findings",
    )
    finding_ids: list[str] = []
    for index, finding_value in enumerate(findings):
        field = f"payload.evidence_ref.content.findings[{index}]"
        finding = require_dict(finding_value, artifact_id=artifact_id, field=field)
        require_exact_fields(
            finding,
            {
                "id",
                "severity",
                "category_id",
                "location",
                "attack_scenario",
                "evidence",
                "remediation",
            },
            artifact_id=artifact_id,
            field=field,
        )
        for field_name in (
            "id",
            "severity",
            "category_id",
            "location",
            "attack_scenario",
            "evidence",
            "remediation",
        ):
            require_string(
                finding[field_name],
                artifact_id=artifact_id,
                field=f"{field}.{field_name}",
            )
        finding_ids.append(finding["id"])
        if finding["severity"] not in SECURITY_SEVERITIES:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.severity",
                invariant="security_finding_severity_must_be_known",
                detail=f"Unknown severity: {finding['severity']}",
            )
        if finding["category_id"] not in expected_by_id:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.category_id",
                invariant="security_finding_category_must_be_known",
                detail=f"Unknown category: {finding['category_id']}",
            )
    if len(finding_ids) != len(set(finding_ids)):
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.findings",
            invariant="security_finding_ids_must_be_unique",
            detail="Security finding IDs must be unique",
        )
    overall_score = require_integer(
        content["overall_score"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.overall_score",
    )
    if overall_score > 100:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.overall_score",
            invariant="security_overall_score_must_be_zero_to_one_hundred",
            detail=f"Invalid overall score: {overall_score}",
        )
    raw_report = require_string(
        content["raw_report"],
        artifact_id=artifact_id,
        field="payload.evidence_ref.content.raw_report",
        allow_empty=True,
    )
    expected_raw_hash = sha256_hex(raw_report.encode("utf-8"))
    if content["raw_report_sha256"] != expected_raw_hash:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.raw_report_sha256",
            invariant="security_raw_report_hash_must_match_utf8_bytes",
            detail=f"Expected {expected_raw_hash}",
        )
    complete = rounds_completed == 10 and category_ids == ordered_ids
    if audit_status == "complete" and not complete:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref.content.audit_status",
            invariant="complete_security_audit_requires_ten_rounds_and_all_categories",
            detail="Complete audit lacks ten rounds or fixed six-category coverage",
        )
    if audit_status == "incomplete" and gate["payload"]["execution_status"] != "failed":
        fail(
            artifact_id=artifact_id,
            field="payload.execution_status",
            invariant="incomplete_security_audit_must_fail_execution",
            detail="Incomplete security audit cannot be execution success",
        )
    if (
        gate["payload"]["execution_status"] == "succeeded"
        and audit_status != "complete"
    ):
        fail(
            artifact_id=artifact_id,
            field="payload.execution_status",
            invariant="successful_security_audit_must_be_complete",
            detail="Successful security audit must have complete adapter evidence",
        )


def _review_coverage_allows_ready(review: dict[str, Any]) -> bool:
    payload = review["payload"]
    return payload["generic_coverage_status"] == "Complete" and (
        review["artifact_type"] != "review" or payload["coverage_status"] == "Complete"
    )


def _project_coverage_allows_ready(
    review: dict[str, Any], *, project_review_status: str
) -> bool:
    payload = review["payload"]
    if project_review_status == "required":
        return payload["project_coverage_status"] == "Complete" and bool(
            payload["project_results"]
        )
    return (
        payload["project_coverage_status"] == "not_required"
        and not payload["project_results"]
    )


def _validate_ready_project_lens_ids(
    review: dict[str, Any], *, required_lens_ids: list[str]
) -> None:
    actual_lens_ids = [
        result["lens_id"] for result in review["payload"]["project_results"]
    ]
    if actual_lens_ids != required_lens_ids:
        fail(
            artifact_id=review["artifact_id"],
            field="payload.project_results",
            invariant="ready_project_lens_ids_must_match_resolved_lenses",
            detail=(
                f"Expected project lens IDs {required_lens_ids}, got {actual_lens_ids}"
            ),
        )


def _validate_ready_required_commands(
    *,
    manifest: dict[str, Any],
    context_resolution: dict[str, Any],
    verifications: list[dict[str, Any]],
) -> None:
    required_commands = context_resolution["payload"]["resolved_commands"]["commands"]
    expected = {command["command_id"]: command["argv"] for command in required_commands}
    actual: dict[str, list[str]] = {}
    for verification in verifications:
        for command in verification["payload"]["commands"]:
            command_id = command["command_id"]
            if command_id in actual:
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.artifact_refs",
                    invariant="ready_required_commands_must_execute_exactly_once",
                    detail=f"Required command was executed ambiguously: {command_id}",
                )
            actual[command_id] = command["argv"]
    if actual != expected:
        fail(
            artifact_id=manifest["artifact_id"],
            field="payload.artifact_refs",
            invariant="ready_required_commands_must_match_resolved_commands",
            detail=f"Expected commands {sorted(expected)}, got {sorted(actual)}",
        )


def _validate_gate_capability_binding(
    gate: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> None:
    payload = gate["payload"]
    matches = [
        artifacts[ref["artifact_id"]]
        for ref in gate["input_refs"]
        if artifacts[ref["artifact_id"]]["artifact_type"] == "input_snapshot"
        and artifacts[ref["artifact_id"]]["payload"]["input_kind"]
        == "required_capability"
        and artifacts[ref["artifact_id"]]["payload"]["content"]["capability_name"]
        == payload["gate_name"]
        and artifacts[ref["artifact_id"]]["payload"]["content"]["declared_version"]
        == payload["declared_version"]
        and artifacts[ref["artifact_id"]]["payload"]["source_revision"]
        == payload["capability_revision"]
        and artifacts[ref["artifact_id"]]["payload"]["content_sha256"]
        == payload["content_sha256"]
    ]
    if len(matches) != 1:
        fail(
            artifact_id=gate["artifact_id"],
            field="payload.capability_revision",
            invariant="gate_capability_must_match_one_required_capability_input",
            detail=f"Expected one matching required capability input, got {len(matches)}",
        )


def _validate_gate_relationship(
    gate: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> None:
    artifact_id = gate["artifact_id"]
    payload = gate["payload"]
    required_refs = ("evidence_ref", "pre_target_check_ref", "post_target_check_ref")
    if any(payload[field_name] is None for field_name in required_refs):
        fail(
            artifact_id=artifact_id,
            field="payload",
            invariant="gate_requires_evidence_and_pre_post_target_checks",
            detail="A gate must bind Evidence and both target checks",
        )
    evidence = artifacts[payload["evidence_ref"]["artifact_id"]]
    pre_check = artifacts[payload["pre_target_check_ref"]["artifact_id"]]
    post_check = artifacts[payload["post_target_check_ref"]["artifact_id"]]
    if not (
        pre_check["monotonic_sequence"]
        < evidence["monotonic_sequence"]
        < post_check["monotonic_sequence"]
        < gate["monotonic_sequence"]
    ):
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref",
            invariant="gate_evidence_must_be_between_pre_and_post_checks",
            detail="Expected pre-check < Evidence < post-check < gate",
        )
    if evidence["target_ref"] != gate["target_ref"]:
        fail(
            artifact_id=artifact_id,
            field="payload.evidence_ref",
            invariant="gate_evidence_must_match_gate_target",
            detail="Gate Evidence belongs to another target",
        )
    for field_name, check in (
        ("pre_target_check_ref", pre_check),
        ("post_target_check_ref", post_check),
    ):
        if (
            check["target_ref"] != gate["target_ref"]
            or check["input_refs"] != gate["input_refs"]
        ):
            fail(
                artifact_id=artifact_id,
                field=f"payload.{field_name}",
                invariant="gate_target_check_must_match_gate_target_and_inputs",
                detail="Gate target check belongs to another target or input set",
            )
    if pre_check["payload"]["status"] != "unchanged":
        fail(
            artifact_id=artifact_id,
            field="payload.pre_target_check_ref",
            invariant="gate_precheck_must_be_unchanged",
            detail="Gate pre-check did not confirm the expected target",
        )
    expected_post_status = "changed" if payload["mutated_target"] else "unchanged"
    if post_check["payload"]["status"] != expected_post_status:
        fail(
            artifact_id=artifact_id,
            field="payload.post_target_check_ref",
            invariant="gate_postcheck_must_match_mutation_status",
            detail=f"Expected {expected_post_status} post-check",
        )
    if payload["gate_name"] == "security-audit":
        if payload["decision_policy"] != "project_or_human":
            fail(
                artifact_id=artifact_id,
                field="payload.decision_policy",
                invariant="security_gate_requires_project_or_human_policy",
                detail="Security audit has no native PASS/BLOCKED contract",
            )
        if evidence["payload"]["evidence_kind"] != "security_audit_result":
            fail(
                artifact_id=artifact_id,
                field="payload.evidence_ref",
                invariant="security_gate_requires_security_audit_evidence",
                detail="Security gate Evidence has the wrong kind",
            )
        _validate_security_audit_adapter(gate, evidence)


def _validate_final_reviewer_independence(artifacts: dict[str, dict[str, Any]]) -> None:
    ordered = sorted(artifacts.values(), key=lambda item: item["monotonic_sequence"])
    by_id = {artifact["artifact_id"]: artifact for artifact in ordered}
    compared_roles = {"initial_reviewer", "project_reviewer", "implementer"}
    for artifact in ordered:
        if artifact["artifact_type"] not in {"blind_review", "final_review"}:
            continue
        artifact_id = artifact["artifact_id"]
        producer = artifact["producer"]
        prior = [
            candidate
            for candidate in ordered
            if candidate["monotonic_sequence"] < artifact["monotonic_sequence"]
            and candidate["producer"]["role"] in compared_roles
        ]
        required_instances = {
            candidate["producer"]["instance_id"] for candidate in prior
        }
        required_contexts = {candidate["producer"]["context_id"] for candidate in prior}
        check = artifact["payload"]["independence_check"]
        if check["status"] == "passed" and (
            not required_instances.issubset(check["compared_instance_ids"])
            or not required_contexts.issubset(check["compared_context_ids"])
            or check["conflicting_instance_ids"]
            or check["conflicting_context_ids"]
            or producer["instance_id"] in required_instances
            or producer["context_id"] in required_contexts
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.independence_check",
                invariant="passed_independence_must_cover_and_differ_from_prior_roles",
                detail="Fresh reviewer metadata does not prove independence",
            )
        if artifact["artifact_type"] == "blind_review":
            forbidden_types = STAGE_TYPES | EVIDENCE_TYPES
            for field_name, refs in (
                ("producer.received_artifacts", producer["received_artifacts"]),
                (
                    "payload.blind_received_artifacts",
                    artifact["payload"]["blind_received_artifacts"],
                ),
            ):
                forbidden = [
                    ref["artifact_id"]
                    for ref in refs
                    if by_id[ref["artifact_id"]]["artifact_type"] in forbidden_types
                ]
                if forbidden:
                    fail(
                        artifact_id=artifact_id,
                        field=field_name,
                        invariant="blind_review_must_not_receive_reconciliation_history",
                        detail=f"Blind review received forbidden artifacts: {forbidden}",
                    )
            blind_input_kinds = {
                "issue_bundle",
                "explicit_scope",
                "project_rule",
                "acceptance_policy",
                "external_record",
                "human_approved_run_local",
            }
            expected_blind_ids = {
                ref["artifact_id"]
                for ref in artifact["input_refs"]
                if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
                in blind_input_kinds
            } | {artifact["target_ref"]["artifact_id"]}
            for field_name, refs in (
                ("producer.received_artifacts", producer["received_artifacts"]),
                (
                    "payload.blind_received_artifacts",
                    artifact["payload"]["blind_received_artifacts"],
                ),
            ):
                if {ref["artifact_id"] for ref in refs} != expected_blind_ids:
                    fail(
                        artifact_id=artifact_id,
                        field=field_name,
                        invariant="blind_review_must_receive_exact_target_and_inputs",
                        detail="Blind review inputs differ from its target generation",
                    )
            continue
        blind = by_id[artifact["payload"]["blind_review_ref"]["artifact_id"]]
        if (
            producer["instance_id"] != blind["producer"]["instance_id"]
            or producer["context_id"] != blind["producer"]["context_id"]
            or artifact["target_ref"] != blind["target_ref"]
            or artifact["input_refs"] != blind["input_refs"]
        ):
            fail(
                artifact_id=artifact_id,
                field="payload.blind_review_ref",
                invariant="final_review_must_continue_same_blind_reviewer_and_target",
                detail="Final reconciliation does not continue the blind review context",
            )
        received_ids = {ref["artifact_id"] for ref in producer["received_artifacts"]}
        required_received = {blind["artifact_id"]} | {
            ref["artifact_id"] for ref in artifact["payload"]["remediation_refs"]
        }
        previous_review = artifact["payload"]["previous_review_ref"]
        if previous_review is not None:
            required_received.add(previous_review["artifact_id"])
        if not required_received.issubset(received_ids):
            fail(
                artifact_id=artifact_id,
                field="producer.received_artifacts",
                invariant="final_review_must_receive_reconciliation_inputs",
                detail="Final review did not receive blind/previous/remediation artifacts",
            )


def _validate_remediation_lineage(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    change_requests = [
        artifact
        for artifact in artifacts.values()
        if artifact["artifact_type"] == "change_request"
    ]
    remediations = [
        artifact
        for artifact in artifacts.values()
        if artifact["artifact_type"] == "remediation"
    ]
    for manifest in manifests:
        if manifest["payload"]["state"] != "FIXING":
            continue
        cause_ref = manifest["payload"]["transition_cause_ref"]
        cause = artifacts.get(cause_ref["artifact_id"]) if cause_ref else None
        lifecycle = lifecycle_map(manifest)
        if (
            cause is None
            or cause["artifact_type"] != "change_request"
            or cause["target_ref"] != manifest["payload"]["current_target_ref"]
            or lifecycle.get(cause["artifact_id"], (None, None))[0] != "current"
        ):
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.transition_cause_ref",
                invariant="fixing_transition_requires_current_same_target_change_request",
                detail="FIXING must be caused by a current change request for its target",
            )
    for remediation in remediations:
        request_id = remediation["payload"]["request_id"]
        sources = [
            request
            for request in change_requests
            if request["monotonic_sequence"] < remediation["monotonic_sequence"]
            and request["target_ref"] == remediation["target_ref"]
            and any(item["id"] == request_id for item in request["payload"]["requests"])
        ]
        if len(sources) != 1:
            fail(
                artifact_id=remediation["artifact_id"],
                field="payload.request_id",
                invariant="remediation_request_id_must_match_exactly_one_change_request",
                detail=f"Request {request_id!r} matched {len(sources)} change requests",
            )
        source_request = next(
            request
            for request in sources[0]["payload"]["requests"]
            if request["id"] == request_id
        )
        if (
            remediation["payload"]["decision"] == "defer_minor"
            and source_request["source_type"] != "review_finding"
        ):
            fail(
                artifact_id=remediation["artifact_id"],
                field="payload.decision",
                invariant="defer_minor_requires_review_finding_source",
                detail="Verification and gate failures cannot be deferred as minor",
            )
        received_ids = {
            ref["artifact_id"] for ref in remediation["producer"]["received_artifacts"]
        }
        if sources[0]["artifact_id"] not in received_ids:
            fail(
                artifact_id=remediation["artifact_id"],
                field="producer.received_artifacts",
                invariant="remediation_must_receive_source_change_request",
                detail="Remediation does not explicitly receive its source request",
            )
    for manifest in manifests:
        lifecycle = lifecycle_map(manifest)
        current_request_ids = [
            remediation["payload"]["request_id"]
            for remediation in remediations
            if lifecycle.get(remediation["artifact_id"], (None, None))[0] == "current"
        ]
        if len(current_request_ids) != len(set(current_request_ids)):
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.artifact_refs",
                invariant="request_id_must_have_at_most_one_current_remediation",
                detail="Multiple current remediations share a request ID",
            )
    latest_lifecycle = lifecycle_map(manifests[-1]) if manifests else {}
    for final_review in (
        artifact
        for artifact in artifacts.values()
        if artifact["artifact_type"] == "final_review"
        and latest_lifecycle.get(artifact["artifact_id"], (None, None))[0] == "current"
    ):
        final_sequence = final_review["monotonic_sequence"]
        final_target = artifacts[final_review["target_ref"]["artifact_id"]]
        final_generation = final_target["payload"]["generation"]
        fixing_requests: set[str] = set()
        for manifest in manifests:
            cause_ref = manifest["payload"]["transition_cause_ref"]
            cause = artifacts.get(cause_ref["artifact_id"]) if cause_ref else None
            if (
                manifest["payload"]["state"] == "FIXING"
                and cause is not None
                and cause["artifact_type"] == "change_request"
                and cause["monotonic_sequence"] < final_sequence
                and latest_lifecycle.get(cause["artifact_id"], (None, None))[0]
                in {"current", "historical"}
                and artifacts[cause["target_ref"]["artifact_id"]]["payload"][
                    "generation"
                ]
                <= final_generation
            ):
                fixing_requests.update(
                    request["id"] for request in cause["payload"]["requests"]
                )
        lineage_remediations = [
            remediation
            for remediation in remediations
            if remediation["monotonic_sequence"] < final_sequence
            and remediation["payload"]["request_id"] in fixing_requests
            and artifacts[remediation["target_ref"]["artifact_id"]]["payload"][
                "generation"
            ]
            <= final_generation
            and latest_lifecycle.get(remediation["artifact_id"], (None, None))[0]
            in {"current", "historical"}
        ]
        expected_refs = sorted(
            (artifact_common_ref(remediation) for remediation in lineage_remediations),
            key=lambda ref: ref["artifact_id"],
        )
        if fixing_requests:
            covered_ids = {
                remediation["payload"]["request_id"]
                for remediation in lineage_remediations
            }
            if (
                final_review["payload"]["remediation_status"] != "required"
                or final_review["payload"]["remediation_refs"] != expected_refs
                or covered_ids != fixing_requests
                or final_review["payload"]["previous_review_ref"] is None
            ):
                fail(
                    artifact_id=final_review["artifact_id"],
                    field="payload.remediation_refs",
                    invariant="final_review_must_cover_all_fixing_request_remediations",
                    detail="Final review does not retain the complete remediation history",
                )
            invalid_current_attempts: list[str] = []
            for request_id in sorted(fixing_requests):
                attempts = [
                    remediation
                    for remediation in lineage_remediations
                    if remediation["payload"]["request_id"] == request_id
                ]
                current_attempts = [
                    remediation
                    for remediation in attempts
                    if latest_lifecycle.get(remediation["artifact_id"], (None, None))[0]
                    == "current"
                ]
                if (
                    len(current_attempts) != 1
                    or current_attempts[0]["payload"]["decision"]
                    not in {"fix", "not_applicable"}
                    or current_attempts[0]["monotonic_sequence"]
                    != max(attempt["monotonic_sequence"] for attempt in attempts)
                ):
                    invalid_current_attempts.append(request_id)
            if invalid_current_attempts:
                fail(
                    artifact_id=final_review["artifact_id"],
                    field="payload.remediation_refs",
                    invariant=(
                        "final_review_requires_one_current_remediation_"
                        "per_fixing_request"
                    ),
                    detail=(
                        "Each fixing request needs one latest current READY-capable "
                        f"remediation: {invalid_current_attempts}"
                    ),
                )
        elif (
            final_review["payload"]["remediation_status"] != "not_required"
            or final_review["payload"]["remediation_refs"]
        ):
            fail(
                artifact_id=final_review["artifact_id"],
                field="payload.remediation_status",
                invariant="remediation_is_not_required_without_fixing_transition",
                detail="No prior FIXING request exists in this lineage",
            )
        previous_ref = final_review["payload"]["previous_review_ref"]
        if previous_ref is not None:
            previous_review = artifacts[previous_ref["artifact_id"]]
            previous_target = artifacts[previous_review["target_ref"]["artifact_id"]]
            if previous_target["payload"][
                "generation"
            ] > final_generation or latest_lifecycle.get(
                previous_review["artifact_id"], (None, None)
            )[0] not in {"current", "historical"}:
                fail(
                    artifact_id=final_review["artifact_id"],
                    field="payload.previous_review_ref",
                    invariant="previous_review_must_be_valid_target_ancestor_history",
                    detail="Previous review is invalidated or outside target lineage",
                )


def _validate_ready_blocking_findings(
    *,
    final_review: dict[str, Any],
    reviews: list[dict[str, Any]],
    manifests: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    latest_lifecycle: dict[str, tuple[str, dict[str, Any] | None]],
) -> None:
    final_payload = final_review["payload"]
    if final_payload["blocking_finding_ids"]:
        fail(
            artifact_id=final_review["artifact_id"],
            field="payload.blocking_finding_ids",
            invariant="ready_requires_no_current_blocking_findings",
            detail=(
                "Final review still has blocking findings: "
                f"{final_payload['blocking_finding_ids']}"
            ),
        )
    reconciliation_by_id = {
        item["finding_id"]: item
        for item in final_payload["reconciliation"]["previous_findings"]
    }
    fixing_cause_ids = {
        manifest["payload"]["transition_cause_ref"]["artifact_id"]
        for manifest in manifests
        if manifest["payload"]["state"] == "FIXING"
        and manifest["payload"]["transition_cause_ref"] is not None
    }
    final_remediations = [
        artifacts[ref["artifact_id"]]
        for ref in final_payload["remediation_refs"]
        if latest_lifecycle.get(ref["artifact_id"], (None, None))[0] == "current"
    ]
    change_requests = [
        artifact
        for artifact in artifacts.values()
        if artifact["artifact_type"] == "change_request"
        and artifact["monotonic_sequence"] < final_review["monotonic_sequence"]
        and latest_lifecycle.get(artifact["artifact_id"], (None, None))[0]
        in {"current", "historical"}
    ]
    for review in reviews:
        review_ref = artifact_common_ref(review)
        for finding_id in review["payload"]["blocking_finding_ids"]:
            reconciliation = reconciliation_by_id.get(finding_id)
            requests = [
                request_artifact
                for request_artifact in change_requests
                if request_artifact["target_ref"] == review["target_ref"]
                and any(
                    request["source_type"] == "review_finding"
                    and request["id"] == finding_id
                    and request["source_item_id"] == finding_id
                    and request["source_ref"] == review_ref
                    for request in request_artifact["payload"]["requests"]
                )
            ]
            remediations = [
                remediation
                for remediation in final_remediations
                if remediation["payload"]["request_id"] == finding_id
            ]
            expected_decision = (
                {
                    "Fixed": "fix",
                    "Not applicable": "not_applicable",
                }.get(reconciliation["status"])
                if reconciliation is not None
                else None
            )
            valid = (
                reconciliation is not None
                and bool(reconciliation["evidence_refs"])
                and len(requests) == 1
                and requests[0]["artifact_id"] in fixing_cause_ids
                and len(remediations) == 1
                and remediations[0]["payload"]["decision"] == expected_decision
            )
            if not valid:
                fail(
                    artifact_id=review["artifact_id"],
                    field="payload.blocking_finding_ids",
                    invariant=(
                        "ready_blocking_finding_requires_change_request_"
                        "remediation_and_evidence"
                    ),
                    detail=(
                        f"Blocking finding {finding_id!r} lacks one exact request, "
                        "FIXING transition, matching remediation, or reconciliation "
                        "Evidence"
                    ),
                )


def _validate_context_grounding_bindings(
    value: Any,
    *,
    owner_id: str,
    artifacts: dict[str, dict[str, Any]],
    generation_input_ids: set[str],
    field: str = "payload",
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_context_grounding_bindings(
                item,
                owner_id=owner_id,
                artifacts=artifacts,
                generation_input_ids=generation_input_ids,
                field=f"{field}[{index}]",
            )
        return
    if not isinstance(value, dict):
        return
    if set(value) == {"artifact_id", "artifact_path", "sha256"}:
        return
    local_refs = list(iter_common_refs(value, field=field))
    if "content_sha256" in value:
        referenced_hashes = {
            artifacts[ref["artifact_id"]]["payload"].get("content_sha256")
            for _, ref in local_refs
            if ref["artifact_id"] in artifacts
        }
        if value["content_sha256"] not in referenced_hashes:
            fail(
                artifact_id=owner_id,
                field=f"{field}.content_sha256",
                invariant="context_content_hash_must_match_grounding_ref",
                detail="Grounded context hash differs from referenced content",
            )
    for ref_field, ref in local_refs:
        referenced = artifacts[ref["artifact_id"]]
        if (
            referenced["artifact_type"] == "input_snapshot"
            and referenced["artifact_id"] not in generation_input_ids
        ):
            fail(
                artifact_id=owner_id,
                field=ref_field,
                invariant="context_input_ref_must_be_current_generation_input",
                detail="Context grounding ref is outside generation inputs",
            )
        if (
            referenced["artifact_type"] == "input_snapshot"
            and referenced["payload"]["input_kind"] == "prior_run_handoff"
            and (".selected_sources" in field or ".resolved_" in field)
        ):
            fail(
                artifact_id=owner_id,
                field=ref_field,
                invariant="prior_run_handoff_must_remain_informational_only",
                detail="Prior-run handoff cannot ground selected or resolved context",
            )
    for key, item in value.items():
        _validate_context_grounding_bindings(
            item,
            owner_id=owner_id,
            artifacts=artifacts,
            generation_input_ids=generation_input_ids,
            field=f"{field}.{key}",
        )


def _validate_typed_refs_and_state_evidence(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    for artifact in artifacts.values():
        artifact_id = artifact["artifact_id"]
        payload = artifact["payload"]
        artifact_type = artifact["artifact_type"]
        if artifact_type in {"review", "blind_review"}:
            for index, requirement in enumerate(payload["required_gates"]):
                if requirement["target_ref"] != artifact["target_ref"]:
                    fail(
                        artifact_id=artifact_id,
                        field=f"payload.required_gates[{index}].target_ref",
                        invariant="required_gate_target_must_match_review_target",
                        detail="Required gate names another target",
                    )
                _require_referenced_type(
                    owner_id=artifact_id,
                    field=f"payload.required_gates[{index}].target_ref",
                    ref=requirement["target_ref"],
                    artifacts=artifacts,
                    artifact_types={"target"},
                )
        if artifact_type == "target_check":
            for field_name in ("expected_target_ref", "observed_target_ref"):
                ref = payload[field_name]
                if ref is not None:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types={"target"},
                    )
            for field_name in ("expected_input_refs", "observed_input_refs"):
                for ref in payload[field_name]:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                    )
            for field_name in (
                "expected_permission_set_ref",
                "observed_permission_set_ref",
            ):
                ref = payload[field_name]
                if ref is not None:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                        input_kinds={"permission_set"},
                    )
            for field_name in ("expected_contract_ref", "observed_contract_ref"):
                ref = payload[field_name]
                if ref is not None:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                        input_kinds={"personal_contract", "required_capability"},
                    )
            for field_name in (
                "expected_project_rule_refs",
                "observed_project_rule_refs",
            ):
                for ref in payload[field_name]:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                        input_kinds={"project_rule", "acceptance_policy"},
                    )
            for ref in payload["observation_evidence_refs"]:
                observation = _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.observation_evidence_refs",
                    ref=ref,
                    artifacts=artifacts,
                    artifact_types={"evidence"},
                )
                if observation["target_ref"] != artifact["target_ref"]:
                    fail(
                        artifact_id=artifact_id,
                        field="payload.observation_evidence_refs",
                        invariant="target_check_evidence_must_match_expected_target",
                        detail="Observation Evidence belongs to another target",
                    )
            if payload["transition_diff_ref"] is not None:
                transition_diff = _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.transition_diff_ref",
                    ref=payload["transition_diff_ref"],
                    artifacts=artifacts,
                    artifact_types={"evidence"},
                )
                if (
                    transition_diff["payload"]["evidence_kind"]
                    != "target_transition_diff"
                    or transition_diff["target_ref"] != artifact["target_ref"]
                ):
                    fail(
                        artifact_id=artifact_id,
                        field="payload.transition_diff_ref",
                        invariant="transition_diff_ref_must_point_to_transition_evidence",
                        detail="Transition diff ref has the wrong evidence kind",
                    )
            _validate_target_check_transition_kinds(artifact, artifacts)
        elif artifact_type == "review" and artifact["producer"]["role"] not in {
            "initial_reviewer",
            "project_reviewer",
        }:
            fail(
                artifact_id=artifact_id,
                field="producer.role",
                invariant="review_requires_reviewer_role",
                detail="Review producer must be an initial or project reviewer",
            )
        elif artifact_type == "verification":
            for index, command in enumerate(payload["commands"]):
                for field_name in (
                    "stdout_ref",
                    "stderr_ref",
                    "environment_snapshot_ref",
                ):
                    command_evidence = _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.commands[{index}].{field_name}",
                        ref=command[field_name],
                        artifacts=artifacts,
                        artifact_types={"evidence"},
                    )
                    if command_evidence["target_ref"] != artifact["target_ref"]:
                        fail(
                            artifact_id=artifact_id,
                            field=f"payload.commands[{index}].{field_name}",
                            invariant="verification_evidence_must_match_verification_target",
                            detail="Verification Evidence belongs to another target",
                        )
                    if payload["status"] == "passed" and command_evidence["payload"][
                        "completeness"
                    ] not in {"full", "redacted"}:
                        fail(
                            artifact_id=artifact_id,
                            field=f"payload.commands[{index}].{field_name}",
                            invariant="passed_verification_requires_complete_evidence",
                            detail="Passed command evidence is truncated",
                        )
            if payload["mutation_patch_ref"] is not None:
                patch = _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.mutation_patch_ref",
                    ref=payload["mutation_patch_ref"],
                    artifacts=artifacts,
                    artifact_types={"evidence"},
                )
                if patch["target_ref"] != artifact["target_ref"]:
                    fail(
                        artifact_id=artifact_id,
                        field="payload.mutation_patch_ref",
                        invariant="mutation_patch_must_match_stage_target",
                        detail="Mutation patch Evidence belongs to another target",
                    )
        elif artifact_type == "remediation":
            if artifact["producer"]["role"] != "implementer":
                fail(
                    artifact_id=artifact_id,
                    field="producer.role",
                    invariant="remediation_requires_implementer_role",
                    detail="Remediation producer must be an implementer",
                )
            if payload["patch_ref"] is not None:
                patch = _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.patch_ref",
                    ref=payload["patch_ref"],
                    artifacts=artifacts,
                    artifact_types={"evidence"},
                )
                if patch["target_ref"] != artifact["target_ref"]:
                    fail(
                        artifact_id=artifact_id,
                        field="payload.patch_ref",
                        invariant="remediation_patch_must_match_remediation_target",
                        detail="Remediation patch Evidence belongs to another target",
                    )
        elif artifact_type == "gate":
            typed_gate_refs = {
                "evidence_ref": {"evidence"},
                "pre_target_check_ref": {"target_check"},
                "post_target_check_ref": {"target_check"},
            }
            for field_name, artifact_types in typed_gate_refs.items():
                ref = payload[field_name]
                if ref is not None:
                    _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.{field_name}",
                        ref=ref,
                        artifacts=artifacts,
                        artifact_types=artifact_types,
                    )
            if payload["acceptance_policy_ref"] is not None:
                _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.acceptance_policy_ref",
                    ref=payload["acceptance_policy_ref"],
                    artifacts=artifacts,
                    artifact_types={"input_snapshot"},
                    input_kinds={"acceptance_policy", "human_approved_run_local"},
                )
                if payload["acceptance_policy_ref"] not in artifact["input_refs"]:
                    fail(
                        artifact_id=artifact_id,
                        field="payload.acceptance_policy_ref",
                        invariant="gate_acceptance_policy_must_be_current_generation_input",
                        detail="Acceptance policy is not a gate generation input",
                    )
            _validate_gate_capability_binding(artifact, artifacts)
            _validate_gate_relationship(artifact, artifacts)
        elif artifact_type == "change_request":
            source_types = {
                "review_finding": {"review", "final_review"},
                "verification_failure": {"verification"},
                "gate_failure": {"gate"},
            }
            for index, request in enumerate(payload["requests"]):
                source_type = request["source_type"]
                source = _require_referenced_type(
                    owner_id=artifact_id,
                    field=f"payload.requests[{index}].source_ref",
                    ref=request["source_ref"],
                    artifacts=artifacts,
                    artifact_types=source_types[source_type],
                )
                if source["target_ref"] != artifact["target_ref"]:
                    fail(
                        artifact_id=artifact_id,
                        field=f"payload.requests[{index}].source_ref",
                        invariant="change_request_source_must_match_request_target",
                        detail="Change request source belongs to another target",
                    )
                if source_type == "review_finding":
                    if source["artifact_type"] == "review":
                        source_finding_ids = set(
                            source["payload"]["blocking_finding_ids"]
                        )
                    else:
                        reconciliation = source["payload"]["reconciliation"]
                        source_finding_ids = {
                            item["finding_id"]
                            for collection in (
                                "previous_findings",
                                "current_findings",
                            )
                            for item in reconciliation[collection]
                        }
                    if request["source_item_id"] not in source_finding_ids:
                        fail(
                            artifact_id=artifact_id,
                            field=f"payload.requests[{index}].source_item_id",
                            invariant="review_request_must_name_source_finding",
                            detail="Finding ID is absent from the source review summary",
                        )
                elif source_type == "verification_failure":
                    expected_behavior = _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.requests[{index}].expected_behavior_ref",
                        ref=request["expected_behavior_ref"],
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                        input_kinds={
                            "issue_bundle",
                            "project_rule",
                            "acceptance_policy",
                            "personal_contract",
                            "required_capability",
                        },
                    )
                    output = _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.requests[{index}].output_ref",
                        ref=request["output_ref"],
                        artifacts=artifacts,
                        artifact_types={"evidence"},
                    )
                    commands = [
                        command
                        for command in source["payload"]["commands"]
                        if command["command_id"] == request["command_id"]
                    ]
                    if (
                        source["payload"]["status"] != "failed"
                        or len(commands) != 1
                        or commands[0]["exit_code"] == 0
                        or request["output_ref"]
                        not in (commands[0]["stdout_ref"], commands[0]["stderr_ref"])
                        or output["target_ref"] != artifact["target_ref"]
                        or artifact_common_ref(expected_behavior)
                        not in source["input_refs"]
                    ):
                        fail(
                            artifact_id=artifact_id,
                            field=f"payload.requests[{index}]",
                            invariant="verification_request_must_bind_failed_command_expected_behavior_and_output",
                            detail="Verification request does not bind one failed source command",
                        )
                else:
                    expected_behavior = _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.requests[{index}].expected_behavior_ref",
                        ref=request["expected_behavior_ref"],
                        artifacts=artifacts,
                        artifact_types={"input_snapshot"},
                        input_kinds={"acceptance_policy"},
                    )
                    evidence = _require_referenced_type(
                        owner_id=artifact_id,
                        field=f"payload.requests[{index}].evidence_ref",
                        ref=request["evidence_ref"],
                        artifacts=artifacts,
                        artifact_types={"evidence"},
                    )
                    if (
                        source["payload"]["execution_status"] != "succeeded"
                        or source["payload"]["decision_status"] != "BLOCKED"
                        or source["payload"]["evidence_ref"] != request["evidence_ref"]
                        or evidence["target_ref"] != artifact["target_ref"]
                        or artifact_common_ref(expected_behavior)
                        not in source["input_refs"]
                    ):
                        fail(
                            artifact_id=artifact_id,
                            field=f"payload.requests[{index}]",
                            invariant="gate_request_must_bind_blocked_gate_policy_and_evidence",
                            detail="Gate request does not bind one blocked gate result",
                        )
        elif artifact_type == "final_review":
            _require_referenced_type(
                owner_id=artifact_id,
                field="payload.blind_review_ref",
                ref=payload["blind_review_ref"],
                artifacts=artifacts,
                artifact_types={"blind_review"},
            )
            if payload["previous_review_ref"] is not None:
                _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.previous_review_ref",
                    ref=payload["previous_review_ref"],
                    artifacts=artifacts,
                    artifact_types={"review", "final_review"},
                )
            for ref in payload["remediation_refs"]:
                _require_referenced_type(
                    owner_id=artifact_id,
                    field="payload.remediation_refs",
                    ref=ref,
                    artifacts=artifacts,
                    artifact_types={"remediation"},
                )
            final_generation = artifacts[artifact["target_ref"]["artifact_id"]][
                "payload"
            ]["generation"]
            for collection_name in ("previous_findings", "current_findings"):
                for item in payload["reconciliation"][collection_name]:
                    for ref in item["evidence_refs"]:
                        evidence = _require_referenced_type(
                            owner_id=artifact_id,
                            field=f"payload.reconciliation.{collection_name}.evidence_refs",
                            ref=ref,
                            artifacts=artifacts,
                            artifact_types={"evidence"},
                        )
                        evidence_target = artifacts[
                            evidence["target_ref"]["artifact_id"]
                        ]
                        if (
                            evidence["target_ref"] != artifact["target_ref"]
                            or evidence_target["payload"]["generation"]
                            > final_generation
                        ):
                            fail(
                                artifact_id=artifact_id,
                                field=f"payload.reconciliation.{collection_name}.evidence_refs",
                                invariant="reconciliation_evidence_must_match_final_target",
                                detail="Reconciliation Evidence belongs to another target",
                            )
        if artifact_type in {"blind_review", "final_review"} and (
            artifact["producer"]["role"] != "final_reviewer"
            or not artifact["producer"]["fresh_context"]
        ):
            fail(
                artifact_id=artifact_id,
                field="producer",
                invariant="final_review_artifacts_require_fresh_final_reviewer",
                detail="Blind and final review artifacts require a fresh final reviewer",
            )

    _validate_final_reviewer_independence(artifacts)
    _validate_remediation_lineage(manifests, artifacts)

    for manifest in manifests:
        payload = manifest["payload"]
        manifest_id = manifest["artifact_id"]
        lifecycle = lifecycle_map(manifest)
        if payload["context_status"] == "resolved":
            context_resolution = _require_referenced_type(
                owner_id=manifest_id,
                field="payload.context_resolution_ref",
                ref=payload["context_resolution_ref"],
                artifacts=artifacts,
                artifact_types={"decision"},
            )
            if context_resolution["payload"]["decision_kind"] != "context_resolution":
                fail(
                    artifact_id=manifest_id,
                    field="payload.context_resolution_ref",
                    invariant="resolved_context_requires_context_resolution_decision",
                    detail="Context resolution ref has the wrong decision kind",
                )
            context_payload = context_resolution["payload"]
            grounded_ref_ids = {
                ref["artifact_id"] for _, ref in iter_common_refs(context_payload)
            }
            required_grounded_ids = {
                payload["permission_set_ref"]["artifact_id"],
                payload["contract_ref"]["artifact_id"],
                *(ref["artifact_id"] for ref in payload["project_context_refs"]),
            }
            if (
                context_resolution["input_refs"] != payload["input_refs"]
                or context_resolution["target_ref"] != payload["current_target_ref"]
                or context_payload["resolution_mode"] != payload["resolution_mode"]
                or context_payload["contract_status"] != payload["contract_status"]
                or context_payload["contract_ref"] != payload["contract_ref"]
                or context_payload["unresolved_inputs"]
                or not required_grounded_ids.issubset(grounded_ref_ids)
            ):
                fail(
                    artifact_id=manifest_id,
                    field="payload.context_resolution_ref",
                    invariant="resolved_manifest_must_bind_complete_context_resolution",
                    detail="Manifest context fields differ from the resolution decision",
                )
            for ref_field, ref in iter_common_refs(context_payload):
                referenced = artifacts[ref["artifact_id"]]
                if referenced["artifact_type"] not in {
                    "input_snapshot",
                    "evidence",
                }:
                    fail(
                        artifact_id=context_resolution["artifact_id"],
                        field=ref_field,
                        invariant="resolved_context_refs_must_be_input_or_evidence",
                        detail="Resolved context ref has an unsupported artifact type",
                    )
            if any(
                isinstance(item, dict) and item.get("authority_status") == "pending"
                for item in context_payload["authority_decisions"]
            ):
                fail(
                    artifact_id=manifest_id,
                    field="payload.context_resolution_ref",
                    invariant="resolved_context_must_not_have_pending_authority",
                    detail="Pending authority cannot support resolved context",
                )
            pending_external_inputs = [
                ref["artifact_id"]
                for ref in payload["input_refs"]
                if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
                == "external_record"
                and artifacts[ref["artifact_id"]]["payload"]["content"][
                    "authority_status"
                ]
                == "pending"
            ]
            if pending_external_inputs:
                fail(
                    artifact_id=manifest_id,
                    field="payload.input_refs",
                    invariant="resolved_context_must_not_include_pending_external_authority",
                    detail=f"Pending external inputs: {pending_external_inputs}",
                )
            _validate_context_grounding_bindings(
                context_payload,
                owner_id=context_resolution["artifact_id"],
                artifacts=artifacts,
                generation_input_ids={
                    ref["artifact_id"] for ref in payload["input_refs"]
                },
            )
        if payload["last_completed_stage"] is not None:
            _require_referenced_type(
                owner_id=manifest_id,
                field="payload.last_completed_stage",
                ref=payload["last_completed_stage"],
                artifacts=artifacts,
                artifact_types=STAGE_TYPES,
            )
        blocker = payload["blocker"]
        if blocker is None:
            continue
        cause = _require_referenced_type(
            owner_id=manifest_id,
            field="payload.blocker.cause_ref",
            ref=blocker["cause_ref"],
            artifacts=artifacts,
            artifact_types=STAGE_TYPES,
        )
        if lifecycle.get(cause["artifact_id"], (None, None))[0] != "current":
            fail(
                artifact_id=manifest_id,
                field="payload.blocker.cause_ref",
                invariant="blocker_cause_must_be_current",
                detail="Blocker cause is not current in the stopping Manifest",
            )
        cause_payload = cause["payload"]
        expected_pairs = {
            "blocked_state": payload["state"],
            "target_ref": payload["current_target_ref"],
            "failure_classification": blocker["failure_classification"],
            "observed_evidence_refs": blocker["observed_evidence_refs"],
            "required_human_action": blocker["required_human_action"],
            "resume_requirement": blocker["resume_requirement"],
            "resume_state": payload["resume_state"],
        }
        if any(
            cause_payload.get(key) != value for key, value in expected_pairs.items()
        ):
            fail(
                artifact_id=manifest_id,
                field="payload.blocker.cause_ref",
                invariant="blocker_cause_payload_must_match_manifest_blocker",
                detail="Cause artifact does not reproduce the blocker union",
            )
        reachable = _reachable_artifact_ids(cause, artifacts)
        for ref in blocker["observed_evidence_refs"]:
            evidence = _require_referenced_type(
                owner_id=manifest_id,
                field="payload.blocker.observed_evidence_refs",
                ref=ref,
                artifacts=artifacts,
                artifact_types={"evidence"},
            )
            if (
                evidence["artifact_id"] not in reachable
                or lifecycle.get(evidence["artifact_id"], (None, None))[0] != "current"
                or evidence["payload"]["completeness"] == "truncated"
            ):
                fail(
                    artifact_id=manifest_id,
                    field="payload.blocker.observed_evidence_refs",
                    invariant="blocker_evidence_must_be_current_complete_and_reachable",
                    detail=f"Invalid blocker Evidence: {evidence['artifact_id']}",
                )


def _validate_lifecycle(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    previous: dict[str, tuple[str, dict[str, Any] | None]] = {}
    previous_input_ids: set[str] = set()
    previous_target_id: str | None = None
    for manifest in manifests:
        current = lifecycle_map(manifest)
        current_input_ids = {
            ref["artifact_id"] for ref in manifest["payload"]["input_refs"]
        }
        current_target_ref = manifest["payload"]["current_target_ref"]
        current_target_id = (
            current_target_ref["artifact_id"]
            if current_target_ref is not None
            else None
        )
        cause_ref = manifest["payload"]["transition_cause_ref"]
        cause = artifacts.get(cause_ref["artifact_id"]) if cause_ref else None
        transition_kinds = (
            set(cause["payload"]["transition_kinds"])
            if cause is not None and cause["artifact_type"] == "target_check"
            else set()
        )
        changed_input_kinds = {
            "governing_input_changed",
            "permission_changed",
            "contract_changed",
            "project_rule_changed",
            "scope_changed",
            "external_revision_changed",
        }
        allowed_transition_ids = (
            _reachable_artifact_ids(cause, artifacts) | {cause["artifact_id"]}
            if cause is not None
            else set()
        )
        generation_switched = (
            previous_target_id is not None
            and current_target_id is not None
            and previous_target_id != current_target_id
        )
        missing = sorted(previous.keys() - current.keys())
        if missing:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.artifact_refs",
                invariant="manifest_must_retain_all_prior_lifecycle_entries",
                detail=f"Missing prior artifact lifecycle entries: {missing}",
            )
        for artifact_id, (status, reason_ref) in current.items():
            is_new = artifact_id not in previous
            if is_new:
                if status != "current":
                    artifact = artifacts[artifact_id]
                    expected_status = (
                        "invalidated"
                        if transition_kinds & changed_input_kinds
                        else "historical"
                    )
                    allowed_transition_exception = (
                        generation_switched
                        and cause is not None
                        and cause["artifact_type"] == "target_check"
                        and cause["payload"]["status"] == "changed"
                        and artifact["artifact_type"] in {"target_check", "evidence"}
                        and artifact_id in allowed_transition_ids
                        and status == expected_status
                    )
                    if allowed_transition_exception:
                        pass
                    else:
                        fail(
                            artifact_id=manifest["artifact_id"],
                            field="payload.artifact_refs",
                            invariant="new_lifecycle_entry_must_start_current",
                            detail=f"Artifact {artifact_id} first appears as {status}",
                        )
                if status != "invalidated":
                    continue
            else:
                previous_status = previous[artifact_id][0]
                allowed = {
                    "current": {"current", "historical", "invalidated"},
                    "historical": {"historical", "invalidated"},
                    "invalidated": {"invalidated"},
                }[previous_status]
                if status not in allowed:
                    fail(
                        artifact_id=manifest["artifact_id"],
                        field="payload.artifact_refs",
                        invariant="artifact_lifecycle_must_be_irreversible",
                        detail=f"Artifact {artifact_id}: {previous_status} -> {status}",
                    )
            if status == "invalidated" and (
                is_new or previous[artifact_id][0] != "invalidated"
            ):
                reason = (
                    artifacts.get(reason_ref["artifact_id"]) if reason_ref else None
                )
                if reason is None:
                    fail(
                        artifact_id=manifest["artifact_id"],
                        field="payload.artifact_refs",
                        invariant="invalidation_reason_must_resolve",
                        detail=f"Invalidation reason is missing for {artifact_id}",
                    )
                if reason["artifact_type"] == "input_snapshot":
                    if (
                        reason["artifact_id"] not in current_input_ids
                        or current_input_ids == previous_input_ids
                    ):
                        fail(
                            artifact_id=manifest["artifact_id"],
                            field="payload.artifact_refs",
                            invariant="input_invalidation_reason_must_be_changed_current_input",
                            detail=f"Invalidation input does not explain a changed input set: {artifact_id}",
                        )
                elif reason["artifact_type"] not in STAGE_TYPES | EVIDENCE_TYPES:
                    fail(
                        artifact_id=manifest["artifact_id"],
                        field="payload.artifact_refs",
                        invariant="invalidation_reason_must_be_input_stage_or_evidence",
                        detail=f"Unsupported invalidation reason type: {reason['artifact_type']}",
                    )
        previous = current
        previous_input_ids = current_input_ids
        previous_target_id = current_target_id


def _validate_repository_identity(
    repository_id: str,
    manifests: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> None:
    for manifest in manifests:
        ref = manifest["payload"]["repository_identity_ref"]
        identity = artifacts.get(ref["artifact_id"])
        if (
            identity is None
            or identity["artifact_type"] != "input_snapshot"
            or identity["payload"]["input_kind"] != "repository_identity"
        ):
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.repository_identity_ref",
                invariant="repository_identity_ref_must_point_to_identity_input",
                detail="Repository identity ref does not point to a repository_identity input",
            )
        derived = f"sha256-{sha256_hex(canonicalize(identity['payload']['content']))}"
        if derived != repository_id:
            fail(
                artifact_id=identity["artifact_id"],
                field="payload.content",
                invariant="repository_directory_id_must_match_identity_content",
                detail=f"Expected directory {derived}, got {repository_id}",
            )


def _validate_targets_and_inputs(
    manifests: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]
) -> None:
    generation_inputs: dict[str, list[dict[str, Any]]] = {}
    generation_payloads: dict[str, dict[str, Any]] = {}
    generation_targets: dict[int, str] = {}
    previous_target_id: str | None = None
    previous_generation: int | None = None
    previous_inputs: list[dict[str, Any]] | None = None
    previous_payload: dict[str, Any] | None = None
    latest_lifecycle: dict[str, tuple[str, dict[str, Any] | None]] = {}
    for manifest in manifests:
        payload = manifest["payload"]
        latest_lifecycle = lifecycle_map(manifest)
        for ref in payload["input_refs"]:
            lifecycle = latest_lifecycle.get(ref["artifact_id"])
            artifact = artifacts.get(ref["artifact_id"])
            if (
                artifact is None
                or artifact["artifact_type"] != "input_snapshot"
                or lifecycle is None
                or lifecycle[0] != "current"
            ):
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.input_refs",
                    invariant="manifest_inputs_must_be_current_input_snapshots",
                    detail=f"Invalid current input ref: {ref['artifact_id']}",
                )
        input_ids = {ref["artifact_id"] for ref in payload["input_refs"]}
        role_refs = {
            "repository_identity_ref": (
                payload["repository_identity_ref"],
                {"repository_identity"},
            ),
            "permission_set_ref": (payload["permission_set_ref"], {"permission_set"}),
        }
        if payload["input_source"] == "issue":
            role_refs["issue_ref"] = (payload["issue_ref"], {"issue_bundle"})
        else:
            role_refs["scope_input_ref"] = (
                payload["scope_input_ref"],
                {"explicit_scope"},
            )
        if payload["contract_ref"] is not None:
            role_refs["contract_ref"] = (
                payload["contract_ref"],
                {"personal_contract", "required_capability"},
            )
        for field_name, (ref, expected_kinds) in role_refs.items():
            referenced_input = artifacts.get(ref["artifact_id"])
            actual_kind = (
                referenced_input["payload"]["input_kind"]
                if referenced_input is not None
                and referenced_input["artifact_type"] == "input_snapshot"
                else None
            )
            if ref["artifact_id"] not in input_ids or actual_kind not in expected_kinds:
                fail(
                    artifact_id=manifest["artifact_id"],
                    field=f"payload.{field_name}",
                    invariant="manifest_role_ref_must_be_member_of_generation_inputs",
                    detail=f"Expected one of {sorted(expected_kinds)}, got {actual_kind!r}",
                )
        for ref in payload["project_context_refs"]:
            if ref["artifact_id"] not in input_ids:
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.project_context_refs",
                    invariant="project_context_refs_must_be_generation_inputs",
                    detail=f"Project context is not a generation input: {ref['artifact_id']}",
                )
        input_kinds = [
            artifacts[ref["artifact_id"]]["payload"]["input_kind"]
            for ref in payload["input_refs"]
        ]
        if input_kinds.count("permission_set") != 1:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.input_refs",
                invariant="generation_inputs_must_have_one_permission_set",
                detail=f"Found {input_kinds.count('permission_set')} permission sets",
            )
        for ref in payload["input_refs"]:
            input_artifact = artifacts[ref["artifact_id"]]
            if input_artifact["payload"][
                "input_kind"
            ] == "external_record" and input_artifact["payload"]["content"][
                "authority_status"
            ] not in {"governing", "pending"}:
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.input_refs",
                    invariant="generation_inputs_must_exclude_evidence_only_external_records",
                    detail=f"External record is evidence_only: {ref['artifact_id']}",
                )
        if payload["target_status"] == "unresolved":
            continue
        target_ref = payload["current_target_ref"]
        target = artifacts.get(target_ref["artifact_id"])
        lifecycle = latest_lifecycle.get(target_ref["artifact_id"])
        if (
            target is None
            or target["artifact_type"] != "target"
            or lifecycle is None
            or lifecycle[0] != "current"
        ):
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.current_target_ref",
                invariant="manifest_target_must_be_current_target_artifact",
                detail="Current target ref does not point to a current target artifact",
            )
        generation = target["payload"]["generation"]
        fingerprint = target["payload"]["popr_target_fingerprint"]
        object_id_length = 40 if fingerprint["git_object_format"] == "sha1" else 64
        base = require_dict(
            fingerprint["base"],
            artifact_id=target["artifact_id"],
            field="payload.popr_target_fingerprint.base",
        )
        base_commit = base.get("commit")
        for ref in payload["input_refs"]:
            input_artifact = artifacts[ref["artifact_id"]]
            if input_artifact["payload"]["input_kind"] not in {
                "project_rule",
                "acceptance_policy",
            }:
                continue
            source_sha = input_artifact["payload"]["source_sha"]
            source_object_id = input_artifact["payload"]["source_object_id"]
            if (
                source_sha != base_commit
                or len(source_sha) != object_id_length
                or len(source_object_id) != object_id_length
            ):
                fail(
                    artifact_id=input_artifact["artifact_id"],
                    field="payload.source_sha",
                    invariant="base_project_input_must_bind_target_base_and_object_format",
                    detail="Project input Git IDs do not match target base/object format",
                )
        if payload["current_target_generation"] != generation:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.current_target_generation",
                invariant="manifest_generation_must_match_target",
                detail=f"Expected {generation}, got {payload['current_target_generation']}",
            )
        existing_target = generation_targets.get(generation)
        if existing_target is not None and existing_target != target["artifact_id"]:
            fail(
                artifact_id=target["artifact_id"],
                field="payload.generation",
                invariant="target_generation_must_not_be_reused",
                detail=f"Generation {generation} was already used by {existing_target}",
            )
        generation_targets[generation] = target["artifact_id"]
        if previous_target_id is None:
            if generation != 0:
                fail(
                    artifact_id=target["artifact_id"],
                    field="payload.generation",
                    invariant="first_resolved_target_generation_must_be_zero",
                    detail=f"First target generation is {generation}",
                )
        elif (
            target["artifact_id"] != previous_target_id
            and generation != previous_generation + 1
        ):
            fail(
                artifact_id=target["artifact_id"],
                field="payload.generation",
                invariant="changed_target_generation_must_increment_by_one",
                detail=f"Expected {previous_generation + 1}, got {generation}",
            )
        if (
            previous_target_id is not None
            and target["artifact_id"] != previous_target_id
        ):
            cause_ref = payload["transition_cause_ref"]
            cause = (
                artifacts.get(cause_ref["artifact_id"])
                if cause_ref is not None
                else None
            )
            expected_project_refs = (
                [
                    ref
                    for ref in previous_payload["project_context_refs"]
                    if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
                    in {"project_rule", "acceptance_policy"}
                ]
                if previous_payload is not None
                else []
            )
            observed_project_refs = [
                ref
                for ref in payload["project_context_refs"]
                if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
                in {"project_rule", "acceptance_policy"}
            ]
            if cause is None or cause["artifact_type"] != "target_check":
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.transition_cause_ref",
                    invariant="target_change_must_have_target_check_cause",
                    detail="Changed target generation requires an earlier target_check",
                )
            if (
                cause["payload"]["status"] != "changed"
                or cause["payload"]["expected_target_ref"]["artifact_id"]
                != previous_target_id
                or cause["payload"]["observed_target_ref"] != target_ref
                or cause["payload"]["expected_input_refs"] != previous_inputs
                or cause["payload"]["observed_input_refs"] != payload["input_refs"]
                or previous_payload is None
                or cause["payload"]["expected_permission_set_ref"]
                != previous_payload["permission_set_ref"]
                or cause["payload"]["observed_permission_set_ref"]
                != payload["permission_set_ref"]
                or cause["payload"]["expected_contract_ref"]
                != previous_payload["contract_ref"]
                or cause["payload"]["observed_contract_ref"] != payload["contract_ref"]
                or cause["payload"]["expected_project_rule_refs"]
                != expected_project_refs
                or cause["payload"]["observed_project_rule_refs"]
                != observed_project_refs
            ):
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.transition_cause_ref",
                    invariant="target_check_cause_must_prove_generation_change",
                    detail="Target check cause does not bind previous and current targets",
                )
        inputs = payload["input_refs"]
        if previous_inputs is not None and inputs != previous_inputs:
            cause_ref = payload["transition_cause_ref"]
            cause = (
                artifacts.get(cause_ref["artifact_id"])
                if cause_ref is not None
                else None
            )
            if cause is None or cause["artifact_type"] != "target_check":
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.transition_cause_ref",
                    invariant="input_change_must_have_transition_cause",
                    detail="Changed generation inputs require an earlier target_check",
                )
        existing_inputs = generation_inputs.get(target["artifact_id"])
        if existing_inputs is None:
            generation_inputs[target["artifact_id"]] = inputs
            generation_payloads[target["artifact_id"]] = payload
        elif existing_inputs != inputs:
            fail(
                artifact_id=manifest["artifact_id"],
                field="payload.input_refs",
                invariant="target_generation_input_refs_must_remain_exact",
                detail="Input refs changed without creating a new target generation",
            )
        for artifact_id, (status, _) in latest_lifecycle.items():
            current_artifact = artifacts[artifact_id]
            belongs_to_old_target = (
                current_artifact["target_ref"] is not None
                and current_artifact["target_ref"]["artifact_id"]
                != target["artifact_id"]
            )
            is_old_target = (
                current_artifact["artifact_type"] == "target"
                and current_artifact["artifact_id"] != target["artifact_id"]
            )
            is_noncurrent_input = (
                current_artifact["artifact_type"] == "input_snapshot"
                and current_artifact["artifact_id"] not in input_ids
            )
            if status == "current" and (
                belongs_to_old_target or is_old_target or is_noncurrent_input
            ):
                fail(
                    artifact_id=manifest["artifact_id"],
                    field="payload.artifact_refs",
                    invariant="current_artifact_must_match_current_generation",
                    detail=f"Current artifact belongs to an old target: {artifact_id}",
                )
        previous_target_id = target["artifact_id"]
        previous_generation = generation
        previous_inputs = inputs
        previous_payload = payload
    for artifact in artifacts.values():
        if artifact["artifact_type"] not in STAGE_TYPES:
            continue
        target_ref = artifact["target_ref"]
        if target_ref is None:
            continue
        expected_inputs = generation_inputs.get(target_ref["artifact_id"])
        if expected_inputs is None:
            fail(
                artifact_id=artifact["artifact_id"],
                field="target_ref",
                invariant="stage_target_must_have_committed_generation_inputs",
                detail="No manifest establishes generation inputs for the referenced target",
            )
        if artifact["artifact_type"] == "target_check":
            if artifact["input_refs"] != artifact["payload"]["expected_input_refs"]:
                fail(
                    artifact_id=artifact["artifact_id"],
                    field="input_refs",
                    invariant="target_check_envelope_must_use_expected_input_refs",
                    detail="Target check input refs differ from expected input refs",
                )
            if artifact["target_ref"] != artifact["payload"]["expected_target_ref"]:
                fail(
                    artifact_id=artifact["artifact_id"],
                    field="payload.expected_target_ref",
                    invariant="target_check_expected_target_must_match_envelope",
                    detail="Expected target ref differs from target_check envelope",
                )
            expected_target = artifacts[artifact["target_ref"]["artifact_id"]]
            expected_payload = generation_payloads[expected_target["artifact_id"]]
            expected_project_refs = [
                ref
                for ref in expected_payload["project_context_refs"]
                if artifacts[ref["artifact_id"]]["payload"]["input_kind"]
                in {"project_rule", "acceptance_policy"}
            ]
            if (
                artifact["payload"]["expected_permission_set_ref"]
                != expected_payload["permission_set_ref"]
                or artifact["payload"]["expected_contract_ref"]
                != expected_payload["contract_ref"]
                or artifact["payload"]["expected_project_rule_refs"]
                != expected_project_refs
            ):
                fail(
                    artifact_id=artifact["artifact_id"],
                    field="payload.expected_input_refs",
                    invariant="target_check_expected_roles_must_match_generation",
                    detail="Target check role refs differ from expected generation",
                )
            observed_ref = artifact["payload"]["observed_target_ref"]
            status = artifact["payload"]["status"]
            if status == "unchanged":
                if (
                    observed_ref != artifact["target_ref"]
                    or artifact["payload"]["observed_input_refs"] != expected_inputs
                    or artifact["payload"]["observed_permission_set_ref"]
                    != expected_payload["permission_set_ref"]
                    or artifact["payload"]["observed_contract_ref"]
                    != expected_payload["contract_ref"]
                    or artifact["payload"]["observed_project_rule_refs"]
                    != expected_project_refs
                ):
                    fail(
                        artifact_id=artifact["artifact_id"],
                        field="payload",
                        invariant="unchanged_target_check_must_preserve_target_and_inputs",
                        detail="Unchanged target check altered target or input refs",
                    )
            elif status == "changed":
                observed_target = (
                    artifacts.get(observed_ref["artifact_id"])
                    if observed_ref is not None
                    else None
                )
                if (
                    observed_target is None
                    or observed_target["artifact_type"] != "target"
                    or observed_target["payload"]["generation"]
                    != expected_target["payload"]["generation"] + 1
                ):
                    fail(
                        artifact_id=artifact["artifact_id"],
                        field="payload.observed_target_ref",
                        invariant="changed_target_check_must_increment_generation_by_one",
                        detail="Observed changed target is not the next generation",
                    )
                observed_inputs = generation_inputs.get(observed_target["artifact_id"])
                if (
                    observed_inputs is not None
                    and artifact["payload"]["observed_input_refs"] != observed_inputs
                ):
                    fail(
                        artifact_id=artifact["artifact_id"],
                        field="payload.observed_input_refs",
                        invariant="target_check_observed_inputs_must_match_observed_generation",
                        detail="Observed input refs differ from committed observed generation",
                    )
        elif artifact["input_refs"] != expected_inputs:
            fail(
                artifact_id=artifact["artifact_id"],
                field="input_refs",
                invariant="stage_input_refs_must_match_target_generation",
                detail="Stage input refs differ from target generation inputs",
            )
    if manifests and manifests[-1]["payload"]["state"] == "READY":
        ready_manifest = manifests[-1]
        current_target_ref = ready_manifest["payload"]["current_target_ref"]
        context_resolution = artifacts[
            ready_manifest["payload"]["context_resolution_ref"]["artifact_id"]
        ]
        project_review_status = context_resolution["payload"]["resolved_lenses"][
            "project_review_status"
        ]
        required_lens_ids = context_resolution["payload"]["resolved_lenses"][
            "required_lens_ids"
        ]
        current_artifacts = [
            artifacts[artifact_id]
            for artifact_id, (status, _) in latest_lifecycle.items()
            if status == "current"
        ]
        current_types = {artifact["artifact_type"] for artifact in current_artifacts}
        required_current_types = {
            "target_check",
            "verification",
            "gate",
            "blind_review",
            "final_review",
        }
        missing_types = sorted(required_current_types - current_types)
        current_reviews = [
            artifact
            for artifact in artifacts.values()
            if artifact["artifact_type"] == "review"
            and latest_lifecycle.get(artifact["artifact_id"], (None, None))[0]
            == "current"
        ]
        reconciliation_reviews = [
            artifact
            for artifact in artifacts.values()
            if artifact["artifact_type"] == "review"
            and latest_lifecycle.get(artifact["artifact_id"], (None, None))[0]
            in {"current", "historical"}
        ]
        if missing_types or not current_reviews:
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.state",
                invariant="ready_requires_validated_review_verification_gate_and_final_artifacts",
                detail=f"Missing READY evidence types: {missing_types}",
            )
        if not any(
            artifact["artifact_type"] == "target_check"
            and artifact["payload"]["status"] == "unchanged"
            for artifact in current_artifacts
        ):
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.state",
                invariant="ready_requires_unchanged_current_target_check",
                detail="No current unchanged target check supports READY",
            )
        current_verifications = [
            artifact
            for artifact in current_artifacts
            if artifact["artifact_type"] == "verification"
        ]
        if not current_verifications or any(
            artifact["payload"]["status"] != "passed"
            or not artifact["payload"]["commands"]
            or any(
                command["exit_code"] != 0 for command in artifact["payload"]["commands"]
            )
            for artifact in current_verifications
        ):
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.state",
                invariant="ready_requires_successful_current_verification",
                detail="Current verification is missing, failed, or incomplete",
            )
        _validate_ready_required_commands(
            manifest=ready_manifest,
            context_resolution=context_resolution,
            verifications=current_verifications,
        )
        for verification in current_verifications:
            for command in verification["payload"]["commands"]:
                for field_name in (
                    "stdout_ref",
                    "stderr_ref",
                    "environment_snapshot_ref",
                ):
                    ref = command[field_name]
                    if latest_lifecycle.get(ref["artifact_id"], (None, None))[0] != (
                        "current"
                    ):
                        fail(
                            artifact_id=verification["artifact_id"],
                            field=f"payload.commands.{field_name}",
                            invariant="ready_verification_evidence_must_be_current",
                            detail="Verification reuses non-current Evidence",
                        )
        blind_reviews = [
            artifact
            for artifact in current_artifacts
            if artifact["artifact_type"] == "blind_review"
        ]
        final_reviews = [
            artifact
            for artifact in current_artifacts
            if artifact["artifact_type"] == "final_review"
        ]
        if len(blind_reviews) != 1 or len(final_reviews) != 1:
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.artifact_refs",
                invariant="ready_requires_one_current_blind_and_final_review",
                detail="READY requires exactly one current blind/final review pair",
            )
        blind_review = blind_reviews[0]
        final_review = final_reviews[0]
        if final_review["payload"]["blind_review_ref"] != artifact_common_ref(
            blind_review
        ):
            fail(
                artifact_id=final_review["artifact_id"],
                field="payload.blind_review_ref",
                invariant="ready_final_review_must_reference_current_blind_review",
                detail="Final review references a non-current blind review",
            )
        lineage_role_artifacts = [
            artifact
            for artifact in artifacts.values()
            if artifact["producer"]["role"]
            in {"initial_reviewer", "project_reviewer", "implementer"}
        ]
        if (
            any(
                artifact["monotonic_sequence"] >= blind_review["monotonic_sequence"]
                for artifact in lineage_role_artifacts
            )
            or blind_review["monotonic_sequence"] >= final_review["monotonic_sequence"]
            or any(
                manifest["payload"]["state"] == "FIXING"
                and manifest["monotonic_sequence"] > final_review["monotonic_sequence"]
                for manifest in manifests
            )
        ):
            fail(
                artifact_id=final_review["artifact_id"],
                field="payload.independence_check",
                invariant="ready_review_order_must_be_initial_fix_blind_final",
                detail="Final review was not produced after all prior review/fix work",
            )
        for collection_name in ("previous_findings", "current_findings"):
            for finding in final_review["payload"]["reconciliation"][collection_name]:
                for ref in finding["evidence_refs"]:
                    evidence = artifacts[ref["artifact_id"]]
                    if latest_lifecycle.get(ref["artifact_id"], (None, None))[
                        0
                    ] not in {"current", "historical"} or evidence["payload"][
                        "completeness"
                    ] not in {"full", "redacted"}:
                        fail(
                            artifact_id=final_review["artifact_id"],
                            field=f"payload.reconciliation.{collection_name}.evidence_refs",
                            invariant="ready_reconciliation_evidence_must_be_noninvalidated_and_complete",
                            detail="Final reconciliation uses invalidated or truncated Evidence",
                        )
        if (
            not _review_coverage_allows_ready(blind_review)
            or blind_review["payload"]["independence_check"]["status"] != "passed"
            or final_review["payload"]["independence_check"]["status"] != "passed"
        ):
            fail(
                artifact_id=final_review["artifact_id"],
                field="payload.independence_check",
                invariant="ready_requires_complete_independent_final_review",
                detail="Final review coverage or independence did not pass",
            )
        if not _project_coverage_allows_ready(
            blind_review, project_review_status=project_review_status
        ):
            fail(
                artifact_id=blind_review["artifact_id"],
                field="payload.project_coverage_status",
                invariant="ready_project_coverage_must_match_resolved_lenses",
                detail="Blind project coverage differs from resolved lens policy",
            )
        if project_review_status == "required":
            _validate_ready_project_lens_ids(
                blind_review, required_lens_ids=required_lens_ids
            )
        for review in current_reviews:
            if not _review_coverage_allows_ready(review):
                fail(
                    artifact_id=review["artifact_id"],
                    field="payload.coverage_status",
                    invariant="ready_requires_complete_review_coverage",
                    detail="Initial review coverage is incomplete",
                )
            if not _project_coverage_allows_ready(
                review, project_review_status=project_review_status
            ):
                fail(
                    artifact_id=review["artifact_id"],
                    field="payload.project_coverage_status",
                    invariant="ready_project_coverage_must_match_resolved_lenses",
                    detail="Review project coverage differs from resolved lens policy",
                )
            if project_review_status == "required":
                _validate_ready_project_lens_ids(
                    review, required_lens_ids=required_lens_ids
                )
        _validate_ready_blocking_findings(
            final_review=final_review,
            reviews=reconciliation_reviews,
            manifests=manifests,
            artifacts=artifacts,
            latest_lifecycle=latest_lifecycle,
        )
        required_gates = [
            *blind_review["payload"]["required_gates"],
            *[
                requirement
                for review in current_reviews
                for requirement in review["payload"]["required_gates"]
            ],
        ]
        current_gates = [
            artifact
            for artifact in current_artifacts
            if artifact["artifact_type"] == "gate"
        ]

        def validate_ready_gate_dependencies(gate: dict[str, Any]) -> None:
            dependency_refs = [
                gate["payload"]["evidence_ref"],
                gate["payload"]["pre_target_check_ref"],
                gate["payload"]["post_target_check_ref"],
            ]
            if any(
                latest_lifecycle.get(ref["artifact_id"], (None, None))[0] != "current"
                for ref in dependency_refs
            ) or artifacts[gate["payload"]["evidence_ref"]["artifact_id"]]["payload"][
                "completeness"
            ] not in {"full", "redacted"}:
                fail(
                    artifact_id=gate["artifact_id"],
                    field="payload",
                    invariant="ready_gate_dependencies_must_be_current_complete_evidence",
                    detail="Gate depends on historical/invalidated/truncated artifacts",
                )

        docs_gates = [
            gate
            for gate in current_gates
            if gate["payload"]["gate_name"] == "sync-docs-code"
            and gate["payload"]["execution_status"] == "succeeded"
            and gate["payload"]["decision_status"] in READY_GATE_SUCCESS_STATUSES
            and not gate["payload"]["mutated_target"]
        ]
        if len(docs_gates) != 1:
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.state",
                invariant="ready_requires_one_successful_docs_gate",
                detail="sync-docs-code gate is missing or ambiguous",
            )
        validate_ready_gate_dependencies(docs_gates[0])
        for requirement in required_gates:
            if requirement["target_ref"] != current_target_ref:
                fail(
                    artifact_id=ready_manifest["artifact_id"],
                    field="payload.state",
                    invariant="ready_required_gate_must_name_current_target",
                    detail=f"Gate {requirement['gate_name']} names another target",
                )
            matches = [
                gate
                for gate in current_gates
                if gate["payload"]["gate_name"] == requirement["gate_name"]
                and gate["target_ref"] == requirement["target_ref"]
                and gate["payload"]["decision_status"]
                in requirement["accepted_decision_statuses"]
                and gate["payload"]["decision_status"] in READY_GATE_SUCCESS_STATUSES
                and gate["payload"]["execution_status"] == "succeeded"
                and not gate["payload"]["mutated_target"]
            ]
            if len(matches) != 1:
                fail(
                    artifact_id=ready_manifest["artifact_id"],
                    field="payload.state",
                    invariant="ready_requires_each_declared_gate_exactly_once",
                    detail=f"Gate requirement not satisfied: {requirement['gate_name']}",
                )
            gate = matches[0]
            validate_ready_gate_dependencies(gate)
            if (
                gate["payload"]["gate_name"] == "sync-docs-code"
                and gate["payload"]["decision_status"]
                not in READY_GATE_SUCCESS_STATUSES
            ):
                fail(
                    artifact_id=gate["artifact_id"],
                    field="payload.decision_status",
                    invariant="docs_gate_ready_status_must_be_pass_or_updated",
                    detail="Docs gate status does not permit READY",
                )
        ready_cause_ref = ready_manifest["payload"]["transition_cause_ref"]
        ready_cause = artifacts.get(ready_cause_ref["artifact_id"])
        latest_support_sequence = max(
            artifact["monotonic_sequence"]
            for artifact in current_artifacts
            if artifact["artifact_type"]
            in {"verification", "gate", "blind_review", "final_review"}
        )
        if (
            ready_cause is None
            or ready_cause["artifact_type"] != "target_check"
            or ready_cause["payload"]["status"] != "unchanged"
            or latest_lifecycle.get(ready_cause["artifact_id"], (None, None))[0]
            != "current"
            or ready_cause["monotonic_sequence"] <= latest_support_sequence
        ):
            fail(
                artifact_id=ready_manifest["artifact_id"],
                field="payload.transition_cause_ref",
                invariant="ready_requires_fresh_post_stage_unchanged_target_check",
                detail="READY transition is not caused by the final unchanged target check",
            )
        for ref in ready_cause["payload"]["observation_evidence_refs"]:
            evidence = artifacts[ref["artifact_id"]]
            if latest_lifecycle.get(ref["artifact_id"], (None, None))[
                0
            ] != "current" or evidence["payload"]["completeness"] not in {
                "full",
                "redacted",
            }:
                fail(
                    artifact_id=ready_cause["artifact_id"],
                    field="payload.observation_evidence_refs",
                    invariant="ready_target_check_evidence_must_be_current_and_complete",
                    detail="READY target check uses non-current or truncated Evidence",
                )
        for artifact in current_artifacts:
            if (
                artifact["artifact_type"] in {"verification", "gate"}
                and artifact["payload"]["mutated_target"]
            ):
                fail(
                    artifact_id=artifact["artifact_id"],
                    field="payload.mutated_target",
                    invariant="mutating_stage_must_not_support_ready",
                    detail="A target-mutating stage cannot support READY",
                )


def _validate_content_bindings(
    reader: _LedgerReader, artifacts: dict[str, dict[str, Any]]
) -> None:
    for artifact in artifacts.values():
        artifact_id = artifact["artifact_id"]
        if (
            artifact["artifact_type"] == "evidence"
            and artifact["payload"].get("content_path") is not None
        ):
            payload = artifact["payload"]
            content = reader.read(payload["content_path"])
            actual_hash = sha256_hex(content)
            if actual_hash != payload["content_sha256"] or payload[
                "content_path"
            ] != object_path(actual_hash):
                fail(
                    artifact_id=artifact_id,
                    field="payload.content_path",
                    invariant="evidence_content_path_hash_and_bytes_must_match",
                    detail="Evidence bytes do not match content path/hash",
                )
        if artifact["artifact_type"] != "target":
            continue
        payload = artifact["payload"]
        fingerprint = payload["popr_target_fingerprint"]
        object_format = fingerprint["git_object_format"]
        working_tree = require_dict(
            fingerprint["working_tree"],
            artifact_id=artifact_id,
            field="payload.popr_target_fingerprint.working_tree",
        )
        entries = working_tree.get("entries")
        if not isinstance(entries, list):
            fail(
                artifact_id=artifact_id,
                field="payload.popr_target_fingerprint.working_tree.entries",
                invariant="working_tree_entries_must_be_array",
                detail="Working tree entries are required",
            )
        present_entry_values = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("status") == "present"
        ]
        present_keys = [
            (entry.get("path"), entry.get("mode"), entry.get("type"))
            for entry in present_entry_values
        ]
        if len(present_keys) != len(set(present_keys)):
            fail(
                artifact_id=artifact_id,
                field="payload.popr_target_fingerprint.working_tree.entries",
                invariant="mutable_fingerprint_entries_must_be_unique",
                detail="Multiple present fingerprint entries share path/mode/type",
            )
        present_entries = dict(zip(present_keys, present_entry_values, strict=True))
        snapshots = payload["mutable_content_snapshots"]
        snapshot_keys: set[tuple[Any, Any, Any]] = set()
        for snapshot in snapshots:
            key = (snapshot["path"], snapshot["mode"], snapshot["type"])
            if key in snapshot_keys or key not in present_entries:
                fail(
                    artifact_id=artifact_id,
                    field="payload.mutable_content_snapshots",
                    invariant="mutable_snapshot_must_bind_one_fingerprint_entry",
                    detail=f"Duplicate or unmatched mutable snapshot: {key}",
                )
            snapshot_keys.add(key)
            content = reader.read(snapshot["content_path"])
            actual_hash = sha256_hex(content)
            actual_oid = git_blob_oid(content, object_format)
            entry = present_entries[key]
            if (
                len(content) != snapshot["byte_length"]
                or actual_hash != snapshot["content_sha256"]
                or snapshot["content_path"] != object_path(actual_hash)
                or actual_oid != snapshot["content_oid"]
                or actual_oid != entry.get("content_oid")
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.mutable_content_snapshots",
                    invariant="mutable_snapshot_bytes_hash_oid_and_fingerprint_must_match",
                    detail=f"Mutable content binding failed for {snapshot['path']}",
                )
        if (
            set(present_entries) != snapshot_keys
            and working_tree.get("mode") == "included"
        ):
            missing = sorted(set(present_entries) - snapshot_keys)
            fail(
                artifact_id=artifact_id,
                field="payload.mutable_content_snapshots",
                invariant="included_mutable_entries_must_have_exact_snapshots",
                detail=f"Missing mutable snapshots: {missing}",
            )
        index_diff = fingerprint["index_diff"]
        if index_diff["included"]:
            snapshot = payload["index_diff_snapshot"]
            content = reader.read(snapshot["content_path"])
            actual_hash = sha256_hex(content)
            actual_oid = git_blob_oid(content, object_format)
            if (
                len(content) != snapshot["byte_length"]
                or actual_hash != snapshot["content_sha256"]
                or snapshot["content_path"] != object_path(actual_hash)
                or actual_oid != index_diff["content_oid"]
            ):
                fail(
                    artifact_id=artifact_id,
                    field="payload.index_diff_snapshot",
                    invariant="index_diff_bytes_hash_oid_and_fingerprint_must_match",
                    detail="Index diff snapshot does not bind to the fingerprint",
                )


def validate_ledger(
    store: SafeDirectory,
    *,
    repository_id: str,
    run_id: str,
    overlay: dict[str, bytes] | None = None,
    head_override: bytes | None = None,
    reject_active_transactions: bool = True,
) -> LedgerSnapshot:
    """Validate a run without mutating it; overlay supports append preflight."""

    validate_repository_id(repository_id)
    validate_identifier(run_id, field="run_id")
    if reject_active_transactions:
        active = active_transaction_ids(store)
        if active:
            fail(
                artifact_id=None,
                field="transactions",
                invariant="active_transaction_requires_explicit_recovery",
                detail=f"Active transactions: {active}",
            )
    transaction_records = _validate_transaction_records(
        store,
        repository_id=repository_id,
        run_id=run_id,
    )
    reader = _LedgerReader(store, overlay)
    head_bytes = (
        head_override if head_override is not None else reader.read("HEAD.json")
    )
    head = validate_head(require_canonical_json(head_bytes, field="HEAD.json"))
    manifests, manifest_bytes = _load_manifest_chain(reader, run_id=run_id, head=head)
    _validate_manifest_transaction_correspondence(
        manifests,
        transaction_records,
        overlay=overlay,
    )
    artifacts, artifact_bytes, artifact_refs = _load_artifacts(
        reader, manifests, run_id=run_id
    )
    _validate_manifest_limits_and_counters(manifests, artifacts)
    max_sequence = _validate_sequences(manifests, artifacts)
    _validate_stage_checkpoints(manifests, artifacts)
    _validate_graph(manifests, artifacts)
    _validate_lifecycle(manifests, artifacts)
    _validate_typed_refs_and_state_evidence(manifests, artifacts)
    if manifests:
        _validate_repository_identity(repository_id, manifests, artifacts)
        _validate_targets_and_inputs(manifests, artifacts)
        _validate_content_bindings(reader, artifacts)
    return LedgerSnapshot(
        repository_id=repository_id,
        run_id=run_id,
        head=head,
        head_bytes=head_bytes,
        manifests=manifests,
        manifest_bytes=manifest_bytes,
        artifacts=artifacts,
        artifact_bytes=artifact_bytes,
        artifact_refs=artifact_refs,
        max_sequence=max_sequence,
    )
