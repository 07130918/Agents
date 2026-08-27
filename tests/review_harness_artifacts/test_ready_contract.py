"""READY and newly closed Harness-owned contract regressions."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any

from factory import RUN_ID, artifact, common_ref, create_location, valid_batch
from review_harness_artifacts.canonical import sha256_hex
from review_harness_artifacts.contract import validate_artifact_shape
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.writer import append_batch


def _set_producer(
    value: dict[str, Any], *, role: str, instance_id: str, context_id: str
) -> None:
    value["producer"]["role"] = role
    value["producer"]["instance_id"] = instance_id
    value["producer"]["context_id"] = context_id
    value["producer"]["fresh_context"] = True


def _target_check_payload(
    *,
    target_ref: dict[str, Any],
    input_refs: list[dict[str, Any]],
    permission_ref: dict[str, Any],
    contract_ref: dict[str, Any],
) -> dict[str, Any]:
    return {
        "expected_target_ref": target_ref,
        "observed_target_status": "resolved",
        "observed_target_ref": target_ref,
        "observed_target_absence_reason": None,
        "expected_input_refs": input_refs,
        "observed_input_refs": input_refs,
        "expected_permission_set_ref": permission_ref,
        "observed_permission_set_ref": permission_ref,
        "expected_contract_ref": contract_ref,
        "observed_contract_ref": contract_ref,
        "expected_project_rule_refs": [],
        "observed_project_rule_refs": [],
        "status": "unchanged",
        "transition_kinds": ["none"],
        "observed_components": [],
        "changed_components": [],
        "unresolved_components": [],
        "observation_evidence_refs": [],
        "transition_diff_ref": None,
        "checked_at": "2026-08-27T00:00:02Z",
    }


def _manifest_batch(
    expected_head: dict[str, Any], transaction_id: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    return {
        "batch_version": "1.0",
        "transaction_id": transaction_id,
        "expected_head": expected_head,
        "writes": [
            {
                "kind": "manifest",
                "content_type": "artifact_json",
                "artifact_id": manifest["artifact_id"],
                "content": manifest,
            }
        ],
    }


def _next_manifest(
    snapshot: Any,
    *,
    state: str,
    sequence: int,
    revision: int,
    cause_ref: dict[str, Any],
) -> dict[str, Any]:
    previous = snapshot.manifests[-1]
    manifest = copy.deepcopy(previous)
    manifest["artifact_id"] = f"{RUN_ID}/{state}/{sequence}"
    manifest["monotonic_sequence"] = sequence
    manifest["stage"] = state
    manifest["payload"]["revision"] = revision
    manifest["payload"]["previous_manifest_ref"] = common_ref(previous)
    manifest["payload"]["previous_state"] = previous["payload"]["state"]
    manifest["payload"]["state"] = state
    manifest["payload"]["transition_id"] = f"ready-transition-{revision}"
    manifest["payload"]["transition_cause_ref"] = cause_ref
    manifest["payload"]["last_completed_stage"] = cause_ref
    return manifest


def _ready_support_batch(
    snapshot: Any,
    *,
    verification_status: str = "passed",
    gate_name: str = "sync-docs-code",
    independence_status: str = "passed",
    stale_ready_check: bool = False,
    stale_gate_evidence: bool = False,
    project_coverage_status: str = "not_required",
    project_results: list[dict[str, Any]] | None = None,
    blind_project_coverage_status: str | None = None,
    blind_project_results: list[dict[str, Any]] | None = None,
    review_blocking_finding: bool = False,
    final_current_blocker: bool = False,
    omit_final_blocker_summary: bool = False,
    gate_content_sha256: str | None = None,
    gate_declared_version: str | None = None,
    gate_capability_revision: str | None = None,
    gate_decision_status: str = "PASS",
    verification_command_id: str = "unit-tests",
    verification_argv: list[str] | None = None,
    duplicate_verification_command: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prior_manifest = snapshot.manifests[-1]
    manifest_payload = prior_manifest["payload"]
    input_refs = copy.deepcopy(manifest_payload["input_refs"])
    target_ref = copy.deepcopy(manifest_payload["current_target_ref"])
    base_evidence = next(
        item
        for item in snapshot.artifacts.values()
        if item["artifact_type"] == "evidence"
    )
    evidence_ref = common_ref(base_evidence)
    capabilities = [
        item
        for item in snapshot.artifacts.values()
        if item["artifact_type"] == "input_snapshot"
        and item["payload"]["input_kind"] == "required_capability"
    ]
    if len(capabilities) != 1:
        raise AssertionError("READY fixture requires one required capability")
    capability = capabilities[0]
    capability_revision = capability["payload"]["source_revision"]
    declared_version = capability["payload"]["content"]["declared_version"]
    start_sequence = snapshot.max_sequence + 1
    issue_ref = copy.deepcopy(manifest_payload["issue_ref"])
    permission_ref = copy.deepcopy(manifest_payload["permission_set_ref"])
    contract_ref = copy.deepcopy(manifest_payload["contract_ref"])
    gate_requirement = {
        "gate_name": "sync-docs-code",
        "trigger_reason": "all candidate commits",
        "accepted_decision_statuses": ["PASS", "UPDATED"],
        "target_ref": target_ref,
    }

    review = artifact(
        sequence=start_sequence + 1,
        artifact_type="review",
        stage="REVIEW_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[*input_refs, target_ref],
        payload={
            "popr_result": {},
            "generic_risk_result": {},
            "generic_coverage_status": "Complete",
            "project_results": copy.deepcopy(project_results or []),
            "project_coverage_status": project_coverage_status,
            "blocking_finding_ids": (
                ["finding-major"] if review_blocking_finding else []
            ),
            "required_gates": [gate_requirement],
            "coverage_status": "Complete",
        },
    )
    _set_producer(
        review,
        role="initial_reviewer",
        instance_id="initial-1",
        context_id="initial-context",
    )
    checks: list[dict[str, Any]] = []
    for sequence in (start_sequence + 8, start_sequence + 10):
        check = artifact(
            sequence=sequence,
            artifact_type="target_check",
            stage="GATES_PENDING",
            input_refs=input_refs,
            target_ref=target_ref,
            received=[*input_refs, target_ref],
            payload=_target_check_payload(
                target_ref=target_ref,
                input_refs=input_refs,
                permission_ref=permission_ref,
                contract_ref=contract_ref,
            ),
        )
        checks.append(check)
    gate_evidence_text = "sync-docs-code result\n"
    gate_evidence = artifact(
        sequence=start_sequence + 9,
        artifact_type="evidence",
        stage="GATES_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[*input_refs, target_ref],
        payload={
            "evidence_kind": "gate_result",
            "media_type": "text/plain",
            "content_sha256": sha256_hex(gate_evidence_text.encode("utf-8")),
            "content": gate_evidence_text,
            "completeness": "full",
            "redactions": [],
            "truncation": None,
        },
    )
    gate_evidence_ref = (
        evidence_ref if stale_gate_evidence else common_ref(gate_evidence)
    )
    verification_command = {
        "command_id": verification_command_id,
        "argv": verification_argv or ["scripts/review-harness-artifacts.test.sh"],
        "exit_code": 0 if verification_status == "passed" else 1,
        "started_at": "2026-08-27T00:00:00Z",
        "finished_at": "2026-08-27T00:00:01Z",
        "stdout_ref": evidence_ref,
        "stderr_ref": evidence_ref,
        "environment_snapshot_ref": evidence_ref,
    }
    verification = artifact(
        sequence=start_sequence + 3,
        artifact_type="verification",
        stage="VERIFYING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[*input_refs, target_ref, evidence_ref],
        payload={
            "commands": [
                verification_command,
                *(
                    [copy.deepcopy(verification_command)]
                    if duplicate_verification_command
                    else []
                ),
            ],
            "status": verification_status,
            "unverified_reason": None,
            "mutated_target": False,
            "mutation_patch_ref": None,
        },
    )
    _set_producer(
        verification,
        role="tester",
        instance_id="tester-1",
        context_id="tester-context",
    )
    gate = artifact(
        sequence=start_sequence + 11,
        artifact_type="gate",
        stage="GATES_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[
            *input_refs,
            target_ref,
            gate_evidence_ref,
            *(common_ref(item) for item in checks),
        ],
        payload={
            "gate_name": gate_name,
            "declared_version": (
                declared_version
                if gate_declared_version is None
                else gate_declared_version
            ),
            "capability_revision": gate_capability_revision or capability_revision,
            "content_sha256": gate_content_sha256
            or capability["payload"]["content_sha256"],
            "execution_status": "succeeded",
            "decision_status": gate_decision_status,
            "decision_policy": "native_status",
            "acceptance_policy_ref": None,
            "evidence_ref": gate_evidence_ref,
            "pre_target_check_ref": common_ref(checks[0]),
            "post_target_check_ref": common_ref(checks[1]),
            "mutated_target": False,
        },
    )
    _set_producer(
        gate,
        role="docs_gate",
        instance_id="docs-1",
        context_id="docs-context",
    )
    blind_received = [issue_ref, target_ref]
    blind_review = artifact(
        sequence=start_sequence + 13,
        artifact_type="blind_review",
        stage="REREVIEW_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=blind_received,
        payload={
            "blind_result": {},
            "generic_risk_result": {},
            "generic_coverage_status": "Complete",
            "blind_received_artifacts": sorted(
                blind_received, key=lambda ref: ref["artifact_id"]
            ),
            "project_results": copy.deepcopy(
                project_results
                if blind_project_results is None
                else blind_project_results
            )
            if project_results is not None or blind_project_results is not None
            else [],
            "project_coverage_status": (
                project_coverage_status
                if blind_project_coverage_status is None
                else blind_project_coverage_status
            ),
            "required_gates": [gate_requirement],
            "independence_check": {
                "status": independence_status,
                "compared_instance_ids": ["initial-1"],
                "compared_context_ids": ["initial-context"],
                "conflicting_instance_ids": [],
                "conflicting_context_ids": [],
            },
        },
    )
    _set_producer(
        blind_review,
        role="final_reviewer",
        instance_id="final-1",
        context_id="final-context",
    )
    reconciliation_evidence_refs = (
        [common_ref(gate_evidence)]
        if review_blocking_finding or final_current_blocker
        else []
    )
    final_review = artifact(
        sequence=start_sequence + 14,
        artifact_type="final_review",
        stage="REREVIEW_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[
            common_ref(review),
            common_ref(blind_review),
            *reconciliation_evidence_refs,
        ],
        payload={
            "blind_review_ref": common_ref(blind_review),
            "reconciliation": {
                "previous_findings": (
                    [
                        {
                            "finding_id": "finding-major",
                            "status": "Fixed",
                            "evidence_refs": reconciliation_evidence_refs,
                        }
                    ]
                    if review_blocking_finding
                    else []
                ),
                "current_findings": (
                    [
                        {
                            "finding_id": "new-major",
                            "status": "New",
                            "blocking": True,
                            "evidence_refs": reconciliation_evidence_refs,
                        }
                    ]
                    if final_current_blocker
                    else []
                ),
            },
            "popr_result": {},
            "blocking_finding_ids": (
                []
                if omit_final_blocker_summary
                else ["new-major"]
                if final_current_blocker
                else []
            ),
            "previous_review_ref": common_ref(review),
            "remediation_status": "not_required",
            "remediation_refs": [],
            "independence_check": {
                "status": independence_status,
                "compared_instance_ids": ["initial-1"],
                "compared_context_ids": ["initial-context"],
                "conflicting_instance_ids": [],
                "conflicting_context_ids": [],
            },
        },
    )
    _set_producer(
        final_review,
        role="final_reviewer",
        instance_id="final-1",
        context_id="final-context",
    )
    ready_check = artifact(
        sequence=start_sequence + 15,
        artifact_type="target_check",
        stage="REREVIEW_PENDING",
        input_refs=input_refs,
        target_ref=target_ref,
        received=[*input_refs, target_ref],
        payload=_target_check_payload(
            target_ref=target_ref,
            input_refs=input_refs,
            permission_ref=permission_ref,
            contract_ref=contract_ref,
        ),
    )
    support = [
        review,
        checks[0],
        gate_evidence,
        checks[1],
        verification,
        gate,
        blind_review,
        final_review,
        ready_check,
    ]
    writes = [
        {
            "kind": "object",
            "content_type": "artifact_json",
            "artifact_id": item["artifact_id"],
            "content": item,
        }
        for item in support
    ]
    ready_cause = common_ref(review) if stale_ready_check else common_ref(ready_check)
    return (
        {
            "batch_version": "1.0",
            "transaction_id": "ready-support",
            "expected_head": snapshot.head,
            "writes": writes,
        },
        ready_cause,
    )


class ReadyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_temporary = tempfile.TemporaryDirectory()
        self.candidate_temporary = tempfile.TemporaryDirectory()
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True
        )
        _location, self.store = create_location(
            state_root=Path(self.state_temporary.name),
            candidate=Path(self.candidate_temporary.name),
            repository_id=self.repository_id,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.candidate_temporary.cleanup()
        self.state_temporary.cleanup()

    def _append_ready(
        self,
        *,
        historical_docs_precheck: bool = False,
        historical_verification_evidence: bool = False,
        historical_review: bool = False,
        **options: Any,
    ) -> Any:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.initial_batch,
        )
        support_batch, ready_cause = _ready_support_batch(snapshot, **options)
        support = [write["content"] for write in support_batch["writes"]]
        review = next(item for item in support if item["artifact_type"] == "review")
        verification = next(
            item for item in support if item["artifact_type"] == "verification"
        )
        gate = next(item for item in support if item["artifact_type"] == "gate")
        gate_support = [
            item
            for item in support
            if item["artifact_type"] in {"target_check", "evidence", "gate"}
            and item["stage"] == "GATES_PENDING"
        ]
        rereview_support = [
            item for item in support if item["stage"] == "REREVIEW_PENDING"
        ]
        start_sequence = snapshot.max_sequence + 1

        def append_stage(
            *,
            state: str,
            sequence: int,
            revision: int,
            cause_ref: dict[str, Any],
            objects: list[dict[str, Any]],
            transaction_id: str,
            historical_id: str | None = None,
        ) -> Any:
            nonlocal snapshot
            manifest = _next_manifest(
                snapshot,
                state=state,
                sequence=sequence,
                revision=revision,
                cause_ref=cause_ref,
            )
            manifest["payload"]["artifact_refs"].extend(
                {
                    "ref": common_ref(item),
                    "lifecycle_status": "current",
                    "invalidation_reason_ref": None,
                }
                for item in objects
            )
            manifest["payload"]["artifact_refs"].sort(
                key=lambda wrapper: wrapper["ref"]["artifact_id"]
            )
            if historical_id is not None:
                wrapper = next(
                    item
                    for item in manifest["payload"]["artifact_refs"]
                    if item["ref"]["artifact_id"] == historical_id
                )
                wrapper["lifecycle_status"] = "historical"
            writes = [
                {
                    "kind": "object",
                    "content_type": "artifact_json",
                    "artifact_id": item["artifact_id"],
                    "content": item,
                }
                for item in sorted(objects, key=lambda item: item["monotonic_sequence"])
            ]
            writes.append(
                {
                    "kind": "manifest",
                    "content_type": "artifact_json",
                    "artifact_id": manifest["artifact_id"],
                    "content": manifest,
                }
            )
            snapshot = append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value={
                    "batch_version": "1.0",
                    "transaction_id": transaction_id,
                    "expected_head": snapshot.head,
                    "writes": writes,
                },
            )
            return snapshot

        context_cause = snapshot.manifests[-1]["payload"]["context_resolution_ref"]
        append_stage(
            state="REVIEW_PENDING",
            sequence=start_sequence,
            revision=1,
            cause_ref=context_cause,
            objects=[],
            transaction_id="ready-review-checkpoint",
        )
        append_stage(
            state="VERIFYING",
            sequence=start_sequence + 2,
            revision=2,
            cause_ref=common_ref(review),
            objects=[review],
            transaction_id="ready-review",
        )
        append_stage(
            state="PRECOMMIT_DOCS_PENDING",
            sequence=start_sequence + 4,
            revision=3,
            cause_ref=common_ref(verification),
            objects=[verification],
            transaction_id="ready-verification",
        )
        for revision, (state, offset) in enumerate(
            (
                ("CANDIDATE_COMMIT_PENDING", 5),
                ("TARGET_VERIFYING", 6),
                ("GATES_PENDING", 7),
            ),
            start=4,
        ):
            append_stage(
                state=state,
                sequence=start_sequence + offset,
                revision=revision,
                cause_ref=common_ref(verification),
                objects=[],
                transaction_id=f"ready-{state.lower()}",
            )
        append_stage(
            state="REREVIEW_PENDING",
            sequence=start_sequence + 12,
            revision=7,
            cause_ref=common_ref(gate),
            objects=gate_support,
            transaction_id="ready-gates",
        )
        historical_id = None
        if historical_docs_precheck:
            historical_id = gate["payload"]["pre_target_check_ref"]["artifact_id"]
        elif historical_verification_evidence:
            historical_id = verification["payload"]["commands"][0]["stdout_ref"][
                "artifact_id"
            ]
        elif historical_review:
            historical_id = review["artifact_id"]
        append_stage(
            state="READY",
            sequence=start_sequence + 16,
            revision=8,
            cause_ref=ready_cause,
            objects=rereview_support,
            transaction_id="ready-final",
            historical_id=historical_id,
        )
        return snapshot

    def test_valid_ready_chain(self) -> None:
        snapshot = self._append_ready()
        self.assertEqual("READY", snapshot.manifests[-1]["payload"]["state"])

    def test_ready_rejects_incomplete_project_coverage(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_project_coverage_must_match_resolved_lenses"
        ):
            self._append_ready(project_coverage_status="Incomplete")

    def test_required_project_lens_accepts_complete_nonempty_results(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            project_review_status="required",
            required_lens_ids=["project-policy"],
        )
        snapshot = self._append_ready(
            project_coverage_status="Complete",
            project_results=[{"lens_id": "project-policy"}],
        )
        self.assertEqual("READY", snapshot.manifests[-1]["payload"]["state"])

    def test_required_project_lens_rejects_not_required_coverage(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            project_review_status="required",
            required_lens_ids=["project-policy"],
        )
        with self.assertRaisesRegex(
            ArtifactError, "ready_project_coverage_must_match_resolved_lenses"
        ):
            self._append_ready()

    def test_required_project_lens_rejects_different_result_id(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            project_review_status="required",
            required_lens_ids=["project-policy"],
        )
        with self.assertRaisesRegex(
            ArtifactError, "ready_project_lens_ids_must_match_resolved_lenses"
        ):
            self._append_ready(
                project_coverage_status="Complete",
                project_results=[{"lens_id": "different-policy"}],
            )

    def test_required_project_lens_rejects_duplicate_result_id(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            project_review_status="required",
            required_lens_ids=["project-policy"],
        )
        with self.assertRaisesRegex(
            ArtifactError, "project_result_lens_ids_must_be_unique"
        ):
            self._append_ready(
                project_coverage_status="Complete",
                project_results=[
                    {"lens_id": "project-policy"},
                    {"lens_id": "project-policy"},
                ],
            )

    def test_not_required_project_lens_rejects_project_results(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_project_coverage_must_match_resolved_lenses"
        ):
            self._append_ready(
                project_coverage_status="Complete",
                project_results=[{"lens_id": "unexpected"}],
            )

    def test_required_gate_accepts_only_success_statuses(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.initial_batch,
        )
        support_batch, _ready_cause = _ready_support_batch(snapshot)
        review = next(
            write["content"]
            for write in support_batch["writes"]
            if write["kind"] == "object"
            and write["content"]["artifact_type"] == "review"
        )
        review["payload"]["required_gates"][0]["accepted_decision_statuses"] = [
            "BLOCKED"
        ]

        with self.assertRaisesRegex(
            ArtifactError, "required_gate_accepted_status_must_be_success"
        ):
            validate_artifact_shape(review)

    def test_ready_rejects_blocking_finding_without_lineage(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError,
            "ready_blocking_finding_requires_change_request_remediation_and_evidence",
        ):
            self._append_ready(review_blocking_finding=True)

    def test_ready_rejects_final_current_blocker(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_requires_no_current_blocking_findings"
        ):
            self._append_ready(final_current_blocker=True)

    def test_final_blocker_summary_must_match_current_findings(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "final_blocking_findings_must_match_current_findings"
        ):
            self._append_ready(
                final_current_blocker=True,
                omit_final_blocker_summary=True,
            )

    def test_gate_capability_must_match_required_capability_input(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError,
            "gate_capability_must_match_one_required_capability_input",
        ):
            self._append_ready(gate_content_sha256="f" * 64)

    def test_gate_capability_name_must_match_required_capability_input(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            required_capability_name="different-gate",
        )
        with self.assertRaisesRegex(
            ArtifactError,
            "gate_capability_must_match_one_required_capability_input",
        ):
            self._append_ready()

    def test_required_capability_declared_version_must_match_revision(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            required_capability_declared_version="2.0",
            required_capability_source_revision="version:1.0",
        )
        with self.assertRaisesRegex(
            ArtifactError, "required_capability_revision_must_match_declared_identity"
        ):
            self._append_ready()

    def test_versionless_required_capability_can_satisfy_gate(self) -> None:
        self.repository_id, self.initial_batch = valid_batch(
            include_required_capability=True,
            required_capability_declared_version=None,
        )
        snapshot = self._append_ready()
        self.assertEqual("READY", snapshot.manifests[-1]["payload"]["state"])

    def test_gate_evidence_must_be_between_target_checks(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "gate_evidence_must_be_between_pre_and_post_checks"
        ):
            self._append_ready(stale_gate_evidence=True)

    def test_failed_verification_requires_observed_failure(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.initial_batch,
        )
        support_batch, _ready_cause = _ready_support_batch(snapshot)
        verification = next(
            write["content"]
            for write in support_batch["writes"]
            if write["kind"] == "object"
            and write["content"]["artifact_type"] == "verification"
        )
        verification["payload"]["commands"] = []
        verification["payload"]["status"] = "failed"

        with self.assertRaisesRegex(
            ArtifactError, "failed_verification_requires_observed_failure"
        ):
            validate_artifact_shape(verification)

    def test_failed_verification_requires_nonzero_exit(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.initial_batch,
        )
        support_batch, _ready_cause = _ready_support_batch(snapshot)
        verification = next(
            write["content"]
            for write in support_batch["writes"]
            if write["kind"] == "object"
            and write["content"]["artifact_type"] == "verification"
        )
        verification["payload"]["status"] = "failed"

        with self.assertRaisesRegex(
            ArtifactError, "failed_verification_requires_observed_failure"
        ):
            validate_artifact_shape(verification)

    def test_ready_rejects_failed_verification(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_requires_successful_current_verification"
        ):
            self._append_ready(verification_status="failed")

    def test_ready_rejects_unresolved_verification_command_id(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_required_commands_must_match_resolved_commands"
        ):
            self._append_ready(verification_command_id="different-tests")

    def test_ready_rejects_verification_argv_drift(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_required_commands_must_match_resolved_commands"
        ):
            self._append_ready(verification_argv=["true"])

    def test_ready_rejects_duplicate_required_command_execution(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_required_commands_must_execute_exactly_once"
        ):
            self._append_ready(duplicate_verification_command=True)

    def test_ready_rejects_missing_docs_gate(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_requires_one_successful_docs_gate"
        ):
            self._append_ready(gate_decision_status="BLOCKED")

    def test_ready_rejects_failed_independence(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_requires_complete_independent_final_review"
        ):
            self._append_ready(independence_status="failed")

    def test_ready_requires_post_stage_target_check(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_requires_fresh_post_stage_unchanged_target_check"
        ):
            self._append_ready(stale_ready_check=True)

    def test_ready_rejects_historical_verification_evidence(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_verification_evidence_must_be_current"
        ):
            self._append_ready(historical_verification_evidence=True)

    def test_mandatory_docs_gate_dependencies_must_be_current(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "ready_gate_dependencies_must_be_current_complete_evidence"
        ):
            self._append_ready(historical_docs_precheck=True)

    def test_ready_requires_current_review(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError,
            "ready_requires_validated_review_verification_gate_and_final_artifacts",
        ):
            self._append_ready(historical_review=True)

    def test_fixing_requires_change_request_cause(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.initial_batch,
        )
        cause = copy.deepcopy(
            snapshot.manifests[-1]["payload"]["context_resolution_ref"]
        )
        sequence = snapshot.max_sequence + 1
        for revision, state in enumerate(
            ("REVIEW_PENDING", "CHANGES_REQUESTED"), start=1
        ):
            manifest = _next_manifest(
                snapshot,
                state=state,
                sequence=sequence,
                revision=revision,
                cause_ref=cause,
            )
            snapshot = append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=_manifest_batch(
                    snapshot.head, f"fixing-setup-{revision}", manifest
                ),
            )
            sequence += 1
        invalid_fixing = _next_manifest(
            snapshot,
            state="FIXING",
            sequence=sequence,
            revision=3,
            cause_ref=cause,
        )
        invalid_fixing["payload"]["counters"]["remediation_cycles_started"] = 1
        with self.assertRaisesRegex(
            ArtifactError,
            "fixing_transition_requires_current_same_target_change_request",
        ):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=_manifest_batch(
                    snapshot.head, "invalid-fixing-cause", invalid_fixing
                ),
            )

    def test_exact_new_payload_unions(self) -> None:
        _repository_id, batch = valid_batch()
        target_ref = common_ref(batch["writes"][4]["content"])
        common = {
            "sequence": 8,
            "input_refs": [],
            "target_ref": target_ref,
        }
        invalid_values = [
            artifact(
                **common,
                artifact_type="blind_review",
                stage="REREVIEW_PENDING",
                payload={
                    "blind_result": {},
                    "generic_risk_result": {},
                    "generic_coverage_status": "Complete",
                    "blind_received_artifacts": [],
                    "project_results": [],
                    "project_coverage_status": "not_required",
                    "required_gates": [],
                    "independence_check": {},
                },
            ),
            artifact(
                **common,
                artifact_type="final_review",
                stage="REREVIEW_PENDING",
                payload={
                    "blind_review_ref": target_ref,
                    "reconciliation": {"previous_findings": [], "current_findings": []},
                    "popr_result": {},
                    "blocking_finding_ids": [],
                    "previous_review_ref": None,
                    "remediation_status": "not_required",
                    "remediation_refs": [],
                    "independence_check": {"status": "banana"},
                },
            ),
        ]
        for value in invalid_values:
            with (
                self.subTest(artifact_type=value["artifact_type"]),
                self.assertRaises(ArtifactError),
            ):
                validate_artifact_shape(value)


if __name__ == "__main__":
    unittest.main()
