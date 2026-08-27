"""Conservative transaction completion and ledger-external recovery reports."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from . import TRANSACTION_VERSION
from .canonical import (
    canonicalize,
    encode_base64,
    require_canonical_json,
    sha256_hex,
)
from .contract import validate_identifier
from .errors import ArtifactError, fail, ijson_safe_value
from .safe_fs import SafeDirectory, StoreLocation, open_state_root
from .validator import (
    LedgerSnapshot,
    active_transaction_ids,
    descriptorless_transaction_ids,
    validate_ledger,
)
from .writer import install_descriptor, validate_descriptor, validate_descriptor_files


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    status: str
    snapshot: LedgerSnapshot | None
    report: dict[str, Any] | None
    report_path: str | None
    report_saved: bool
    report_save_error: dict[str, Any] | None = None


def _now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def new_report_id() -> str:
    return f"recovery-{uuid.uuid4().hex}"


def _observe_head(store: SafeDirectory) -> tuple[str | None, str | None, list[str]]:
    diagnostics: list[str] = []
    try:
        content = store.read_bytes("HEAD.json")
    except ArtifactError as error:
        diagnostics.append(f"HEAD.json could not be read safely: {error.detail}")
        return None, None, diagnostics
    return encode_base64(content), sha256_hex(content), diagnostics


def _observe_manifests(store: SafeDirectory) -> tuple[list[dict[str, str]], list[str]]:
    observations: list[dict[str, str]] = []
    diagnostics: list[str] = []
    try:
        names = store.list_names("manifests")
    except ArtifactError as error:
        diagnostics.append(
            f"manifests directory could not be listed safely: {error.detail}"
        )
        return observations, diagnostics
    for name in names:
        path = f"manifests/{name}"
        try:
            observations.append(
                {"path": path, "sha256": sha256_hex(store.read_bytes(path))}
            )
        except ArtifactError as error:
            diagnostics.append(f"{path} could not be read safely: {error.detail}")
    return observations, diagnostics


def _observe_descriptor(
    store: SafeDirectory,
    transaction_id: str | None,
) -> tuple[str | None, list[str]]:
    if transaction_id is None:
        return None, []
    path = f"transactions/{transaction_id}/descriptor.json"
    try:
        return sha256_hex(store.read_bytes(path)), []
    except ArtifactError as error:
        return None, [f"{path} could not be read safely: {error.detail}"]


def build_recovery_report(
    *,
    location: StoreLocation,
    store: SafeDirectory,
    error: ArtifactError,
    report_id: str,
    transaction_id: str | None,
    violation_kind: str,
) -> dict[str, Any]:
    validate_identifier(report_id, field="report_id")
    observed_head_base64, observed_head_sha256, diagnostics = _observe_head(store)
    observed_manifests, manifest_diagnostics = _observe_manifests(store)
    descriptor_sha256, descriptor_diagnostics = _observe_descriptor(
        store, transaction_id
    )
    diagnostics.extend(manifest_diagnostics)
    diagnostics.extend(descriptor_diagnostics)
    diagnostics.append(error.detail)
    required_human_action = (
        "start_new_run"
        if violation_kind
        in {"active_transaction_ambiguous", "transaction_unrecoverable"}
        else "restore_verified_store"
    )
    report = {
        "report_version": TRANSACTION_VERSION,
        "report_id": report_id,
        "repository_id": location.repository_id,
        "run_id": location.run_id,
        "observed_at": _now(),
        "observed_head_base64": observed_head_base64,
        "observed_head_sha256": observed_head_sha256,
        "observed_manifests": observed_manifests,
        "transaction_id": transaction_id,
        "descriptor_sha256": descriptor_sha256,
        "violation_kind": violation_kind,
        "field": error.field,
        "invariant": error.invariant,
        "detail": error.detail,
        "diagnostics": diagnostics,
        "required_human_action": required_human_action,
    }
    return {key: ijson_safe_value(value) for key, value in report.items()}


def save_recovery_report(
    *,
    location: StoreLocation,
    report: dict[str, Any],
) -> str:
    report_id = validate_identifier(report["report_id"], field="report_id")
    relative_path = f"recovery-reports/{location.repository_id}/{location.run_id}/{report_id}/report.json"
    with open_state_root(location) as root:
        root.write_exclusive(relative_path, canonicalize(report))
    return str(location.state_root / relative_path)


def _descriptor_for_active_transaction(
    store: SafeDirectory,
    *,
    location: StoreLocation,
    transaction_id: str,
) -> tuple[dict[str, Any], bytes]:
    descriptor_path = f"transactions/{transaction_id}/descriptor.json"
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
        descriptor["repository_id"] != location.repository_id
        or descriptor["run_id"] != location.run_id
    ):
        fail(
            artifact_id=None,
            field=descriptor_path,
            invariant="descriptor_scope_must_match_run_directory",
            detail="Descriptor repository_id/run_id differs from its run directory",
        )
    validate_descriptor_files(store, descriptor)
    return descriptor, descriptor_bytes


def _complete_unique_transaction(
    *,
    location: StoreLocation,
    store: SafeDirectory,
    transaction_id: str,
) -> LedgerSnapshot:
    descriptor, descriptor_bytes = _descriptor_for_active_transaction(
        store,
        location=location,
        transaction_id=transaction_id,
    )
    current_head_bytes = store.read_bytes("HEAD.json")
    expected_head_bytes = canonicalize(descriptor["expected_head"])
    proposed_head_bytes = canonicalize(descriptor["proposed_head"])
    if current_head_bytes not in {expected_head_bytes, proposed_head_bytes}:
        fail(
            artifact_id=None,
            field="HEAD.json",
            invariant="recovery_head_must_match_descriptor_expected_or_proposed",
            detail="Current HEAD is neither the expected nor proposed descriptor head",
        )
    overlay = {
        write["destination_path"]: store.read_bytes(write["staged_path"])
        for write in descriptor["writes"]
    }
    validate_ledger(
        store,
        repository_id=location.repository_id,
        run_id=location.run_id,
        overlay=overlay,
        head_override=proposed_head_bytes,
        reject_active_transactions=False,
    )
    install_descriptor(store, descriptor, descriptor_bytes)
    return validate_ledger(
        store,
        repository_id=location.repository_id,
        run_id=location.run_id,
        reject_active_transactions=True,
    )


def _sync_validated_committed_state(store: SafeDirectory) -> None:
    """Re-establish durability after a crash may have exposed an unsynced marker."""

    marker_paths: list[str] = []
    for transaction_id in store.list_names("transactions"):
        descriptor_path = f"transactions/{transaction_id}/descriptor.json"
        marker_path = f"transactions/{transaction_id}/committed.json"
        if not store.exists(descriptor_path) or not store.exists(marker_path):
            continue
        descriptor = validate_descriptor(
            require_canonical_json(
                store.read_bytes(descriptor_path), field=descriptor_path
            )
        )
        for write in descriptor["writes"]:
            store.sync_file(write["staged_path"])
            store.sync_file(write["destination_path"])
        store.sync_file(descriptor_path)
        marker_paths.append(marker_path)
    store.sync_file("HEAD.json")
    store.sync_root()
    for marker_path in marker_paths:
        store.sync_file(marker_path)
    store.sync_root()


def _recovery_failure_result(
    *,
    location: StoreLocation,
    store: SafeDirectory,
    error: ArtifactError,
    report_id: str,
    transaction_id: str | None,
    violation_kind: str,
) -> RecoveryResult:
    report = build_recovery_report(
        location=location,
        store=store,
        error=error,
        report_id=report_id,
        transaction_id=transaction_id,
        violation_kind=violation_kind,
    )
    try:
        report_path = save_recovery_report(location=location, report=report)
    except ArtifactError as save_error:
        return RecoveryResult(
            status="recovery_required",
            snapshot=None,
            report=report,
            report_path=None,
            report_saved=False,
            report_save_error=save_error.as_dict(),
        )
    return RecoveryResult(
        status="recovery_required",
        snapshot=None,
        report=report,
        report_path=report_path,
        report_saved=True,
    )


def recover_run(
    *,
    location: StoreLocation,
    store: SafeDirectory,
    report_id: str | None = None,
) -> RecoveryResult:
    """Complete one uniquely recoverable transaction; otherwise write an external report."""

    selected_report_id = report_id or new_report_id()
    validate_identifier(selected_report_id, field="report_id")
    transaction_id: str | None = None
    violation_kind = "ledger_corruption"
    try:
        with store.exclusive_lock():
            active = active_transaction_ids(store)
            descriptorless = descriptorless_transaction_ids(store)
            if descriptorless:
                violation_kind = "transaction_unrecoverable"
                if len(descriptorless) == 1:
                    transaction_id = descriptorless[0]
                fail(
                    artifact_id=None,
                    field="transactions",
                    invariant="recovery_requires_published_transaction_descriptor",
                    detail=(
                        "Transaction directories without descriptor.json: "
                        f"{descriptorless}"
                    ),
                )
            if len(active) > 1:
                violation_kind = "active_transaction_ambiguous"
                fail(
                    artifact_id=None,
                    field="transactions",
                    invariant="recovery_requires_at_most_one_active_transaction",
                    detail=f"Active transactions: {active}",
                )
            if not active:
                snapshot = validate_ledger(
                    store,
                    repository_id=location.repository_id,
                    run_id=location.run_id,
                    reject_active_transactions=True,
                )
                _sync_validated_committed_state(store)
                return RecoveryResult(
                    status="healthy",
                    snapshot=snapshot,
                    report=None,
                    report_path=None,
                    report_saved=False,
                )
            transaction_id = active[0]
            violation_kind = "transaction_unrecoverable"
            snapshot = _complete_unique_transaction(
                location=location,
                store=store,
                transaction_id=transaction_id,
            )
            return RecoveryResult(
                status="recovered",
                snapshot=snapshot,
                report=None,
                report_path=None,
                report_saved=False,
            )
    except ArtifactError as error:
        return _recovery_failure_result(
            location=location,
            store=store,
            error=error,
            report_id=selected_report_id,
            transaction_id=transaction_id,
            violation_kind=violation_kind,
        )
    except Exception as unexpected:  # noqa: BLE001 - recovery must emit an external report.
        error = ArtifactError(
            artifact_id=None,
            field="recovery",
            invariant="unexpected_recovery_validation_failure",
            detail=f"{type(unexpected).__name__}: {unexpected}",
        )
        return _recovery_failure_result(
            location=location,
            store=store,
            error=error,
            report_id=selected_report_id,
            transaction_id=transaction_id,
            violation_kind=violation_kind,
        )
