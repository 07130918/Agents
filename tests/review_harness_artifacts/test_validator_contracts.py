"""Focused cross-artifact validator regressions."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from factory import artifact, common_ref, input_snapshot, valid_chain
from review_harness_artifacts.canonical import canonicalize, sha256_hex
from review_harness_artifacts.contract import lifecycle_map, validate_artifact_shape
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.validator import (
    SECURITY_CATEGORY_WEIGHTS,
    _transition_file_side_for_target,
    _validate_manifest_limits_and_counters,
    _validate_ready_blocking_findings,
    _validate_remediation_lineage,
    _validate_security_audit_adapter,
    _validate_stage_checkpoints,
    _validate_targets_and_inputs,
    _validate_typed_refs_and_state_evidence,
)


def _security_content() -> dict[str, Any]:
    raw_report = "complete security report\n"
    return {
        "audit_contract_revision": "version:1.0",
        "audit_status": "complete",
        "rounds_completed": 10,
        "category_results": [
            {
                "category_id": category_id,
                "weight_percent": weight,
                "score": 100,
            }
            for category_id, weight in SECURITY_CATEGORY_WEIGHTS
        ],
        "findings": [],
        "overall_score": 100,
        "raw_report": raw_report,
        "raw_report_sha256": sha256_hex(raw_report.encode("utf-8")),
    }


def _capability_sources() -> list[dict[str, str]]:
    content = "# sync-docs-code\n"
    return [
        {
            "canonical_realpath": "/Users/test/.agents/skills/sync-docs-code/SKILL.md",
            "content": content,
            "content_sha256": sha256_hex(content.encode("utf-8")),
        }
    ]


def _remediation_attempt_lineage(
    *, first_status: str, second_status: str
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    target = artifact(
        sequence=0,
        artifact_type="target",
        payload={"generation": 0},
    )
    target_ref = common_ref(target)
    review = artifact(
        sequence=1,
        artifact_type="review",
        target_ref=target_ref,
        payload={"blocking_finding_ids": ["finding-major"]},
    )
    review_ref = common_ref(review)
    request = artifact(
        sequence=2,
        artifact_type="change_request",
        target_ref=target_ref,
        payload={
            "requests": [
                {
                    "id": "finding-major",
                    "source_type": "review_finding",
                    "source_ref": review_ref,
                    "source_item_id": "finding-major",
                }
            ]
        },
    )
    request_ref = common_ref(request)
    first = artifact(
        sequence=3,
        artifact_type="remediation",
        target_ref=target_ref,
        received=[request_ref],
        payload={"request_id": "finding-major", "decision": "human_decision"},
    )
    second = artifact(
        sequence=4,
        artifact_type="remediation",
        target_ref=target_ref,
        received=[request_ref],
        payload={"request_id": "finding-major", "decision": "fix"},
    )
    remediation_refs = sorted(
        [common_ref(first), common_ref(second)],
        key=lambda ref: ref["artifact_id"],
    )
    final_review = artifact(
        sequence=5,
        artifact_type="final_review",
        target_ref=target_ref,
        payload={
            "remediation_status": "required",
            "remediation_refs": remediation_refs,
            "previous_review_ref": review_ref,
            "blocking_finding_ids": [],
            "reconciliation": {
                "previous_findings": [
                    {
                        "finding_id": "finding-major",
                        "status": "Fixed",
                        "evidence_refs": [target_ref],
                    }
                ],
                "current_findings": [],
            },
        },
    )

    def wrapper(value: dict[str, Any], status: str) -> dict[str, Any]:
        return {
            "ref": common_ref(value),
            "lifecycle_status": status,
            "invalidation_reason_ref": None,
        }

    fixing_manifest = {
        "artifact_id": "run-49-test/FIXING/6",
        "payload": {
            "state": "FIXING",
            "transition_cause_ref": request_ref,
            "current_target_ref": target_ref,
            "artifact_refs": [wrapper(request, "current")],
        },
    }
    latest_manifest = {
        "artifact_id": "run-49-test/READY/7",
        "payload": {
            "state": "READY",
            "transition_cause_ref": None,
            "current_target_ref": target_ref,
            "artifact_refs": [
                wrapper(request, "historical"),
                wrapper(first, first_status),
                wrapper(second, second_status),
                wrapper(review, "historical"),
                wrapper(final_review, "current"),
            ],
        },
    }
    values = [target, review, request, first, second, final_review]
    return [fixing_manifest, latest_manifest], {
        value["artifact_id"]: value for value in values
    }


class CrossArtifactValidatorTests(unittest.TestCase):
    def test_required_capability_requires_exact_loaded_sources(self) -> None:
        capability = input_snapshot(
            sequence=8,
            input_kind="required_capability",
            content={
                "capability_name": "sync-docs-code",
                "declared_version": "1.0",
            },
            source_revision="version:1.0",
            trust_source="personal_contract",
            source_identifier="skill:sync-docs-code",
        )

        with self.assertRaisesRegex(
            ArtifactError, "required_capability_sources_must_not_be_empty"
        ):
            validate_artifact_shape(capability)

    def test_context_resolution_requires_exact_command_contracts(self) -> None:
        _repository_id, objects, _manifest = valid_chain()
        resolution = next(
            value for value in objects if value["artifact_type"] == "decision"
        )
        resolution["payload"]["resolved_commands"].pop("commands")

        with self.assertRaisesRegex(
            ArtifactError, "resolved_commands_must_define_required_commands"
        ):
            validate_artifact_shape(resolution)

    def test_review_cannot_be_created_during_context_resolution(self) -> None:
        _repository_id, objects, manifest = valid_chain()
        review = artifact(
            sequence=8,
            artifact_type="review",
            input_refs=manifest["payload"]["input_refs"],
            target_ref=manifest["payload"]["current_target_ref"],
            payload={
                "popr_result": {},
                "generic_risk_result": {},
                "generic_coverage_status": "Complete",
                "project_results": [],
                "project_coverage_status": "not_required",
                "blocking_finding_ids": [],
                "required_gates": [],
                "coverage_status": "Complete",
            },
        )
        del objects

        with self.assertRaisesRegex(
            ArtifactError, "artifact_type_must_use_allowed_stage"
        ):
            validate_artifact_shape(review)

    def test_review_requires_preceding_review_pending_manifest(self) -> None:
        _repository_id, objects, manifest = valid_chain()
        review = artifact(
            sequence=8,
            artifact_type="review",
            stage="REVIEW_PENDING",
            input_refs=manifest["payload"]["input_refs"],
            target_ref=manifest["payload"]["current_target_ref"],
            payload={
                "popr_result": {},
                "generic_risk_result": {},
                "generic_coverage_status": "Complete",
                "project_results": [],
                "project_coverage_status": "not_required",
                "blocking_finding_ids": [],
                "required_gates": [],
                "coverage_status": "Complete",
            },
        )
        artifacts = {item["artifact_id"]: item for item in [*objects, review]}

        with self.assertRaisesRegex(
            ArtifactError, "stage_artifact_requires_preceding_matching_manifest"
        ):
            _validate_stage_checkpoints([manifest], artifacts)

    def test_manifest_requires_exact_nonempty_limits_and_counters(self) -> None:
        _repository_id, _objects, manifest = valid_chain()
        manifest["payload"]["limits"] = {}

        with self.assertRaisesRegex(
            ArtifactError, "manifest_limits_must_use_exact_schema"
        ):
            validate_artifact_shape(manifest)

    def test_manifest_limits_stay_fixed_and_counters_do_not_decrease(self) -> None:
        _repository_id, _objects, initial = valid_chain()
        next_manifest = copy.deepcopy(initial)
        next_manifest["artifact_id"] = "run-49-test/REVIEW_PENDING/8"
        next_manifest["payload"]["state"] = "REVIEW_PENDING"
        next_manifest["payload"]["previous_state"] = "CONTEXT_RESOLVING"

        changed_limits = copy.deepcopy(next_manifest)
        changed_limits["payload"]["limits"]["max_diff_lines"] += 1
        with self.assertRaisesRegex(
            ArtifactError, "manifest_limits_must_remain_fixed_for_run"
        ):
            _validate_manifest_limits_and_counters([initial, changed_limits], {})

        manifest_with_retry = copy.deepcopy(next_manifest)
        manifest_with_retry["payload"]["counters"][
            "transient_retries_by_execution_key"
        ] = {"verify/unit-tests": 1}
        manifest_after_retry = copy.deepcopy(manifest_with_retry)
        manifest_after_retry["artifact_id"] = "run-49-test/VERIFYING/9"
        manifest_after_retry["payload"]["state"] = "VERIFYING"
        manifest_after_retry["payload"]["previous_state"] = "REVIEW_PENDING"
        manifest_after_retry["payload"]["counters"][
            "transient_retries_by_execution_key"
        ] = {}
        with self.assertRaisesRegex(
            ArtifactError,
            "manifest_counter_maps_must_be_append_only_and_non_decreasing",
        ):
            _validate_manifest_limits_and_counters(
                [initial, manifest_with_retry, manifest_after_retry], {}
            )

    def test_manifest_after_deadline_must_stop_for_deadline(self) -> None:
        _repository_id, _objects, manifest = valid_chain()
        manifest["payload"]["limits"]["deadline_at"] = "2026-08-26T00:00:00Z"
        with self.assertRaisesRegex(
            ArtifactError, "manifest_after_deadline_must_stop_for_deadline"
        ):
            _validate_manifest_limits_and_counters([manifest], {})

    def test_fixing_entry_reserves_exactly_one_remediation_cycle(self) -> None:
        _repository_id, _objects, previous = valid_chain()
        previous["payload"]["state"] = "CHANGES_REQUESTED"
        request = artifact(
            sequence=8,
            artifact_type="change_request",
            stage="CHANGES_REQUESTED",
            target_ref=previous["payload"]["current_target_ref"],
            payload={
                "requests": [
                    {
                        "id": "finding-major",
                        "source_type": "review_finding",
                        "source_ref": previous["payload"]["last_completed_stage"],
                        "source_item_id": "finding-major",
                    }
                ]
            },
        )
        fixing = copy.deepcopy(previous)
        fixing["artifact_id"] = "run-49-test/FIXING/8"
        fixing["payload"]["state"] = "FIXING"
        fixing["payload"]["previous_state"] = "CHANGES_REQUESTED"
        fixing["payload"]["transition_cause_ref"] = common_ref(request)
        with self.assertRaisesRegex(
            ArtifactError, "remediation_cycle_must_be_reserved_on_fixing_entry_only"
        ):
            _validate_manifest_limits_and_counters(
                [previous, fixing], {request["artifact_id"]: request}
            )

        fixing["payload"]["counters"]["remediation_cycles_started"] = 1
        fixing["payload"]["counters"]["remediation_attempts_by_request_id"] = {
            "finding-major": 1
        }
        _validate_manifest_limits_and_counters(
            [previous, fixing], {request["artifact_id"]: request}
        )

    def test_request_attempt_reservation_matches_fixing_cause(self) -> None:
        _repository_id, _objects, previous = valid_chain()
        previous["payload"]["state"] = "CHANGES_REQUESTED"
        request = artifact(
            sequence=8,
            artifact_type="change_request",
            stage="CHANGES_REQUESTED",
            target_ref=previous["payload"]["current_target_ref"],
            payload={
                "requests": [
                    {
                        "id": "finding-major",
                        "source_type": "review_finding",
                        "source_ref": previous["payload"]["last_completed_stage"],
                        "source_item_id": "finding-major",
                    },
                    {
                        "id": "finding-minor",
                        "source_type": "review_finding",
                        "source_ref": previous["payload"]["last_completed_stage"],
                        "source_item_id": "finding-minor",
                    },
                ]
            },
        )
        fixing = copy.deepcopy(previous)
        fixing["artifact_id"] = "run-49-test/FIXING/9"
        fixing["payload"]["state"] = "FIXING"
        fixing["payload"]["previous_state"] = "CHANGES_REQUESTED"
        fixing["payload"]["transition_cause_ref"] = common_ref(request)
        fixing["payload"]["counters"]["remediation_cycles_started"] = 1
        with self.assertRaisesRegex(
            ArtifactError, "request_attempt_must_be_reserved_once_for_fixing_cause"
        ):
            _validate_manifest_limits_and_counters(
                [previous, fixing], {request["artifact_id"]: request}
            )

        fixing["payload"]["counters"]["remediation_attempts_by_request_id"] = {
            "different-finding": 1
        }
        artifacts = {request["artifact_id"]: request}
        with self.assertRaisesRegex(
            ArtifactError, "request_attempt_must_be_reserved_once_for_fixing_cause"
        ):
            _validate_manifest_limits_and_counters([previous, fixing], artifacts)

        fixing["payload"]["counters"]["remediation_attempts_by_request_id"] = {
            "finding-major": 1,
        }
        with self.assertRaisesRegex(
            ArtifactError, "request_attempt_must_be_reserved_once_for_fixing_cause"
        ):
            _validate_manifest_limits_and_counters([previous, fixing], artifacts)

        fixing["payload"]["counters"]["remediation_attempts_by_request_id"] = {
            "finding-major": 2,
            "finding-minor": 1,
        }
        with self.assertRaisesRegex(
            ArtifactError, "request_attempt_must_be_reserved_once_for_fixing_cause"
        ):
            _validate_manifest_limits_and_counters([previous, fixing], artifacts)

        fixing["payload"]["counters"]["remediation_attempts_by_request_id"] = {
            "finding-major": 1,
            "finding-minor": 1,
        }
        _validate_manifest_limits_and_counters([previous, fixing], artifacts)

    def test_manifest_counter_support_and_upper_bounds_are_exact(self) -> None:
        _repository_id, _objects, manifest = valid_chain()
        manifest["payload"]["counters"]["paid_external_calls"] = 3
        with self.assertRaisesRegex(
            ArtifactError, "manifest_counter_must_not_exceed_limit"
        ):
            validate_artifact_shape(manifest)

        _repository_id, _objects, manifest = valid_chain()
        manifest["payload"]["counters"]["tokens_used"] = 0
        with self.assertRaisesRegex(
            ArtifactError, "token_counter_and_budget_support_must_match"
        ):
            validate_artifact_shape(manifest)

        _repository_id, _objects, manifest = valid_chain()
        manifest["payload"]["counters"] = {}
        with self.assertRaisesRegex(
            ArtifactError, "manifest_counters_must_use_exact_schema"
        ):
            validate_artifact_shape(manifest)

    def test_budget_exhausted_binds_exact_limit_observation(self) -> None:
        _repository_id, objects, previous = valid_chain()
        previous["payload"]["limits"]["max_remediation_cycles"] = 0
        evidence = next(item for item in objects if item["artifact_type"] == "evidence")
        observation = artifact(
            sequence=8,
            artifact_type="decision",
            stage="BUDGET_EXHAUSTED",
            input_refs=previous["payload"]["input_refs"],
            target_ref=previous["payload"]["current_target_ref"],
            received=[common_ref(evidence)],
            payload={
                "decision_kind": "limit_observation",
                "blocked_state": "BUDGET_EXHAUSTED",
                "target_ref": previous["payload"]["current_target_ref"],
                "failure_classification": "remediation_cycle_exhausted",
                "observed_evidence_refs": [common_ref(evidence)],
                "required_human_action": "start_new_run",
                "resume_requirement": "new_run_with_prior_run_handoff",
                "resume_state": None,
                "limit_name": "max_remediation_cycles",
                "limit_value": 0,
                "limit_event": "next_attempt_rejected",
                "observed_value": 0,
                "counter_key": None,
                "counter_snapshot": copy.deepcopy(previous["payload"]["counters"]),
                "previous_manifest_revision": 0,
                "previous_manifest_sha256": common_ref(previous)["sha256"],
            },
        )
        validate_artifact_shape(observation)
        invalid_observation = copy.deepcopy(observation)
        invalid_observation["payload"]["counter_snapshot"][
            "remediation_cycles_started"
        ] = "0"
        with self.assertRaisesRegex(ArtifactError, "field_must_be_integer"):
            validate_artifact_shape(invalid_observation)

        current = copy.deepcopy(previous)
        current["artifact_id"] = "run-49-test/BUDGET_EXHAUSTED/9"
        current["payload"]["state"] = "BUDGET_EXHAUSTED"
        current["payload"]["previous_state"] = "CONTEXT_RESOLVING"
        current["payload"]["transition_cause_ref"] = common_ref(observation)
        artifacts = {observation["artifact_id"]: observation}
        _validate_manifest_limits_and_counters([previous, current], artifacts)

        observation["payload"]["observed_value"] = -1
        with self.assertRaisesRegex(
            ArtifactError,
            "limit_observation_value_must_match_counter",
        ):
            _validate_manifest_limits_and_counters([previous, current], artifacts)
        observation["payload"]["observed_value"] = 0

        observation["payload"]["previous_manifest_sha256"] = "f" * 64
        artifacts = {observation["artifact_id"]: observation}
        with self.assertRaisesRegex(
            ArtifactError,
            "limit_observation_must_bind_previous_manifest_counters",
        ):
            _validate_manifest_limits_and_counters([previous, current], artifacts)

    def test_required_capability_content_is_exact(self) -> None:
        capability = input_snapshot(
            sequence=8,
            input_kind="required_capability",
            content={
                "capability_name": "sync-docs-code",
                "declared_version": "1.0",
                "sources": _capability_sources(),
                "untrusted_alias": "docs",
            },
            source_revision="version:1.0",
            trust_source="personal_contract",
            source_identifier="skill:sync-docs-code",
        )
        with self.assertRaisesRegex(ArtifactError, "unknown_fields_must_be_rejected"):
            validate_artifact_shape(capability)

    def test_required_capability_source_identifier_matches_identity(self) -> None:
        capability = input_snapshot(
            sequence=8,
            input_kind="required_capability",
            content={
                "capability_name": "sync-docs-code",
                "declared_version": "1.0",
                "sources": _capability_sources(),
            },
            source_revision="version:1.0",
            trust_source="personal_contract",
            source_identifier="skill:different-gate",
        )
        with self.assertRaisesRegex(
            ArtifactError, "required_capability_source_identifier_must_match_identity"
        ):
            validate_artifact_shape(capability)

    def test_versionless_required_capability_uses_content_hash_revision(self) -> None:
        content = {
            "capability_name": "sync-docs-code",
            "declared_version": None,
            "sources": _capability_sources(),
        }
        content_hash = sha256_hex(canonicalize(content))
        capability = input_snapshot(
            sequence=8,
            input_kind="required_capability",
            content=content,
            source_revision=f"sha256:{content_hash}",
            trust_source="personal_contract",
            source_identifier="skill:sync-docs-code",
        )
        validate_artifact_shape(capability)

    def test_required_project_review_requires_lens_ids(self) -> None:
        _repository_id, objects, _manifest = valid_chain(
            project_review_status="required",
        )
        resolution = next(
            value for value in objects if value["artifact_type"] == "decision"
        )
        with self.assertRaisesRegex(
            ArtifactError, "required_project_review_requires_lens_ids"
        ):
            validate_artifact_shape(resolution)

    def test_historical_remediation_attempt_does_not_block_current_fix(self) -> None:
        manifests, artifacts = _remediation_attempt_lineage(
            first_status="historical",
            second_status="current",
        )
        _validate_remediation_lineage(manifests, artifacts)
        final_review = next(
            value
            for value in artifacts.values()
            if value["artifact_type"] == "final_review"
        )
        review = next(
            value for value in artifacts.values() if value["artifact_type"] == "review"
        )
        _validate_ready_blocking_findings(
            final_review=final_review,
            reviews=[review],
            manifests=manifests,
            artifacts=artifacts,
            latest_lifecycle=lifecycle_map(manifests[-1]),
        )

    def test_final_review_requires_one_current_remediation_attempt(self) -> None:
        manifests, artifacts = _remediation_attempt_lineage(
            first_status="historical",
            second_status="historical",
        )
        with self.assertRaisesRegex(
            ArtifactError,
            "final_review_requires_one_current_remediation_per_fixing_request",
        ):
            _validate_remediation_lineage(manifests, artifacts)

    def test_security_audit_adapter_requires_exact_complete_evidence(self) -> None:
        gate = {
            "artifact_id": "run-49-test/GATES_PENDING/10",
            "payload": {"execution_status": "succeeded"},
        }
        evidence = {"payload": {"completeness": "full", "content": _security_content()}}
        _validate_security_audit_adapter(gate, evidence)

        invalid_values = [
            (
                lambda value: value["payload"]["content"]["category_results"].pop(),
                "complete_security_audit_requires_ten_rounds_and_all_categories",
            ),
            (
                lambda value: value["payload"]["content"].update(
                    {"raw_report_sha256": "0" * 64}
                ),
                "security_raw_report_hash_must_match_utf8_bytes",
            ),
        ]
        for mutate, invariant in invalid_values:
            invalid_evidence = copy.deepcopy(evidence)
            mutate(invalid_evidence)
            with (
                self.subTest(invariant=invariant),
                self.assertRaisesRegex(ArtifactError, invariant),
            ):
                _validate_security_audit_adapter(gate, invalid_evidence)

    def test_unlisted_tracked_file_side_accepts_only_git_object_binding(self) -> None:
        _repository_id, objects, _manifest = valid_chain()
        target = objects[4]
        side = {
            "status": "present",
            "mode": "100644",
            "type": "regular",
            "content_oid": "c" * 40,
            "byte_length": 1,
            "content_sha256": "0" * 64,
            "content_source": {"kind": "git_object", "object_id": "c" * 40},
        }
        _transition_file_side_for_target(
            owner_id="run-49-test/TARGET_VERIFYING/10",
            field="payload.content.path_changes[0].before",
            side=side,
            path="tracked.py",
            target=target,
        )

        invalid_side = copy.deepcopy(side)
        invalid_side["content_source"] = {
            "kind": "target_attachment",
            "target_id": target["artifact_id"],
            "content_path": "objects/sha256/00/" + "0" * 62,
        }
        with self.assertRaisesRegex(
            ArtifactError, "unlisted_tracked_file_side_requires_git_object_source"
        ):
            _transition_file_side_for_target(
                owner_id="run-49-test/TARGET_VERIFYING/10",
                field="payload.content.path_changes[0].before",
                side=invalid_side,
                path="tracked.py",
                target=target,
            )

    def test_resolved_context_rejects_pending_external_input(self) -> None:
        _repository_id, objects, manifest = valid_chain()
        pending = input_snapshot(
            sequence=8,
            input_kind="external_record",
            content={
                "authority_status": "pending",
                "authority_basis": "human decision required",
            },
            source_revision="record:1",
            trust_source="external_observed",
        )
        input_refs = sorted(
            [*manifest["payload"]["input_refs"], common_ref(pending)],
            key=lambda ref: ref["artifact_id"],
        )
        decision = objects[6]
        decision["input_refs"] = copy.deepcopy(input_refs)
        manifest["input_refs"] = copy.deepcopy(input_refs)
        manifest["payload"]["input_refs"] = copy.deepcopy(input_refs)
        artifacts = {item["artifact_id"]: item for item in [*objects, pending]}

        with self.assertRaisesRegex(
            ArtifactError,
            "resolved_context_must_not_include_pending_external_authority",
        ):
            _validate_typed_refs_and_state_evidence([manifest], artifacts)

    def test_project_rule_source_sha_must_match_target_base(self) -> None:
        _repository_id, objects, manifest = valid_chain()
        project_rule = input_snapshot(
            sequence=8,
            input_kind="project_rule",
            content={"rule": "base policy"},
            source_revision="placeholder",
            trust_source="base",
        )
        project_rule["payload"]["source_sha"] = "d" * 40
        project_rule["payload"]["source_object_id"] = "e" * 40
        project_rule["payload"]["source_revision"] = None
        project_ref = common_ref(project_rule)
        input_refs = sorted(
            [*manifest["payload"]["input_refs"], project_ref],
            key=lambda ref: ref["artifact_id"],
        )
        objects[6]["input_refs"] = copy.deepcopy(input_refs)
        manifest["input_refs"] = copy.deepcopy(input_refs)
        manifest["payload"]["input_refs"] = copy.deepcopy(input_refs)
        manifest["payload"]["project_context_refs"].append(project_ref)
        manifest["payload"]["artifact_refs"].append(
            {
                "ref": project_ref,
                "lifecycle_status": "current",
                "invalidation_reason_ref": None,
            }
        )
        artifacts = {item["artifact_id"]: item for item in [*objects, project_rule]}

        with self.assertRaisesRegex(
            ArtifactError,
            "base_project_input_must_bind_target_base_and_object_format",
        ):
            _validate_targets_and_inputs([manifest], artifacts)

    def test_verification_request_binds_failed_command_and_output(self) -> None:
        _repository_id, objects, manifest = valid_chain()
        target_ref = manifest["payload"]["current_target_ref"]
        input_refs = manifest["payload"]["input_refs"]
        evidence_ref = common_ref(objects[5])
        verification = artifact(
            sequence=8,
            artifact_type="verification",
            stage="VERIFYING",
            input_refs=input_refs,
            target_ref=target_ref,
            received=[*input_refs, target_ref, evidence_ref],
            payload={
                "commands": [
                    {
                        "command_id": "unit-tests",
                        "argv": ["scripts/review-harness-artifacts.test.sh"],
                        "exit_code": 1,
                        "started_at": "2026-08-27T00:00:00Z",
                        "finished_at": "2026-08-27T00:00:01Z",
                        "stdout_ref": evidence_ref,
                        "stderr_ref": evidence_ref,
                        "environment_snapshot_ref": evidence_ref,
                    }
                ],
                "status": "failed",
                "unverified_reason": None,
                "mutated_target": False,
                "mutation_patch_ref": None,
            },
        )
        request = artifact(
            sequence=9,
            artifact_type="change_request",
            stage="CHANGES_REQUESTED",
            input_refs=input_refs,
            target_ref=target_ref,
            received=[common_ref(verification), evidence_ref, input_refs[1]],
            payload={
                "requests": [
                    {
                        "source_type": "verification_failure",
                        "id": "verification/unit-tests/assertion",
                        "source_ref": common_ref(verification),
                        "command_id": "unit-tests",
                        "expected_behavior_ref": input_refs[1],
                        "observed_failure": "assertion failed",
                        "output_ref": evidence_ref,
                    }
                ]
            },
        )
        artifacts = {
            item["artifact_id"]: item for item in [*objects, verification, request]
        }
        _validate_typed_refs_and_state_evidence([], artifacts)

        invalid_request = copy.deepcopy(request)
        invalid_request["payload"]["requests"][0]["command_id"] = "unknown-command"
        artifacts[invalid_request["artifact_id"]] = invalid_request

        with self.assertRaisesRegex(
            ArtifactError,
            "verification_request_must_bind_failed_command_expected_behavior_and_output",
        ):
            _validate_typed_refs_and_state_evidence([], artifacts)

        mixed_verification = copy.deepcopy(verification)
        passed_command = copy.deepcopy(mixed_verification["payload"]["commands"][0])
        passed_command["command_id"] = "lint"
        passed_command["argv"] = ["lint"]
        passed_command["exit_code"] = 0
        mixed_verification["payload"]["commands"].append(passed_command)
        passed_request = copy.deepcopy(request)
        passed_request["payload"]["requests"][0]["source_ref"] = common_ref(
            mixed_verification
        )
        passed_request["payload"]["requests"][0]["command_id"] = "lint"
        artifacts = {
            item["artifact_id"]: item
            for item in [*objects, mixed_verification, passed_request]
        }
        with self.assertRaisesRegex(
            ArtifactError,
            "verification_request_must_bind_failed_command_expected_behavior_and_output",
        ):
            _validate_typed_refs_and_state_evidence([], artifacts)


if __name__ == "__main__":
    unittest.main()
