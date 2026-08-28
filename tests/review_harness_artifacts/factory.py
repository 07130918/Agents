"""作業記録の保存機能を試験する、再現可能なテストデータを生成する。"""

from __future__ import annotations

import base64
import copy
from pathlib import Path
from typing import Any

from review_harness_artifacts.canonical import (
    canonicalize,
    git_blob_oid,
    object_path,
    sha256_hex,
)
from review_harness_artifacts.contract import artifact_common_ref
from review_harness_artifacts.safe_fs import StoreLocation, create_run_store
from review_harness_artifacts.validator import initial_head

RUN_ID = "run-49-test"
STAGE = "CONTEXT_RESOLVING"
CREATED_AT = "2026-08-27T00:00:00Z"


def default_limits() -> dict[str, Any]:
    return {
        "max_remediation_cycles": 2,
        "max_same_request_attempts": 2,
        "max_transient_stage_retries": 1,
        "deadline_at": "2026-09-27T00:00:00Z",
        "token_budget": "unsupported",
        "paid_external_call_budget": 2,
        "allowed_write_paths": ["docs", "src"],
        "max_changed_files": 20,
        "max_diff_lines": 1000,
    }


def default_counters() -> dict[str, Any]:
    return {
        "remediation_cycles_started": 0,
        "remediation_attempts_by_request_id": {},
        "transient_retries_by_execution_key": {},
        "tokens_used": "unsupported",
        "paid_external_calls": 0,
    }


def required_test_command() -> dict[str, Any]:
    return {
        "command_id": "unit-tests",
        "argv": ["scripts/review-harness-artifacts.test.sh"],
        "effects": ["repository_read"],
        "timeout_seconds": 300,
        "required_services": [],
    }


def common_ref(artifact: dict[str, Any]) -> dict[str, Any]:
    return artifact_common_ref(artifact)


def producer(received: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "role": "orchestrator",
        "instance_id": "orchestrator-1",
        "context_id": "context-1",
        "parent_context_id": None,
        "fresh_context": True,
        "model": "test-model",
        "received_artifacts": sorted(
            copy.deepcopy(received or []), key=lambda ref: ref["artifact_id"]
        ),
    }


def artifact(
    *,
    sequence: int,
    artifact_type: str,
    payload: dict[str, Any],
    input_refs: list[dict[str, Any]] | None = None,
    target_ref: dict[str, Any] | None = None,
    received: list[dict[str, Any]] | None = None,
    run_id: str = RUN_ID,
    stage: str = STAGE,
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "artifact_type": artifact_type,
        "artifact_id": f"{run_id}/{stage}/{sequence}",
        "run_id": run_id,
        "monotonic_sequence": sequence,
        "stage": stage,
        "target_ref": copy.deepcopy(target_ref),
        "producer": producer(received),
        "input_refs": sorted(
            copy.deepcopy(input_refs or []), key=lambda ref: ref["artifact_id"]
        ),
        "created_at": CREATED_AT,
        "payload": payload,
    }


def input_snapshot(
    *,
    sequence: int,
    input_kind: str,
    content: Any,
    source_revision: str,
    trust_source: str,
    source_identifier: str | None = None,
) -> dict[str, Any]:
    content_bytes = canonicalize(content)
    return artifact(
        sequence=sequence,
        artifact_type="input_snapshot",
        payload={
            "input_kind": input_kind,
            "trust_source": trust_source,
            "source_identifier": source_identifier or f"test:{input_kind}",
            "source_sha": None,
            "source_object_id": None,
            "source_revision": source_revision,
            "content_format": "jcs_json",
            "content_sha256": sha256_hex(content_bytes),
            "content": content,
        },
    )


