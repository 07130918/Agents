"""Single-writer append transaction protocol."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from . import TRANSACTION_VERSION
from .canonical import (
    canonicalize,
    decode_base64,
    manifest_path,
    object_path,
    sha256_hex,
)
from .contract import (
    artifact_common_ref,
    require_dict,
    require_exact_fields,
    require_integer,
    require_list,
    require_string,
    validate_artifact_shape,
    validate_hash,
    validate_identifier,
    validate_repository_id,
    validate_run_relative_path,
)
from .errors import ArtifactError, fail
from .safe_fs import SafeDirectory
from .validator import (
    LedgerSnapshot,
    active_transaction_ids,
    initial_head_bytes,
    validate_head,
    validate_ledger,
)

CrashHook = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class PreparedWrite:
    write_index: int
    kind: str
    content_type: str
    artifact_id: str | None
    content: bytes
    sha256: str
    destination_path: str
    staged_path: str

    def descriptor_value(self) -> dict[str, Any]:
        return {
            "write_index": self.write_index,
            "kind": self.kind,
            "content_type": self.content_type,
            "staged_path": self.staged_path,
            "destination_path": self.destination_path,
            "sha256": self.sha256,
            "byte_length": len(self.content),
            "artifact_id": self.artifact_id,
        }


@dataclass(frozen=True, slots=True)
class PreparedTransaction:
    repository_id: str
    run_id: str
    transaction_id: str
    expected_head: dict[str, Any]
    proposed_head: dict[str, Any]
    next_manifest_revision: int
    sequence_start: int
    sequence_end: int
    writes: tuple[PreparedWrite, ...]

    def descriptor_value(self) -> dict[str, Any]:
        return {
            "descriptor_version": TRANSACTION_VERSION,
            "repository_id": self.repository_id,
            "run_id": self.run_id,
            "transaction_id": self.transaction_id,
            "expected_head": self.expected_head,
            "proposed_head": self.proposed_head,
            "next_manifest_revision": self.next_manifest_revision,
            "sequence_range": {
                "start": self.sequence_start,
                "end": self.sequence_end,
            },
            "writes": [write.descriptor_value() for write in self.writes],
        }


def _checkpoint(hook: CrashHook | None, name: str) -> None:
    if hook is not None:
        hook(name)


def bootstrap_store(store: SafeDirectory) -> None:
    store.ensure_directory("manifests")
    store.ensure_directory("objects/sha256")
    store.ensure_directory("transactions")
    if not store.exists("HEAD.json"):
        try:
            store.write_exclusive("HEAD.json", initial_head_bytes())
        except ArtifactError as error:
            if (
                error.invariant != "file_must_be_created_exclusively"
                or not store.exists("HEAD.json")
            ):
                raise


def _validate_batch_shape(value: Any) -> dict[str, Any]:
    batch = require_dict(value, artifact_id=None, field="batch")
    require_exact_fields(
        batch,
        {"batch_version", "transaction_id", "expected_head", "writes"},
        artifact_id=None,
        field="batch",
    )
    if batch["batch_version"] != TRANSACTION_VERSION:
        fail(
            artifact_id=None,
            field="batch.batch_version",
            invariant="batch_version_must_be_supported",
            detail=f"Expected {TRANSACTION_VERSION}, got {batch['batch_version']}",
        )
    validate_identifier(batch["transaction_id"], field="batch.transaction_id")
    validate_head(batch["expected_head"])
    writes = require_list(batch["writes"], artifact_id=None, field="batch.writes")
    if not writes:
        fail(
            artifact_id=None,
            field="batch.writes",
            invariant="batch_must_have_writes",
            detail="Append batch cannot be empty",
        )
    return batch


def prepare_transaction(
    batch_value: Any,
    *,
    store: SafeDirectory,
    snapshot: LedgerSnapshot,
) -> PreparedTransaction:
    batch = _validate_batch_shape(batch_value)
    if batch["expected_head"] != snapshot.head:
        fail(
            artifact_id=None,
            field="batch.expected_head",
            invariant="batch_expected_head_must_match_current_head",
            detail=f"Expected {snapshot.head}, got {batch['expected_head']}",
        )
    transaction_id = batch["transaction_id"]
    writes: list[PreparedWrite] = []
    manifest_count = 0
    artifact_sequences: list[int] = []
    destination_paths: set[str] = set()
    for index, write_value in enumerate(batch["writes"]):
        field = f"batch.writes[{index}]"
        write = require_dict(write_value, artifact_id=None, field=field)
        common = {"kind", "content_type", "artifact_id"}
        artifact_id_hint = (
            write.get("artifact_id")
            if isinstance(write.get("artifact_id"), str)
            else None
        )
        content_type = require_string(
            write.get("content_type"),
            artifact_id=artifact_id_hint,
            field=f"{field}.content_type",
        )
        write_kind = require_string(
            write.get("kind"), artifact_id=artifact_id_hint, field=f"{field}.kind"
        )
        if content_type == "artifact_json":
            require_exact_fields(
                write,
                common | {"content"},
                artifact_id=write.get("artifact_id"),
                field=field,
            )
            artifact = validate_artifact_shape(write["content"])
            artifact_id = artifact["artifact_id"]
            if write["artifact_id"] != artifact_id:
                fail(
                    artifact_id=artifact_id,
                    field=f"{field}.artifact_id",
                    invariant="batch_artifact_id_must_match_content",
                    detail=f"Expected {artifact_id}, got {write['artifact_id']}",
                )
            content = canonicalize(artifact)
            content_hash = sha256_hex(content)
            artifact_sequences.append(artifact["monotonic_sequence"])
            if write_kind == "manifest":
                if artifact["artifact_type"] != "run_manifest":
                    fail(
                        artifact_id=artifact_id,
                        field=f"{field}.kind",
                        invariant="manifest_write_must_contain_run_manifest",
                        detail=f"Found {artifact['artifact_type']}",
                    )
                manifest_count += 1
                destination = manifest_path(artifact["payload"]["revision"])
            elif write_kind == "object":
                if artifact["artifact_type"] == "run_manifest":
                    fail(
                        artifact_id=artifact_id,
                        field=f"{field}.kind",
                        invariant="run_manifest_must_use_manifest_write_kind",
                        detail="Run manifest cannot be stored as an object",
                    )
                destination = object_path(content_hash)
            else:
                fail(
                    artifact_id=artifact_id,
                    field=f"{field}.kind",
                    invariant="write_kind_must_be_object_or_manifest",
                    detail=f"Unknown write kind: {write_kind}",
                )
        elif content_type in {"attachment", "evidence_bytes"}:
            require_exact_fields(
                write,
                common | {"content_base64"},
                artifact_id=None,
                field=field,
            )
            if write_kind != "object" or write["artifact_id"] is not None:
                fail(
                    artifact_id=None,
                    field=field,
                    invariant="raw_bytes_must_be_unidentified_object_write",
                    detail="Raw bytes require kind object and null artifact_id",
                )
            content_base64 = require_string(
                write["content_base64"],
                artifact_id=None,
                field=f"{field}.content_base64",
                allow_empty=True,
            )
            content = decode_base64(content_base64, field=f"{field}.content_base64")
            content_hash = sha256_hex(content)
            artifact_id = None
            destination = object_path(content_hash)
        else:
            fail(
                artifact_id=write.get("artifact_id"),
                field=f"{field}.content_type",
                invariant="write_content_type_must_be_known",
                detail=f"Unknown content type: {content_type}",
            )
        if destination in destination_paths:
            fail(
                artifact_id=artifact_id,
                field=f"{field}.content",
                invariant="batch_destination_must_be_unique",
                detail=f"Duplicate destination in batch: {destination}",
            )
        destination_paths.add(destination)
        writes.append(
            PreparedWrite(
                write_index=index,
                kind=write_kind,
                content_type=content_type,
                artifact_id=artifact_id,
                content=content,
                sha256=content_hash,
                destination_path=destination,
                staged_path=f"transactions/{transaction_id}/staged/{index}",
            )
        )
    if manifest_count != 1 or writes[-1].kind != "manifest":
        fail(
            artifact_id=writes[-1].artifact_id,
            field="batch.writes",
            invariant="batch_must_end_with_exactly_one_manifest",
            detail=f"Manifest count is {manifest_count}; final write kind is {writes[-1].kind}",
        )
    expected_sequence_start = snapshot.max_sequence + 1
    expected_sequences = list(
        range(
            expected_sequence_start, expected_sequence_start + len(artifact_sequences)
        )
    )
    if artifact_sequences != expected_sequences:
        fail(
            artifact_id=writes[-1].artifact_id,
            field="batch.writes",
            invariant="batch_artifact_sequences_must_continue_in_write_order",
            detail=f"Expected {expected_sequences}, got {artifact_sequences}",
        )
    manifest_artifact = batch["writes"][-1]["content"]
    next_revision = snapshot.head["revision"] + 1
    if manifest_artifact["payload"]["revision"] != next_revision:
        fail(
            artifact_id=manifest_artifact["artifact_id"],
            field="payload.revision",
            invariant="batch_manifest_revision_must_follow_head",
            detail=f"Expected {next_revision}, got {manifest_artifact['payload']['revision']}",
        )
    proposed_ref = artifact_common_ref(manifest_artifact)
    proposed_head = {"revision": next_revision, "manifest_ref": proposed_ref}
    overlay = {write.destination_path: write.content for write in writes}
    proposed_snapshot = validate_ledger(
        store=store,
        repository_id=snapshot.repository_id,
        run_id=snapshot.run_id,
        overlay=overlay,
        head_override=canonicalize(proposed_head),
        reject_active_transactions=False,
    )
    evidence_paths = {
        artifact["payload"]["content_path"]
        for artifact in proposed_snapshot.artifacts.values()
        if artifact["artifact_type"] == "evidence"
        and artifact["payload"].get("content_path") is not None
    }
    attachment_paths: set[str] = set()
    for artifact in proposed_snapshot.artifacts.values():
        if artifact["artifact_type"] != "target":
            continue
        attachment_paths.update(
            snapshot["content_path"]
            for snapshot in artifact["payload"]["mutable_content_snapshots"]
        )
        index_snapshot = artifact["payload"]["index_diff_snapshot"]
        if index_snapshot is not None:
            attachment_paths.add(index_snapshot["content_path"])
    for write in writes:
        if write.content_type == "artifact_json":
            continue
        bound_paths = (
            attachment_paths if write.content_type == "attachment" else evidence_paths
        )
        if write.destination_path not in bound_paths:
            fail(
                artifact_id=None,
                field=f"batch.writes[{write.write_index}].content_base64",
                invariant="raw_write_must_be_bound_by_matching_artifact_content_path",
                detail=(
                    f"{write.content_type} object {write.destination_path} has no "
                    "matching content-path binding"
                ),
            )
    return PreparedTransaction(
        repository_id=snapshot.repository_id,
        run_id=snapshot.run_id,
        transaction_id=transaction_id,
        expected_head=snapshot.head,
        proposed_head=proposed_head,
        next_manifest_revision=next_revision,
        sequence_start=artifact_sequences[0],
        sequence_end=artifact_sequences[-1],
        writes=tuple(writes),
    )


def validate_descriptor(value: Any) -> dict[str, Any]:
    descriptor = require_dict(value, artifact_id=None, field="descriptor")
    require_exact_fields(
        descriptor,
        {
            "descriptor_version",
            "repository_id",
            "run_id",
            "transaction_id",
            "expected_head",
            "proposed_head",
            "next_manifest_revision",
            "sequence_range",
            "writes",
        },
        artifact_id=None,
        field="descriptor",
    )
    if descriptor["descriptor_version"] != TRANSACTION_VERSION:
        fail(
            artifact_id=None,
            field="descriptor.descriptor_version",
            invariant="descriptor_version_must_be_supported",
            detail=f"Expected {TRANSACTION_VERSION}, got {descriptor['descriptor_version']}",
        )
    validate_repository_id(
        descriptor["repository_id"], field="descriptor.repository_id"
    )
    validate_identifier(descriptor["run_id"], field="descriptor.run_id")
    transaction_id = validate_identifier(
        descriptor["transaction_id"], field="descriptor.transaction_id"
    )
    expected_head = validate_head(descriptor["expected_head"])
    proposed_head = validate_head(descriptor["proposed_head"])
    next_revision = require_integer(
        descriptor["next_manifest_revision"],
        artifact_id=None,
        field="descriptor.next_manifest_revision",
    )
    if descriptor["proposed_head"]["revision"] != next_revision:
        fail(
            artifact_id=None,
            field="descriptor.proposed_head.revision",
            invariant="proposed_head_revision_must_match_descriptor",
            detail="Proposed HEAD revision differs from next_manifest_revision",
        )
    if expected_head["revision"] + 1 != next_revision:
        fail(
            artifact_id=None,
            field="descriptor.expected_head.revision",
            invariant="descriptor_next_revision_must_follow_expected_head",
            detail=f"Expected {expected_head['revision'] + 1}, got {next_revision}",
        )
    sequence_range = require_dict(
        descriptor["sequence_range"],
        artifact_id=None,
        field="descriptor.sequence_range",
    )
    require_exact_fields(
        sequence_range,
        {"start", "end"},
        artifact_id=None,
        field="descriptor.sequence_range",
    )
    start = require_integer(
        sequence_range["start"],
        artifact_id=None,
        field="descriptor.sequence_range.start",
    )
    end = require_integer(
        sequence_range["end"], artifact_id=None, field="descriptor.sequence_range.end"
    )
    if end < start:
        fail(
            artifact_id=None,
            field="descriptor.sequence_range",
            invariant="descriptor_sequence_range_must_be_ordered",
            detail=f"Invalid range {start}..{end}",
        )
    writes = require_list(
        descriptor["writes"], artifact_id=None, field="descriptor.writes"
    )
    if not writes:
        fail(
            artifact_id=None,
            field="descriptor.writes",
            invariant="descriptor_must_have_writes",
            detail="Descriptor writes cannot be empty",
        )
    artifact_sequences: list[int] = []
    destinations: set[str] = set()
    for index, write_value in enumerate(writes):
        field = f"descriptor.writes[{index}]"
        write = require_dict(write_value, artifact_id=None, field=field)
        require_exact_fields(
            write,
            {
                "write_index",
                "kind",
                "content_type",
                "staged_path",
                "destination_path",
                "sha256",
                "byte_length",
                "artifact_id",
            },
            artifact_id=write.get("artifact_id"),
            field=field,
        )
        artifact_id_hint = (
            write["artifact_id"] if isinstance(write["artifact_id"], str) else None
        )
        write_kind = require_string(
            write["kind"], artifact_id=artifact_id_hint, field=f"{field}.kind"
        )
        content_type = require_string(
            write["content_type"],
            artifact_id=artifact_id_hint,
            field=f"{field}.content_type",
        )
        if write["write_index"] != index:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.write_index",
                invariant="descriptor_write_indices_must_be_contiguous",
                detail=f"Expected {index}, got {write['write_index']}",
            )
        if write_kind not in {"object", "manifest"}:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.kind",
                invariant="descriptor_write_kind_must_be_known",
                detail=f"Unknown write kind: {write_kind}",
            )
        if content_type not in {
            "artifact_json",
            "attachment",
            "evidence_bytes",
        }:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.content_type",
                invariant="descriptor_content_type_must_be_known",
                detail=f"Unknown content type: {content_type}",
            )
        expected_staged = f"transactions/{transaction_id}/staged/{index}"
        if write["staged_path"] != expected_staged:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.staged_path",
                invariant="descriptor_staged_path_must_be_derived",
                detail=f"Expected {expected_staged}, got {write['staged_path']}",
            )
        validate_run_relative_path(
            write["destination_path"],
            artifact_id=write["artifact_id"],
            field=f"{field}.destination_path",
        )
        content_hash = validate_hash(
            write["sha256"], artifact_id=write["artifact_id"], field=f"{field}.sha256"
        )
        byte_length = require_integer(
            write["byte_length"],
            artifact_id=write["artifact_id"],
            field=f"{field}.byte_length",
        )
        if byte_length < 0:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.byte_length",
                invariant="descriptor_byte_length_must_be_nonnegative",
                detail=f"Negative byte length: {byte_length}",
            )
        destination = write["destination_path"]
        if destination in destinations:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.destination_path",
                invariant="descriptor_destinations_must_be_unique",
                detail=f"Duplicate destination: {destination}",
            )
        destinations.add(destination)
        if write_kind == "object" and destination != object_path(content_hash):
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.destination_path",
                invariant="descriptor_object_destination_must_be_hash_derived",
                detail=f"Expected {object_path(content_hash)}, got {destination}",
            )
        if content_type == "artifact_json" and write["artifact_id"] is None:
            fail(
                artifact_id=None,
                field=f"{field}.artifact_id",
                invariant="artifact_json_descriptor_must_have_artifact_id",
                detail="Artifact JSON requires an artifact ID",
            )
        if content_type != "artifact_json" and write["artifact_id"] is not None:
            fail(
                artifact_id=write["artifact_id"],
                field=f"{field}.artifact_id",
                invariant="raw_descriptor_write_must_have_null_artifact_id",
                detail="Raw bytes must not claim an artifact ID",
            )
        if write["artifact_id"] is not None:
            parts = require_string(
                write["artifact_id"],
                artifact_id=artifact_id_hint,
                field=f"{field}.artifact_id",
            ).split("/")
            if len(parts) != 3 or not parts[2].isdigit():
                fail(
                    artifact_id=write["artifact_id"],
                    field=f"{field}.artifact_id",
                    invariant="descriptor_artifact_id_must_be_valid",
                    detail=f"Invalid artifact ID: {write['artifact_id']}",
                )
            artifact_sequences.append(int(parts[2]))
    if (
        writes[-1]["kind"] != "manifest"
        or sum(write["kind"] == "manifest" for write in writes) != 1
    ):
        fail(
            artifact_id=writes[-1]["artifact_id"],
            field="descriptor.writes",
            invariant="descriptor_must_end_with_exactly_one_manifest",
            detail="Descriptor must have one final Manifest entry",
        )
    manifest_write = writes[-1]
    expected_manifest_path = manifest_path(next_revision)
    if (
        manifest_write["content_type"] != "artifact_json"
        or manifest_write["destination_path"] != expected_manifest_path
    ):
        fail(
            artifact_id=manifest_write["artifact_id"],
            field="descriptor.writes[-1]",
            invariant="descriptor_manifest_destination_must_be_revision_derived",
            detail=f"Expected artifact_json at {expected_manifest_path}",
        )
    proposed_ref = proposed_head["manifest_ref"]
    if proposed_ref != {
        "artifact_id": manifest_write["artifact_id"],
        "artifact_path": manifest_write["destination_path"],
        "sha256": manifest_write["sha256"],
    }:
        fail(
            artifact_id=manifest_write["artifact_id"],
            field="descriptor.proposed_head.manifest_ref",
            invariant="proposed_head_must_match_manifest_write",
            detail="Proposed HEAD ref differs from final Manifest write",
        )
    expected_sequences = list(range(start, end + 1))
    if artifact_sequences != expected_sequences:
        fail(
            artifact_id=None,
            field="descriptor.sequence_range",
            invariant="descriptor_sequence_range_must_match_artifact_writes",
            detail=f"Expected {expected_sequences}, got {artifact_sequences}",
        )
    return descriptor


def marker_value(
    descriptor_bytes: bytes, descriptor: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "marker_version": TRANSACTION_VERSION,
        "transaction_id": descriptor["transaction_id"],
        "descriptor_sha256": sha256_hex(descriptor_bytes),
        "committed_head": descriptor["proposed_head"],
    }


def validate_marker(
    value: Any,
    *,
    descriptor: Mapping[str, Any],
    descriptor_bytes: bytes,
) -> dict[str, Any]:
    marker = require_dict(value, artifact_id=None, field="commit_marker")
    require_exact_fields(
        marker,
        {"marker_version", "transaction_id", "descriptor_sha256", "committed_head"},
        artifact_id=None,
        field="commit_marker",
    )
    expected = marker_value(descriptor_bytes, descriptor)
    if marker != expected:
        fail(
            artifact_id=None,
            field="commit_marker",
            invariant="commit_marker_must_match_descriptor_exactly",
            detail=f"Expected {expected}, got {marker}",
        )
    return marker


def validate_descriptor_files(
    store: SafeDirectory,
    descriptor: Mapping[str, Any],
) -> None:
    """Revalidate exact staged bytes and every derived artifact destination."""

    for write in descriptor["writes"]:
        staged = store.read_bytes(write["staged_path"])
        if len(staged) != write["byte_length"] or sha256_hex(staged) != write["sha256"]:
            fail(
                artifact_id=write["artifact_id"],
                field=write["staged_path"],
                invariant="staged_bytes_must_match_descriptor",
                detail="Staged bytes length or hash differs from descriptor",
            )
        if write["content_type"] == "artifact_json":
            from .canonical import require_canonical_json

            artifact = validate_artifact_shape(
                require_canonical_json(staged, field=write["staged_path"]),
                expected_path=write["destination_path"],
            )
            if artifact["artifact_id"] != write["artifact_id"]:
                fail(
                    artifact_id=write["artifact_id"],
                    field=write["staged_path"],
                    invariant="staged_artifact_id_must_match_descriptor",
                    detail=f"Found {artifact['artifact_id']}",
                )
            expected_type = "run_manifest" if write["kind"] == "manifest" else None
            if expected_type is not None and artifact["artifact_type"] != expected_type:
                fail(
                    artifact_id=artifact["artifact_id"],
                    field="artifact_type",
                    invariant="descriptor_manifest_must_contain_run_manifest",
                    detail=f"Found {artifact['artifact_type']}",
                )


def _stage_transaction(
    store: SafeDirectory,
    transaction: PreparedTransaction,
    *,
    crash_hook: CrashHook | None,
) -> tuple[dict[str, Any], bytes]:
    transaction_root = f"transactions/{transaction.transaction_id}"
    store.ensure_directory(f"{transaction_root}/staged")
    for write in transaction.writes:
        store.write_exclusive(write.staged_path, write.content)
    _checkpoint(crash_hook, "after_staged")
    descriptor = validate_descriptor(transaction.descriptor_value())
    descriptor_bytes = canonicalize(descriptor)
    pending = f"{transaction_root}/descriptor.pending"
    committed = f"{transaction_root}/descriptor.json"
    store.write_exclusive(pending, descriptor_bytes)
    store.hard_link_no_replace(pending, committed)
    _checkpoint(crash_hook, "after_descriptor")
    return descriptor, descriptor_bytes


def install_descriptor(
    store: SafeDirectory,
    descriptor: Mapping[str, Any],
    descriptor_bytes: bytes,
    *,
    crash_hook: CrashHook | None = None,
) -> None:
    transaction_id = descriptor["transaction_id"]
    validate_descriptor_files(store, descriptor)
    for write in descriptor["writes"]:
        store.hard_link_no_replace(write["staged_path"], write["destination_path"])
    _checkpoint(crash_hook, "after_installs")
    current_head_bytes = store.read_bytes("HEAD.json")
    expected_head_bytes = canonicalize(descriptor["expected_head"])
    proposed_head_bytes = canonicalize(descriptor["proposed_head"])
    if current_head_bytes == expected_head_bytes:
        head_pending = f"transactions/{transaction_id}/head.pending"
        if store.exists(head_pending):
            if store.read_bytes(head_pending) != proposed_head_bytes:
                fail(
                    artifact_id=None,
                    field=head_pending,
                    invariant="pending_head_must_match_descriptor",
                    detail="Existing pending HEAD differs from proposed HEAD",
                )
        else:
            store.write_exclusive(head_pending, proposed_head_bytes)
        store.replace(head_pending, "HEAD.json")
    elif current_head_bytes != proposed_head_bytes:
        fail(
            artifact_id=None,
            field="HEAD.json",
            invariant="head_cas_must_match_expected_or_proposed_head",
            detail="Current HEAD is neither descriptor expected nor proposed HEAD",
        )
    else:
        store.sync_file("HEAD.json")
        store.sync_root()
    _checkpoint(crash_hook, "after_head")
    marker = canonicalize(marker_value(descriptor_bytes, descriptor))
    marker_pending = f"transactions/{transaction_id}/committed.pending"
    marker_path = f"transactions/{transaction_id}/committed.json"
    if store.exists(marker_pending):
        if store.read_bytes(marker_pending) != marker:
            fail(
                artifact_id=None,
                field=marker_pending,
                invariant="pending_commit_marker_must_match_descriptor",
                detail="Existing pending marker differs from derived marker",
            )
    else:
        store.write_exclusive(marker_pending, marker)
    _checkpoint(crash_hook, "after_marker_pending")
    store.hard_link_no_replace(marker_pending, marker_path)
    _checkpoint(crash_hook, "after_marker")


def append_batch(
    store: SafeDirectory,
    *,
    repository_id: str,
    run_id: str,
    batch_value: Any,
    crash_hook: CrashHook | None = None,
) -> LedgerSnapshot:
    with store.exclusive_lock():
        bootstrap_store(store)
        active = active_transaction_ids(store)
        if active:
            fail(
                artifact_id=None,
                field="transactions",
                invariant="append_requires_explicit_recovery_of_active_transaction",
                detail=f"Active transactions: {active}",
            )
        snapshot = validate_ledger(
            store,
            repository_id=repository_id,
            run_id=run_id,
            reject_active_transactions=False,
        )
        transaction = prepare_transaction(batch_value, store=store, snapshot=snapshot)
        descriptor, descriptor_bytes = _stage_transaction(
            store,
            transaction,
            crash_hook=crash_hook,
        )
        install_descriptor(
            store,
            descriptor,
            descriptor_bytes,
            crash_hook=crash_hook,
        )
        return validate_ledger(
            store,
            repository_id=repository_id,
            run_id=run_id,
            reject_active_transactions=True,
        )
