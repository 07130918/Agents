"""Command-line boundary for the artifact writer, validator, and recovery path."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import CONTRACT_VERSION
from .canonical import (
    canonicalize,
    encode_base64,
    load_json,
    object_path,
    parse_json_bytes,
    sha256_hex,
)
from .contract import artifact_common_ref, validate_artifact_shape
from .errors import ArtifactError, ijson_safe_value
from .recovery import build_recovery_report, new_report_id, recover_run
from .safe_fs import StoreLocation, create_run_store, open_run_store
from .validator import (
    LedgerSnapshot,
    active_transaction_ids,
    descriptorless_transaction_ids,
    validate_ledger,
)
from .writer import append_batch

DEFAULT_STATE_ROOT = Path("~/.agents/state")


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ArtifactError(
            artifact_id=None,
            field="argv",
            invariant="cli_arguments_must_be_valid",
            detail=message,
        )


def _write_json(value: Any, *, stream: Any = sys.stdout) -> None:
    stream.buffer.write(canonicalize(ijson_safe_value(value)) + b"\n")
    stream.flush()


def _snapshot_value(snapshot: LedgerSnapshot, *, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "repository_id": snapshot.repository_id,
        "run_id": snapshot.run_id,
        "head": snapshot.head,
        "manifest_count": len(snapshot.manifests),
        "artifact_count": len(snapshot.artifacts),
        "max_sequence": snapshot.max_sequence,
        "diagnostics": snapshot.diagnostics,
    }


def _location_from_args(
    args: argparse.Namespace,
    *,
    require_candidate: bool,
    create_state_root: bool,
) -> StoreLocation:
    candidate = Path(args.candidate_worktree) if require_candidate else None
    return StoreLocation.resolve(
        state_root=Path(args.state_root),
        repository_id=args.repository_id,
        run_id=args.run_id,
        candidate_worktree=candidate,
        create_state_root=create_state_root,
    )


def _canonicalize_command(args: argparse.Namespace) -> int:
    try:
        raw = Path(args.input).read_bytes()
    except OSError as error:
        raise ArtifactError(
            artifact_id=None,
            field=str(args.input),
            invariant="input_file_must_be_readable",
            detail=str(error),
        ) from error
    value = parse_json_bytes(raw, field=str(args.input))
    content = canonicalize(value)
    content_hash = sha256_hex(content)
    destination = object_path(content_hash)
    artifact_id: str | None = None
    if isinstance(value, dict) and "artifact_type" in value:
        artifact = validate_artifact_shape(value)
        common_ref = artifact_common_ref(artifact)
        destination = common_ref["artifact_path"]
        artifact_id = artifact["artifact_id"]
    _write_json(
        {
            "status": "canonicalized",
            "artifact_id": artifact_id,
            "sha256": content_hash,
            "byte_length": len(content),
            "destination_path": destination,
            "canonical_base64": encode_base64(content),
        }
    )
    return 0


def _append_command(args: argparse.Namespace) -> int:
    location = _location_from_args(
        args,
        require_candidate=True,
        create_state_root=True,
    )
    batch = load_json(Path(args.batch))
    with create_run_store(location) as store:
        snapshot = append_batch(
            store,
            repository_id=location.repository_id,
            run_id=location.run_id,
            batch_value=batch,
        )
    _write_json(_snapshot_value(snapshot, status="appended"))
    return 0


def _validate_command(args: argparse.Namespace) -> int:
    location = _location_from_args(
        args,
        require_candidate=False,
        create_state_root=False,
    )
    with open_run_store(location) as store:
        try:
            snapshot = validate_ledger(
                store,
                repository_id=location.repository_id,
                run_id=location.run_id,
            )
        except ArtifactError as error:
            active: list[str] = []
            descriptorless: list[str] = []
            try:
                active = active_transaction_ids(store)
                descriptorless = descriptorless_transaction_ids(store)
            except ArtifactError:
                pass
            transaction_id: str | None = None
            if descriptorless:
                violation_kind = "transaction_unrecoverable"
                if len(descriptorless) == 1:
                    transaction_id = descriptorless[0]
            elif len(active) > 1:
                violation_kind = "active_transaction_ambiguous"
            else:
                violation_kind = "ledger_corruption"
                if len(active) == 1:
                    transaction_id = active[0]
            report = build_recovery_report(
                location=location,
                store=store,
                error=error,
                report_id=args.report_id or new_report_id(),
                transaction_id=transaction_id,
                violation_kind=violation_kind,
            )
            _write_json({"status": "invalid", "report": report})
            return 2
    _write_json(_snapshot_value(snapshot, status="valid"))
    return 0


def _recover_command(args: argparse.Namespace) -> int:
    location = _location_from_args(
        args,
        require_candidate=True,
        create_state_root=False,
    )
    with open_run_store(location) as store:
        result = recover_run(
            location=location,
            store=store,
            report_id=args.report_id,
        )
    if result.snapshot is not None:
        _write_json(_snapshot_value(result.snapshot, status=result.status))
        return 0
    _write_json(
        {
            "status": result.status,
            "report": result.report,
            "report_path": result.report_path,
            "report_saved": result.report_saved,
            "report_save_error": result.report_save_error,
        }
    )
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = StructuredArgumentParser(prog="review-harness-artifacts")
    parser.add_argument("--version", action="version", version=CONTRACT_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    canonicalize_parser = commands.add_parser(
        "canonicalize",
        help="Strictly parse JSON and return its canonical bytes metadata",
    )
    canonicalize_parser.add_argument("--input", required=True)
    canonicalize_parser.set_defaults(handler=_canonicalize_command)

    def add_run_arguments(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
        command_parser.add_argument("--repository-id", required=True)
        command_parser.add_argument("--run-id", required=True)

    append_parser = commands.add_parser(
        "append", help="Append one versioned transaction batch"
    )
    add_run_arguments(append_parser)
    append_parser.add_argument("--candidate-worktree", required=True)
    append_parser.add_argument("--batch", required=True)
    append_parser.set_defaults(handler=_append_command)

    validate_parser = commands.add_parser(
        "validate", help="Read-only validation of one run"
    )
    add_run_arguments(validate_parser)
    validate_parser.add_argument("--report-id")
    validate_parser.set_defaults(handler=_validate_command)

    recover_parser = commands.add_parser(
        "recover", help="Complete one uniquely safe transaction"
    )
    add_run_arguments(recover_parser)
    recover_parser.add_argument("--candidate-worktree", required=True)
    recover_parser.add_argument("--report-id")
    recover_parser.set_defaults(handler=_recover_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        handler = args.handler
        return int(handler(args))
    except ArtifactError as error:
        _write_json({"status": "error", "error": error.as_dict()}, stream=sys.stderr)
        return 2
    except Exception as unexpected:  # noqa: BLE001 - CLI must fail closed with structured JSON.
        error = ArtifactError(
            artifact_id=None,
            field="command",
            invariant="unexpected_command_failure",
            detail=f"{type(unexpected).__name__}: {unexpected}",
        )
        _write_json({"status": "error", "error": error.as_dict()}, stream=sys.stderr)
        return 2