def valid_chain(
    *,
    run_id: str = RUN_ID,
    include_required_capability: bool = False,
    required_capability_name: str = "sync-docs-code",
    required_capability_declared_version: str | None = "1.0",
    required_capability_source_revision: str | None = None,
    project_review_status: str = "not_required",
    required_lens_ids: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """一連の正常な実行状態を表すテストデータを組み立てる。

    Args:
        run_id: テストデータへ設定する実行ID。
        include_required_capability: 外部確認機能の入力記録を含めるかどうか。
        required_capability_name: 必須となる外部確認機能の名前。
        required_capability_declared_version: 外部確認機能が宣言する版。
        required_capability_source_revision: 外部確認機能の内容を特定する改訂値。
        project_review_status: プロジェクト固有観点の確認状態。
        required_lens_ids: 必須とするプロジェクト固有観点ID。

    Returns:
        リポジトリ識別子、追記する作業記録、最新状態記録の組。
    """
    identity_content = {
        "identity_kind": "git_common_dir_realpath",
        "identity_value": "/tmp/repositories/example/.git",
    }
    identity_hash = sha256_hex(canonicalize(identity_content))
    repository_id = f"sha256-{identity_hash}"
    identity = input_snapshot(
        sequence=0,
        input_kind="repository_identity",
        content=identity_content,
        source_revision=f"sha256:{identity_hash}",
        trust_source="runtime_observed",
        source_identifier="runtime:git-common-dir",
    )
    issue = input_snapshot(
        sequence=1,
        input_kind="issue_bundle",
        content={"issue": 49, "title": "artifact harness"},
        source_revision="issue:49:revision:1",
        trust_source="external_authoritative",
    )
    contract = input_snapshot(
        sequence=2,
        input_kind="personal_contract",
        content={"contract_version": "2.0.0"},
        source_revision="version:2.0.0",
        trust_source="personal_contract",
    )
    permission = input_snapshot(
        sequence=3,
        input_kind="permission_set",
        content={"write_run_store": True, "write_candidate": True},
        source_revision="approval:test-permission",
        trust_source="human_approved_run_local",
    )
    input_artifacts = [identity, issue, contract, permission]
    if include_required_capability:
        source_content = "# sync-docs-code\n"
        capability_content = {
            "capability_name": required_capability_name,
            "declared_version": required_capability_declared_version,
            "sources": [
                {
                    "canonical_realpath": (
                        f"/Users/test/.agents/skills/{required_capability_name}/SKILL.md"
                    ),
                    "content": source_content,
                    "content_sha256": sha256_hex(source_content.encode("utf-8")),
                }
            ],
        }
        capability_hash = sha256_hex(canonicalize(capability_content))
        capability_revision = required_capability_source_revision or (
            f"version:{required_capability_declared_version}"
            if required_capability_declared_version is not None
            else f"sha256:{capability_hash}"
        )
        capability_fingerprint_version = (
            required_capability_declared_version or capability_revision
        )
        capability = input_snapshot(
            sequence=4,
            input_kind="required_capability",
            content=capability_content,
            source_revision=capability_revision,
            trust_source="personal_contract",
            source_identifier=f"skill:{required_capability_name}",
        )
        input_artifacts.append(capability)
    input_refs = sorted(
        (common_ref(item) for item in input_artifacts),
        key=lambda ref: ref["artifact_id"],
    )
    identity_ref = common_ref(identity)
    target_sequence = len(input_artifacts)
    target = artifact(
        sequence=target_sequence,
        artifact_type="target",
        input_refs=[identity_ref],
        received=[identity_ref],
        payload={
            "popr_target_fingerprint": {
                "schema_version": "1.0",
                "target_source": "working_tree",
                "git_object_format": "sha1",
                "base": {"commit": "a" * 40},
                "head": {"commit": "b" * 40},
                "working_tree": {"mode": "excluded", "entries": []},
                "index_diff": {"included": False, "content_oid": None},
                "pr_remote": None,
                "scope": {"included_paths": ["."], "excluded_paths": []},
                "skill_versions": {
                    "review-remediation-harness": "2.0.0",
                    **(
                        {required_capability_name: capability_fingerprint_version}
                        if include_required_capability
                        else {}
                    ),
                },
                "project_rules": [],
            },
            "repository_identity_ref": identity_ref,
            "generation": 0,
            "transition_reason": "initial target",
            "mutable_content_snapshots": [],
            "index_diff_snapshot": None,
        },
    )
    target_ref = common_ref(target)
    evidence_text = "exact evidence\n"
    evidence = artifact(
        sequence=target_sequence + 1,
        artifact_type="evidence",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[*input_refs, target_ref],
        payload={
            "evidence_kind": "command_output",
            "media_type": "text/plain",
            "content_sha256": sha256_hex(evidence_text.encode("utf-8")),
            "content": evidence_text,
            "completeness": "full",
            "redactions": [],
            "truncation": None,
        },
    )
    prior_refs = [*input_refs, target_ref, common_ref(evidence)]
    decision = artifact(
        sequence=target_sequence + 2,
        artifact_type="decision",
        input_refs=input_refs,
        target_ref=target_ref,
        received=prior_refs,
        payload={
            "decision_kind": "context_resolution",
            "resolution_mode": "repository_baseline",
            "contract_status": "resolved",
            "contract_ref": common_ref(contract),
            "considered_sources": [
                {"source": "issue", "status": "selected"},
                {"source": "personal_contract", "status": "selected"},
            ],
            "selected_sources": [
                {
                    "source_name": "issue",
                    "source_ref": common_ref(issue),
                    "content_sha256": issue["payload"]["content_sha256"],
                },
                {
                    "source_name": "personal_contract",
                    "source_ref": common_ref(contract),
                    "content_sha256": contract["payload"]["content_sha256"],
                },
            ],
            "authority_decisions": [
                {
                    "authority_status": "governing",
                    "source_ref": common_ref(issue),
                    "content_sha256": issue["payload"]["content_sha256"],
                }
            ],
            "resolved_source_of_truth": {
                "source_ref": common_ref(issue),
                "content_sha256": issue["payload"]["content_sha256"],
            },
            "resolved_scope": {
                "source_ref": common_ref(issue),
                "content_sha256": issue["payload"]["content_sha256"],
            },
            "resolved_lenses": {
                "project_review_status": project_review_status,
                "required_lens_ids": sorted(required_lens_ids or []),
                "source_ref": common_ref(contract),
                "content_sha256": contract["payload"]["content_sha256"],
            },
            "resolved_commands": {
                "commands": [required_test_command()],
                "source_ref": common_ref(contract),
                "content_sha256": contract["payload"]["content_sha256"],
            },
            "resolved_gates": {
                "source_ref": common_ref(contract),
                "content_sha256": contract["payload"]["content_sha256"],
            },
            "resolved_risk_triggers": {
                "source_ref": common_ref(contract),
                "content_sha256": contract["payload"]["content_sha256"],
            },
            "resolved_permissions": {
                "source_ref": common_ref(permission),
                "content_sha256": permission["payload"]["content_sha256"],
            },
            "resolved_limits": {
                "source_ref": common_ref(contract),
                "content_sha256": contract["payload"]["content_sha256"],
            },
            "unresolved_inputs": [],
        },
    )
    decision_ref = common_ref(decision)
    objects = [*input_artifacts, target, evidence, decision]
    wrappers = [
        {
            "ref": common_ref(item),
            "lifecycle_status": "current",
            "invalidation_reason_ref": None,
        }
        for item in objects
    ]
    wrappers.sort(key=lambda wrapper: wrapper["ref"]["artifact_id"])
    manifest = artifact(
        sequence=target_sequence + 3,
        artifact_type="run_manifest",
        input_refs=input_refs,
        target_ref=target_ref,
        received=sorted(
            (common_ref(item) for item in objects), key=lambda ref: ref["artifact_id"]
        ),
        payload={
            "revision": 0,
            "previous_manifest_ref": None,
            "state": STAGE,
            "previous_state": None,
            "transition_id": "transition-0",
            "transition_cause_ref": decision_ref,
            "repository_identity_ref": identity_ref,
            "target_status": "resolved",
            "target_absence_reason": None,
            "current_target_generation": 0,
            "current_target_ref": target_ref,
            "input_refs": input_refs,
            "permission_set_ref": common_ref(permission),
            "artifact_refs": wrappers,
            "limits": default_limits(),
            "counters": default_counters(),
            "input_source": "issue",
            "issue_ref": common_ref(issue),
            "scope_input_ref": None,
            "contract_status": "resolved",
            "contract_ref": common_ref(contract),
            "context_status": "resolved",
            "resolution_mode": "repository_baseline",
            "pending_reason_refs": [],
            "conflict_refs": [],
            "project_context_refs": [common_ref(contract)],
            "context_resolution_ref": decision_ref,
            "last_completed_stage": decision_ref,
            "resume_state": None,
            "blocker": None,
        },
    )
    return repository_id, objects, manifest


def valid_batch(
    *,
    transaction_id: str = "transaction-0",
    run_id: str = RUN_ID,
    include_required_capability: bool = False,
    required_capability_name: str = "sync-docs-code",
    required_capability_declared_version: str | None = "1.0",
    required_capability_source_revision: str | None = None,
    project_review_status: str = "not_required",
    required_lens_ids: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    repository_id, objects, manifest = valid_chain(
        run_id=run_id,
        include_required_capability=include_required_capability,
        required_capability_name=required_capability_name,
        required_capability_declared_version=required_capability_declared_version,
        required_capability_source_revision=required_capability_source_revision,
        project_review_status=project_review_status,
        required_lens_ids=required_lens_ids,
    )
    writes = [
        {
            "kind": "object",
            "content_type": "artifact_json",
            "artifact_id": item["artifact_id"],
            "content": item,
        }
        for item in objects
    ]
    writes.append(
        {
            "kind": "manifest",
            "content_type": "artifact_json",
            "artifact_id": manifest["artifact_id"],
            "content": manifest,
        }
    )
    return repository_id, {
        "batch_version": "1.0",
        "transaction_id": transaction_id,
        "expected_head": initial_head(),
        "writes": writes,
    }


def external_evidence_batch() -> tuple[str, dict[str, Any], bytes, str]:
    repository_id, batch = valid_batch(transaction_id="external-evidence")
    batch = copy.deepcopy(batch)
    raw = b"\x00exact stdout bytes\xff\n"
    content_hash = sha256_hex(raw)
    content_path = object_path(content_hash)
    evidence = batch["writes"][5]["content"]
    evidence["payload"].pop("content")
    evidence["payload"]["content_path"] = content_path
    evidence["payload"]["content_sha256"] = content_hash
    evidence_ref = common_ref(evidence)

    decision = batch["writes"][6]["content"]
    decision["producer"]["received_artifacts"] = [
        evidence_ref if ref["artifact_id"] == evidence["artifact_id"] else ref
        for ref in decision["producer"]["received_artifacts"]
    ]
    decision_ref = common_ref(decision)

    manifest = batch["writes"][7]["content"]
    manifest["producer"]["received_artifacts"] = [
        evidence_ref
        if ref["artifact_id"] == evidence["artifact_id"]
        else decision_ref
        if ref["artifact_id"] == decision["artifact_id"]
        else ref
        for ref in manifest["producer"]["received_artifacts"]
    ]
    for wrapper in manifest["payload"]["artifact_refs"]:
        if wrapper["ref"]["artifact_id"] == evidence["artifact_id"]:
            wrapper["ref"] = evidence_ref
        elif wrapper["ref"]["artifact_id"] == decision["artifact_id"]:
            wrapper["ref"] = decision_ref
    for field in (
        "transition_cause_ref",
        "context_resolution_ref",
        "last_completed_stage",
    ):
        manifest["payload"][field] = decision_ref

    batch["writes"].insert(
        5,
        {
            "kind": "object",
            "content_type": "evidence_bytes",
            "artifact_id": None,
            "content_base64": base64.b64encode(raw).decode("ascii"),
        },
    )
    return repository_id, batch, raw, content_path


def mutable_target_batch(
    *,
    working_content: bytes = b"\x00binary working tree\xff",
    working_type: str = "regular",
    include_snapshot: bool = True,
    deleted: bool = False,
    working_oid_override: str | None = None,
    index_oid_override: str | None = None,
) -> tuple[str, dict[str, Any], list[str]]:
    """変更中の作業ツリーを含む追記データを組み立てる。

    Args:
        working_content: 作業ツリー上のファイル内容。
        working_type: 作業ツリー項目の種別。
        include_snapshot: ファイル内容を保存データへ含めるかどうか。
        deleted: ファイルを削除済みとして扱うかどうか。
        working_oid_override: 作業ツリー側のGitオブジェクトID差し替え値。
        index_oid_override: 索引差分側のGitオブジェクトID差し替え値。

    Returns:
        リポジトリ識別子、追記データ、追加保存する本文パスの一覧。
    """
    repository_id, batch = valid_batch(transaction_id="mutable-target")
    batch = copy.deepcopy(batch)
    target = batch["writes"][4]["content"]
    working_oid = git_blob_oid(working_content, "sha1")
    working_hash = sha256_hex(working_content)
    working_path = object_path(working_hash)
    index_content = b"cached diff --binary\x00\xff\n"
    index_oid = git_blob_oid(index_content, "sha1")
    index_hash = sha256_hex(index_content)
    index_path = object_path(index_hash)
    if deleted:
        entries = [
            {
                "path": "deleted.bin",
                "status": "deleted",
                "head_mode": "100644",
                "head_type": "regular",
                "head_content_oid": "c" * 40,
            }
        ]
        snapshots: list[dict[str, Any]] = []
    else:
        mode = "120000" if working_type == "symlink" else "100644"
        entries = [
            {
                "path": "mutable.bin",
                "status": "present",
                "mode": mode,
                "type": working_type,
                "content_oid": working_oid_override or working_oid,
            }
        ]
        snapshots = (
            [
                {
                    "path": "mutable.bin",
                    "mode": mode,
                    "type": working_type,
                    "content_oid": working_oid,
                    "byte_length": len(working_content),
                    "content_sha256": working_hash,
                    "content_path": working_path,
                }
            ]
            if include_snapshot
            else []
        )
    target["payload"]["popr_target_fingerprint"]["working_tree"] = {
        "mode": "included",
        "entries": entries,
    }
    target["payload"]["popr_target_fingerprint"]["index_diff"] = {
        "included": True,
        "content_oid": index_oid_override or index_oid,
    }
    target["payload"]["mutable_content_snapshots"] = snapshots
    target["payload"]["index_diff_snapshot"] = {
        "byte_length": len(index_content),
        "content_sha256": index_hash,
        "content_path": index_path,
        "capture_environment": {"GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"},
        "capture_argv": ["git", "diff", "--cached", "--binary"],
    }
    target_ref = common_ref(target)

    evidence = batch["writes"][5]["content"]
    evidence["target_ref"] = target_ref
    evidence["producer"]["received_artifacts"] = [
        target_ref if ref["artifact_id"] == target["artifact_id"] else ref
        for ref in evidence["producer"]["received_artifacts"]
    ]
    evidence_ref = common_ref(evidence)

    decision = batch["writes"][6]["content"]
    decision["target_ref"] = target_ref
    decision["producer"]["received_artifacts"] = [
        target_ref
        if ref["artifact_id"] == target["artifact_id"]
        else evidence_ref
        if ref["artifact_id"] == evidence["artifact_id"]
        else ref
        for ref in decision["producer"]["received_artifacts"]
    ]
    decision_ref = common_ref(decision)

    manifest = batch["writes"][7]["content"]
    manifest["target_ref"] = target_ref
    manifest["payload"]["current_target_ref"] = target_ref
    manifest["producer"]["received_artifacts"] = [
        target_ref
        if ref["artifact_id"] == target["artifact_id"]
        else evidence_ref
        if ref["artifact_id"] == evidence["artifact_id"]
        else decision_ref
        if ref["artifact_id"] == decision["artifact_id"]
        else ref
        for ref in manifest["producer"]["received_artifacts"]
    ]
    for wrapper in manifest["payload"]["artifact_refs"]:
        if wrapper["ref"]["artifact_id"] == target["artifact_id"]:
            wrapper["ref"] = target_ref
        elif wrapper["ref"]["artifact_id"] == evidence["artifact_id"]:
            wrapper["ref"] = evidence_ref
        elif wrapper["ref"]["artifact_id"] == decision["artifact_id"]:
            wrapper["ref"] = decision_ref
    for field in (
        "transition_cause_ref",
        "context_resolution_ref",
        "last_completed_stage",
    ):
        manifest["payload"][field] = decision_ref

    raw_writes = [
        {
            "kind": "object",
            "content_type": "attachment",
            "artifact_id": None,
            "content_base64": base64.b64encode(index_content).decode("ascii"),
        }
    ]
    content_paths = [index_path]
    if not deleted:
        raw_writes.insert(
            0,
            {
                "kind": "object",
                "content_type": "attachment",
                "artifact_id": None,
                "content_base64": base64.b64encode(working_content).decode("ascii"),
            },
        )
        content_paths.insert(0, working_path)
    batch["writes"][4:4] = raw_writes
    return repository_id, batch, content_paths


def create_location(
    *,
    state_root: Path,
    candidate: Path,
    repository_id: str,
    run_id: str = RUN_ID,
) -> tuple[StoreLocation, Any]:
    location = StoreLocation.resolve(
        state_root=state_root,
        repository_id=repository_id,
        run_id=run_id,
        candidate_worktree=candidate,
        create_state_root=True,
    )
    return location, create_run_store(location)
