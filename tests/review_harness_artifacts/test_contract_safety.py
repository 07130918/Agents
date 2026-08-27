"""Table-driven tests for strict JSON, schema, references, and path safety."""

from __future__ import annotations

import copy
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

from factory import (
    RUN_ID,
    artifact,
    common_ref,
    create_location,
    external_evidence_batch,
    input_snapshot,
    mutable_target_batch,
    valid_batch,
)
from review_harness_artifacts import safe_fs
from review_harness_artifacts.canonical import (
    MAX_IJSON_INTEGER,
    canonicalize,
    decode_base64,
    object_path,
    parse_json_bytes,
    require_canonical_json,
    sha256_hex,
)
from review_harness_artifacts.contract import (
    validate_artifact_shape,
    validate_run_relative_path,
)
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.recovery import save_recovery_report
from review_harness_artifacts.safe_fs import StoreLocation, create_run_store
from review_harness_artifacts.validator import validate_ledger
from review_harness_artifacts.writer import append_batch


class CanonicalJsonTests(unittest.TestCase):
    def test_jcs_serialization_is_exact(self) -> None:
        self.assertEqual(
            b'{"a":0,"b":1,"unicode":"\xe2\x82\xac"}',
            canonicalize({"unicode": "€", "b": 1.0, "a": -0.0}),
        )

    def test_noncanonical_stored_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "stored_json_must_be_exact_jcs"):
            require_canonical_json(b'{"b":1, "a":2}', field="artifact.json")

    def test_noncanonical_base64_padding_bits_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "content_base64_must_be_canonical_base64"
        ):
            decode_base64("ZE==", field="content_base64")

    def test_invalid_ijson_inputs_are_rejected(self) -> None:
        cases = [
            (b'{"a":1,"a":2}', "json_object_keys_must_be_unique"),
            (b"\xef\xbb\xbf{}", "json_must_not_have_bom"),
            (b'"\\ud800"', "json_string_must_not_contain_lone_surrogate"),
            (b"NaN", "json_number_must_be_finite"),
            (
                str(MAX_IJSON_INTEGER + 1).encode("ascii"),
                "json_integer_must_be_ijson_exact",
            ),
        ]
        for content, invariant in cases:
            with (
                self.subTest(content=content),
                self.assertRaisesRegex(ArtifactError, invariant),
            ):
                parse_json_bytes(content)

    def test_structured_error_preserves_surrogateescaped_bytes_as_hex(self) -> None:
        error = ArtifactError(
            artifact_id=None,
            field="transactions/entry-\udcff",
            invariant="invalid_filesystem_entry",
            detail="Unexpected filesystem entry: entry-\udcff",
        )

        encoded = canonicalize(error.as_dict())

        self.assertIn(b"filesystem-bytes-hex:ff", encoded)


class ContractAndPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_temporary = tempfile.TemporaryDirectory()
        self.candidate_temporary = tempfile.TemporaryDirectory()
        self.state_root = Path(self.state_temporary.name)
        self.candidate = Path(self.candidate_temporary.name)
        self.repository_id, self.batch = valid_batch()
        self.location, self.store = create_location(
            state_root=self.state_root,
            candidate=self.candidate,
            repository_id=self.repository_id,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.candidate_temporary.cleanup()
        self.state_temporary.cleanup()

    def assert_append_fails(
        self,
        mutate: Callable[[dict[str, Any]], None],
        invariant: str,
    ) -> None:
        batch = copy.deepcopy(self.batch)
        mutate(batch)
        with self.assertRaisesRegex(ArtifactError, invariant):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=batch,
            )

    def assert_capability_preflight_failure_is_clean(self, patcher: Any) -> None:
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            state_root = Path(state_name)
            candidate = Path(candidate_name)
            state_sentinel = state_root / "state-sentinel.txt"
            state_sentinel.write_text("state\n", encoding="utf-8")
            sentinel = candidate / "sentinel.txt"
            sentinel.write_text("candidate\n", encoding="utf-8")
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
            )

            with (
                patcher,
                self.assertRaisesRegex(ArtifactError, "capability_unavailable"),
            ):
                store = create_run_store(location)
                store.close()

            self.assertFalse(location.run_root.exists())
            self.assertEqual([state_sentinel], list(state_root.iterdir()))
            self.assertEqual("state\n", state_sentinel.read_text(encoding="utf-8"))
            self.assertEqual("candidate\n", sentinel.read_text(encoding="utf-8"))

    def test_pilot_path_only_ref_is_rejected(self) -> None:
        target = copy.deepcopy(self.batch["writes"][4]["content"])
        target["input_refs"] = [target["input_refs"][0]["artifact_path"]]
        with self.assertRaisesRegex(ArtifactError, "field_must_be_object"):
            validate_artifact_shape(target)

    def test_harness_owned_final_review_refs_require_common_ref_shape(self) -> None:
        target_ref = common_ref(self.batch["writes"][4]["content"])
        final_review = artifact(
            sequence=8,
            artifact_type="final_review",
            stage="REREVIEW_PENDING",
            target_ref=target_ref,
            payload={
                "blind_review_ref": "path-only",
                "reconciliation": {},
                "popr_result": {},
                "blocking_finding_ids": [],
                "previous_review_ref": None,
                "remediation_status": "not_required",
                "remediation_refs": [],
                "independence_check": {},
            },
        )
        with self.assertRaisesRegex(ArtifactError, "field_must_be_object"):
            validate_artifact_shape(final_review)

    def test_manifest_last_completed_stage_requires_common_ref_shape(self) -> None:
        manifest = copy.deepcopy(self.batch["writes"][-1]["content"])
        manifest["payload"]["last_completed_stage"] = "path-only"
        with self.assertRaisesRegex(ArtifactError, "field_must_be_object"):
            validate_artifact_shape(manifest)

    def test_run_store_path_grammar_rejects_unsafe_forms(self) -> None:
        cases = [
            "/absolute",
            "",
            "objects//entry",
            "objects/../entry",
            "objects/./entry",
            "objects/entry\x00suffix",
            "objects\\entry",
        ]
        for path in cases:
            with self.subTest(path=path), self.assertRaises(ArtifactError):
                validate_run_relative_path(
                    path,
                    artifact_id=None,
                    field="test.path",
                )

    def test_input_kind_rejects_unauthorized_trust_source(self) -> None:
        project_rule = input_snapshot(
            sequence=100,
            input_kind="project_rule",
            content={"rule": "test"},
            source_revision="placeholder",
            trust_source="base",
        )
        project_rule["payload"]["source_sha"] = "a" * 40
        project_rule["payload"]["source_object_id"] = "b" * 40
        project_rule["payload"]["source_revision"] = None
        human_input = input_snapshot(
            sequence=100,
            input_kind="human_approved_run_local",
            content={"approval": "test"},
            source_revision="approval:test",
            trust_source="human_approved_run_local",
        )
        governing_external_record = input_snapshot(
            sequence=100,
            input_kind="external_record",
            content={
                "authority_status": "governing",
                "authority_basis": "issue is authoritative",
            },
            source_revision="external:revision:1",
            trust_source="external_authoritative",
        )
        cases = [
            (
                "project_rule",
                project_rule,
                "external_observed",
                "input_kind_must_bind_to_authorized_trust_source",
            ),
            (
                "human_approved_run_local",
                human_input,
                "base",
                "input_kind_must_bind_to_authorized_trust_source",
            ),
            (
                "governing_external_record",
                governing_external_record,
                "external_observed",
                "external_authority_status_must_bind_to_trust_source",
            ),
        ]
        for name, snapshot, trust_source, invariant in cases:
            candidate = copy.deepcopy(snapshot)
            candidate["payload"]["trust_source"] = trust_source

            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ArtifactError, invariant),
            ):
                validate_artifact_shape(candidate)

    def test_project_rule_rejects_invalid_git_object_identifiers(self) -> None:
        project_rule = input_snapshot(
            sequence=100,
            input_kind="project_rule",
            content={"rule": "test"},
            source_revision="placeholder",
            trust_source="base",
        )
        project_rule["payload"]["source_sha"] = "a" * 40
        project_rule["payload"]["source_object_id"] = "b" * 64
        project_rule["payload"]["source_revision"] = None
        cases = [
            ("source_sha_wrong_length", "source_sha", "a" * 39),
            ("source_sha_uppercase", "source_sha", "A" * 40),
            ("source_object_id_wrong_length", "source_object_id", "b" * 65),
            ("source_object_id_uppercase", "source_object_id", "B" * 64),
        ]
        for name, field, invalid_value in cases:
            candidate = copy.deepcopy(project_rule)
            candidate["payload"][field] = invalid_value

            with (
                self.subTest(name=name),
                self.assertRaisesRegex(
                    ArtifactError,
                    "base_input_git_object_id_must_be_lowercase_hex",
                ),
            ):
                validate_artifact_shape(candidate)

    def test_sha256_revision_must_match_input_content_hash(self) -> None:
        content = {"contract_version": "2.0.0"}
        content_hash = sha256_hex(canonicalize(content))
        snapshot = input_snapshot(
            sequence=100,
            input_kind="personal_contract",
            content=content,
            source_revision=f"sha256:{content_hash}",
            trust_source="personal_contract",
        )
        candidate = copy.deepcopy(snapshot)
        mismatched_hash = "0" * 64 if content_hash != "0" * 64 else "1" * 64
        candidate["payload"]["source_revision"] = f"sha256:{mismatched_hash}"

        with self.assertRaisesRegex(
            ArtifactError,
            "sha256_revision_must_match_exact_input_content",
        ):
            validate_artifact_shape(candidate)

    def test_pilot_wrong_ref_hash_is_rejected(self) -> None:
        def mutate(batch: dict[str, Any]) -> None:
            manifest = batch["writes"][-1]["content"]
            wrong_ref = copy.deepcopy(manifest["payload"]["repository_identity_ref"])
            wrong_ref["sha256"] = "0" * 64
            manifest["payload"]["repository_identity_ref"] = wrong_ref

        self.assert_append_fails(mutate, "artifact_ref_must_match_exact_saved_ref")

    def test_repository_root_scope_sentinel_must_be_exact_singleton(self) -> None:
        target = copy.deepcopy(self.batch["writes"][4]["content"])
        target["payload"]["popr_target_fingerprint"]["scope"]["included_paths"] = [
            ".",
            "src",
        ]
        with self.assertRaisesRegex(
            ArtifactError, "repository_root_sentinel_must_be_exact_singleton"
        ):
            validate_artifact_shape(target)

    def test_manifest_role_refs_must_match_generation_input_kind(self) -> None:
        def mutate(batch: dict[str, Any]) -> None:
            manifest = batch["writes"][-1]["content"]
            decision = batch["writes"][6]["content"]
            manifest["payload"]["permission_set_ref"] = common_ref(decision)

        self.assert_append_fails(
            mutate, "resolved_manifest_must_bind_complete_context_resolution"
        )

    def test_pilot_verification_requires_exact_evidence_refs(self) -> None:
        fake_hash = "1" * 64
        target_ref = {
            "artifact_id": f"{RUN_ID}/CONTEXT_RESOLVING/4",
            "artifact_path": object_path(fake_hash),
            "sha256": fake_hash,
        }
        verification = artifact(
            sequence=8,
            artifact_type="verification",
            stage="VERIFYING",
            input_refs=[],
            target_ref=target_ref,
            payload={
                "commands": [
                    {
                        "command_id": "test",
                        "argv": ["test"],
                        "exit_code": 0,
                        "started_at": "2026-08-27T00:00:00Z",
                        "finished_at": "2026-08-27T00:00:01Z",
                    }
                ],
                "status": "passed",
                "unverified_reason": None,
                "mutated_target": False,
                "mutation_patch_ref": None,
            },
        )
        with self.assertRaisesRegex(ArtifactError, "required_fields_must_exist"):
            validate_artifact_shape(verification)

    def test_inline_evidence_hash_must_match_exact_bytes(self) -> None:
        evidence = copy.deepcopy(self.batch["writes"][5]["content"])
        evidence["payload"]["content"] = "changed\n"
        with self.assertRaisesRegex(
            ArtifactError, "inline_evidence_hash_must_match_content"
        ):
            validate_artifact_shape(evidence)

    def test_external_evidence_bytes_are_bound_to_path_and_hash(self) -> None:
        repository_id, batch, raw, content_path = external_evidence_batch()
        snapshot = append_batch(
            self.store,
            repository_id=repository_id,
            run_id=RUN_ID,
            batch_value=batch,
        )
        self.assertEqual(raw, (self.location.run_root / content_path).read_bytes())
        self.assertEqual(7, len(snapshot.artifacts))

    def test_external_evidence_hash_mismatch_is_rejected(self) -> None:
        repository_id, batch, _, content_path = external_evidence_batch()
        append_batch(
            self.store,
            repository_id=repository_id,
            run_id=RUN_ID,
            batch_value=batch,
        )
        content_file = self.location.run_root / content_path
        content_file.unlink()
        content_file.write_bytes(b"different")
        with self.assertRaisesRegex(
            ArtifactError, "committed_destination_must_match_descriptor"
        ):
            validate_ledger(
                self.store,
                repository_id=repository_id,
                run_id=RUN_ID,
            )

    def test_mutable_target_binary_empty_symlink_and_deleted_entries(self) -> None:
        cases = [
            {"working_content": b"\x00binary\xff", "working_type": "regular"},
            {"working_content": b"", "working_type": "regular"},
            {"working_content": b"../target", "working_type": "symlink"},
            {"deleted": True},
        ]
        for index, options in enumerate(cases):
            with (
                self.subTest(options=options),
                tempfile.TemporaryDirectory() as state_name,
            ):
                repository_id, batch, content_paths = mutable_target_batch(**options)
                batch["transaction_id"] = f"mutable-{index}"
                _location, store = create_location(
                    state_root=Path(state_name),
                    candidate=self.candidate,
                    repository_id=repository_id,
                )
                try:
                    snapshot = append_batch(
                        store,
                        repository_id=repository_id,
                        run_id=RUN_ID,
                        batch_value=batch,
                    )
                    self.assertEqual(7, len(snapshot.artifacts))
                    self.assertTrue(content_paths)
                finally:
                    store.close()

    def test_mutable_target_requires_one_to_one_snapshot_and_git_oid_binding(
        self,
    ) -> None:
        cases = [
            (
                {"include_snapshot": False},
                "included_mutable_entries_must_have_exact_snapshots",
            ),
            (
                {"working_oid_override": "d" * 40},
                "mutable_snapshot_bytes_hash_oid_and_fingerprint_must_match",
            ),
            (
                {"index_oid_override": "e" * 40},
                "index_diff_bytes_hash_oid_and_fingerprint_must_match",
            ),
        ]
        for index, (options, invariant) in enumerate(cases):
            with (
                self.subTest(options=options),
                tempfile.TemporaryDirectory() as state_name,
            ):
                repository_id, batch, _ = mutable_target_batch(**options)
                batch["transaction_id"] = f"invalid-mutable-{index}"
                _location, store = create_location(
                    state_root=Path(state_name),
                    candidate=self.candidate,
                    repository_id=repository_id,
                )
                try:
                    with self.assertRaisesRegex(ArtifactError, invariant):
                        append_batch(
                            store,
                            repository_id=repository_id,
                            run_id=RUN_ID,
                            batch_value=batch,
                        )
                finally:
                    store.close()

    def test_index_diff_capture_environment_and_argv_shape_are_exact(self) -> None:
        _, batch, _ = mutable_target_batch()
        target = next(
            write["content"]
            for write in batch["writes"]
            if write["content_type"] == "artifact_json"
            and write["content"]["artifact_type"] == "target"
        )
        cases = [
            ("capture_argv", [], "capture_argv_must_not_be_empty"),
            ("capture_environment", {"LC_ALL": 1}, "field_must_be_string"),
        ]
        for field, value, invariant in cases:
            with self.subTest(field=field):
                candidate = copy.deepcopy(target)
                candidate["payload"]["index_diff_snapshot"][field] = value
                with self.assertRaisesRegex(ArtifactError, invariant):
                    validate_artifact_shape(candidate)

    def test_sequence_revision_generation_and_state_invariants(self) -> None:
        mutations: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            (
                "sequence",
                lambda batch: batch["writes"].__setitem__(
                    slice(0, 2), [batch["writes"][1], batch["writes"][0]]
                ),
                "batch_artifact_sequences_must_continue_in_write_order",
            ),
            (
                "revision",
                self._set_invalid_initial_revision,
                "batch_manifest_revision_must_follow_head",
            ),
            (
                "generation",
                lambda batch: batch["writes"][-1]["content"]["payload"].__setitem__(
                    "current_target_generation", 1
                ),
                "manifest_generation_must_match_target",
            ),
            (
                "state",
                lambda batch: batch["writes"][-1]["content"]["payload"].__setitem__(
                    "state", "UNKNOWN"
                ),
                "initial_manifest_must_start_context_resolution",
            ),
        ]
        for name, mutate, invariant in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as state_name:
                _location, store = create_location(
                    state_root=Path(state_name),
                    candidate=self.candidate,
                    repository_id=self.repository_id,
                )
                try:
                    batch = copy.deepcopy(self.batch)
                    mutate(batch)
                    with self.assertRaisesRegex(ArtifactError, invariant):
                        append_batch(
                            store,
                            repository_id=self.repository_id,
                            run_id=RUN_ID,
                            batch_value=batch,
                        )
                finally:
                    store.close()

    def test_manifest_state_transition_is_enforced(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        manifest = self._next_manifest(
            snapshot=snapshot,
            state="FIXING",
            sequence=8,
            revision=1,
        )
        with self.assertRaisesRegex(
            ArtifactError, "manifest_state_transition_must_be_allowed"
        ):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self._manifest_batch(
                    snapshot.head, "transaction-1", manifest
                ),
            )

    def test_lifecycle_cannot_return_from_historical_to_current(self) -> None:
        snapshot0 = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        manifest1 = self._next_manifest(
            snapshot=snapshot0,
            state="REVIEW_PENDING",
            sequence=8,
            revision=1,
        )
        evidence_id = self.batch["writes"][5]["artifact_id"]
        for wrapper in manifest1["payload"]["artifact_refs"]:
            if wrapper["ref"]["artifact_id"] == evidence_id:
                wrapper["lifecycle_status"] = "historical"
        snapshot1 = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self._manifest_batch(
                snapshot0.head, "transaction-1", manifest1
            ),
        )
        manifest2 = self._next_manifest(
            snapshot=snapshot1,
            state="VERIFYING",
            sequence=9,
            revision=2,
        )
        for wrapper in manifest2["payload"]["artifact_refs"]:
            if wrapper["ref"]["artifact_id"] == evidence_id:
                wrapper["lifecycle_status"] = "current"
        with self.assertRaisesRegex(
            ArtifactError, "artifact_lifecycle_must_be_irreversible"
        ):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self._manifest_batch(
                    snapshot1.head, "transaction-2", manifest2
                ),
            )

    def test_new_lifecycle_entry_must_start_current(self) -> None:
        def mutate(batch: dict[str, Any]) -> None:
            manifest = batch["writes"][-1]["content"]
            manifest["payload"]["artifact_refs"][0]["lifecycle_status"] = "historical"

        self.assert_append_fails(mutate, "new_lifecycle_entry_must_start_current")

    @staticmethod
    def _next_manifest(
        *,
        snapshot: Any,
        state: str,
        sequence: int,
        revision: int,
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
        manifest["payload"]["transition_id"] = f"transition-{revision}"
        return manifest

    @staticmethod
    def _manifest_batch(
        expected_head: dict[str, Any],
        transaction_id: str,
        manifest: dict[str, Any],
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

    @staticmethod
    def _set_invalid_initial_revision(batch: dict[str, Any]) -> None:
        manifest = batch["writes"][-1]["content"]
        manifest["payload"]["revision"] = 1
        manifest["payload"]["previous_state"] = "CONTEXT_RESOLVING"
        manifest["payload"]["previous_manifest_ref"] = {
            "artifact_id": f"{RUN_ID}/CONTEXT_RESOLVING/0",
            "artifact_path": "manifests/0.json",
            "sha256": "2" * 64,
        }

    def test_batch_rejects_caller_owned_destination_and_hash(self) -> None:
        def mutate(batch: dict[str, Any]) -> None:
            batch["writes"][0]["destination_path"] = "objects/sha256/aa/forged"
            batch["writes"][0]["sha256"] = "0" * 64

        self.assert_append_fails(mutate, "unknown_fields_must_be_rejected")

    def test_unreferenced_raw_write_is_rejected(self) -> None:
        def mutate(batch: dict[str, Any]) -> None:
            batch["writes"].insert(
                0,
                {
                    "kind": "object",
                    "content_type": "attachment",
                    "artifact_id": None,
                    "content_base64": "dW51c2Vk",
                },
            )

        self.assert_append_fails(
            mutate, "raw_write_must_be_bound_by_matching_artifact_content_path"
        )

    def test_store_inside_candidate_is_rejected(self) -> None:
        state_root = self.candidate / "state"
        state_root.mkdir()
        with self.assertRaisesRegex(
            ArtifactError, "run_store_must_be_outside_candidate_worktree"
        ):
            StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=self.candidate,
            )

    def test_rejected_missing_state_root_does_not_modify_candidate(self) -> None:
        state_root = self.candidate / "missing-state"
        with self.assertRaisesRegex(
            ArtifactError, "run_store_must_be_outside_candidate_worktree"
        ):
            StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=self.candidate,
                create_state_root=True,
            )
        self.assertFalse(state_root.exists())

    def test_case_insensitive_candidate_alias_is_rejected_before_creation(self) -> None:
        candidate = self.state_root / "CandidateWorktree"
        candidate.mkdir()
        candidate_alias = self.state_root / "candidateworktree"
        if not candidate_alias.exists():
            self.skipTest("requires a case-insensitive filesystem")

        nested_state_root = candidate_alias / "state"
        with self.assertRaisesRegex(
            ArtifactError, "run_store_must_be_outside_candidate_worktree"
        ):
            StoreLocation.resolve(
                state_root=nested_state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
                create_state_root=True,
            )
        self.assertFalse((candidate / "state").exists())

    def test_new_state_root_creation_syncs_each_created_directory(self) -> None:
        with tempfile.TemporaryDirectory() as parent_name:
            state_root = Path(parent_name) / "first" / "second"
            original_fsync = safe_fs.os.fsync
            with mock.patch.object(safe_fs.os, "fsync", wraps=original_fsync) as fsync:
                StoreLocation.resolve(
                    state_root=state_root,
                    repository_id=self.repository_id,
                    run_id=RUN_ID,
                    candidate_worktree=self.candidate,
                    create_state_root=True,
                )
            self.assertGreaterEqual(fsync.call_count, 3)

    def test_candidate_rename_during_state_root_creation_is_rejected_before_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            candidate = root / "candidate"
            candidate.mkdir()
            sentinel = candidate / "sentinel.txt"
            sentinel.write_text("candidate\n", encoding="utf-8")
            state_root = root / "state" / "nested"
            original_create = safe_fs._create_absolute_directory_durably

            def move_candidate_then_create(
                path: Path,
                *,
                forbidden_identity: tuple[int, int] | None = None,
            ) -> None:
                candidate.rename(root / "state")
                original_create(path, forbidden_identity=forbidden_identity)

            with (
                mock.patch.object(
                    safe_fs,
                    "_create_absolute_directory_durably",
                    side_effect=move_candidate_then_create,
                ),
                self.assertRaisesRegex(
                    ArtifactError,
                    "state_root_creation_must_not_enter_candidate_worktree_identity",
                ),
            ):
                StoreLocation.resolve(
                    state_root=state_root,
                    repository_id=self.repository_id,
                    run_id=RUN_ID,
                    candidate_worktree=candidate,
                    create_state_root=True,
                )

            moved_candidate = root / "state"
            self.assertEqual(
                ["sentinel.txt"],
                sorted(item.name for item in moved_candidate.iterdir()),
            )
            self.assertEqual(
                "candidate\n",
                (moved_candidate / "sentinel.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((moved_candidate / "nested").exists())

    def test_run_store_creation_preflights_writer_lock(self) -> None:
        self.assert_capability_preflight_failure_is_clean(
            mock.patch.object(
                safe_fs.fcntl,
                "flock",
                side_effect=OSError("lock unsupported"),
            )
        )

    def test_run_store_creation_preflights_file_durable_sync(self) -> None:
        self.assert_capability_preflight_failure_is_clean(
            mock.patch.object(
                safe_fs,
                "durable_sync",
                side_effect=ArtifactError(
                    artifact_id=None,
                    field="filesystem",
                    invariant="filesystem_must_support_durable_sync",
                    detail="file sync unsupported",
                ),
            )
        )

    def test_run_store_creation_preflights_directory_durable_sync(self) -> None:
        self.assert_capability_preflight_failure_is_clean(
            mock.patch.object(
                safe_fs.os,
                "fsync",
                side_effect=OSError("directory sync unsupported"),
            )
        )

    def test_run_store_creation_preflights_hard_link_no_replace(self) -> None:
        self.assert_capability_preflight_failure_is_clean(
            mock.patch.object(
                safe_fs.os,
                "link",
                side_effect=OSError("hard links unsupported"),
            )
        )

    def test_run_store_creation_preflights_atomic_replace(self) -> None:
        self.assert_capability_preflight_failure_is_clean(
            mock.patch.object(
                safe_fs.os,
                "replace",
                side_effect=OSError("atomic replace unsupported"),
            )
        )

    def test_successful_capability_preflight_removes_probe_namespace(self) -> None:
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            state_root = Path(state_name)
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=Path(candidate_name),
            )
            with create_run_store(location):
                pass

            self.assertFalse(
                any(
                    entry.name.startswith("capability-probe-")
                    for entry in state_root.iterdir()
                )
            )
            self.assertFalse((location.run_root / "HEAD.json").exists())
            self.assertFalse((location.run_root / "transactions").exists())

    def test_recovery_report_store_overlap_with_candidate_is_rejected(self) -> None:
        candidate = (
            self.state_root
            / "recovery-reports"
            / self.repository_id
            / RUN_ID
            / "candidate"
        )
        candidate.mkdir(parents=True)
        with self.assertRaisesRegex(
            ArtifactError, "recovery_reports_must_be_outside_candidate_worktree"
        ):
            StoreLocation.resolve(
                state_root=self.state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
            )

    def test_replaced_state_root_is_rejected_before_store_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            state_root = root / "state"
            candidate = root / "candidate"
            replaced_state_root = root / "original-state"
            state_root.mkdir()
            candidate.mkdir()
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
            )
            state_root.rename(replaced_state_root)
            state_root.mkdir()

            with self.assertRaisesRegex(
                ArtifactError, "state_root_identity_must_match_resolution"
            ):
                create_run_store(location)

            self.assertEqual([], list(state_root.iterdir()))

    def test_candidate_renamed_to_future_run_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            state_root = root / "state"
            candidate = root / "candidate"
            state_root.mkdir()
            candidate.mkdir()
            (candidate / "sentinel.txt").write_text("candidate\n", encoding="utf-8")
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
            )
            location.run_root.parent.mkdir(parents=True)
            candidate.rename(location.run_root)

            with self.assertRaisesRegex(
                ArtifactError, "store_must_not_enter_candidate_worktree_identity"
            ):
                create_run_store(location)

            self.assertEqual(
                "candidate\n",
                (location.run_root / "sentinel.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((location.run_root / "transactions").exists())

    def test_candidate_renamed_to_recovery_report_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            state_root = root / "state"
            candidate = root / "candidate"
            state_root.mkdir()
            candidate.mkdir()
            (candidate / "sentinel.txt").write_text("candidate\n", encoding="utf-8")
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=candidate,
            )
            report_root = (
                state_root
                / "recovery-reports"
                / self.repository_id
                / RUN_ID
                / "report-test"
            )
            report_root.parent.mkdir(parents=True)
            candidate.rename(report_root)

            with self.assertRaisesRegex(
                ArtifactError, "store_must_not_enter_candidate_worktree_identity"
            ):
                save_recovery_report(
                    location=location,
                    report={"report_id": "report-test"},
                )

            self.assertEqual(
                "candidate\n",
                (report_root / "sentinel.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((report_root / "report.json").exists())

    def test_symlinked_store_object_is_rejected(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        identity_ref = snapshot.manifests[0]["payload"]["repository_identity_ref"]
        object_file = self.location.run_root / identity_ref["artifact_path"]
        target = self.state_root / "outside.json"
        target.write_text("{}", encoding="utf-8")
        object_file.unlink()
        object_file.symlink_to(target)
        with self.assertRaisesRegex(
            ArtifactError, "file_must_open_without_following_symlink"
        ):
            validate_ledger(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
            )

    def test_missing_intermediate_store_path_is_structured(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError, "path_components_must_be_real_directories"
        ):
            self.store.read_bytes("missing/component/object")

    def test_symlinked_directory_component_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as target_name,
        ):
            state_root = Path(state_name)
            (state_root / "review-harness").symlink_to(
                Path(target_name), target_is_directory=True
            )
            location = StoreLocation.resolve(
                state_root=state_root,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                candidate_worktree=self.candidate,
            )
            with self.assertRaisesRegex(
                ArtifactError, "directory_tree_must_be_openable_without_symlinks"
            ):
                store = create_run_store(location)
                store.close()

    def test_evidence_path_traversal_is_rejected(self) -> None:
        evidence = copy.deepcopy(self.batch["writes"][5]["content"])
        del evidence["payload"]["content"]
        evidence["payload"]["content_path"] = "../outside"
        with self.assertRaisesRegex(
            ArtifactError, "run_store_path_segments_must_match_grammar"
        ):
            validate_artifact_shape(evidence)


if __name__ == "__main__":
    unittest.main()
