"""Integration tests for append, read-only validation, and crash recovery."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from factory import RUN_ID, create_location, valid_batch
from review_harness_artifacts import safe_fs
from review_harness_artifacts.canonical import (
    canonicalize,
    parse_json_bytes,
)
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.recovery import recover_run
from review_harness_artifacts.safe_fs import SafeDirectory
from review_harness_artifacts.validator import validate_ledger
from review_harness_artifacts.writer import append_batch


class SimulatedCrash(RuntimeError):
    pass


def tree_snapshot(root: Path) -> list[tuple[str, str, int]]:
    values: list[tuple[str, str, int]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            values.append(
                (relative, f"symlink:{path.readlink()}", path.lstat().st_mode)
            )
        elif path.is_file():
            values.append(
                (
                    relative,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    path.stat().st_mode,
                )
            )
        else:
            values.append((relative, "directory", path.stat().st_mode))
    return values


class ArtifactStoreIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_temporary = tempfile.TemporaryDirectory()
        self.candidate_temporary = tempfile.TemporaryDirectory()
        self.state_root = Path(self.state_temporary.name)
        self.candidate = Path(self.candidate_temporary.name)
        (self.candidate / "sentinel.txt").write_text("candidate\n", encoding="utf-8")
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

    def test_valid_chain_roundtrip_and_candidate_unchanged(self) -> None:
        candidate_before = tree_snapshot(self.candidate)
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        validated = validate_ledger(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
        )
        self.assertEqual(snapshot.head, validated.head)
        self.assertEqual(7, validated.max_sequence)
        self.assertEqual(7, len(validated.artifacts))
        self.assertEqual(candidate_before, tree_snapshot(self.candidate))

    def test_healthy_recovery_resyncs_commit_marker(self) -> None:
        append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        synced_paths: list[str] = []
        original_sync_file = SafeDirectory.sync_file

        def observe_sync(directory: SafeDirectory, relative_path: str) -> None:
            synced_paths.append(relative_path)
            original_sync_file(directory, relative_path)

        with mock.patch.object(SafeDirectory, "sync_file", new=observe_sync):
            result = recover_run(location=self.location, store=self.store)

        self.assertEqual("healthy", result.status)
        self.assertIn("HEAD.json", synced_paths)
        self.assertIn("transactions/transaction-0/committed.json", synced_paths)

    def test_validate_is_byte_for_byte_read_only(self) -> None:
        append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        before = tree_snapshot(self.location.run_root)
        validate_ledger(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
        )
        self.assertEqual(before, tree_snapshot(self.location.run_root))

    def test_validate_never_calls_filesystem_sync(self) -> None:
        append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        with mock.patch.object(
            safe_fs.os,
            "fsync",
            side_effect=AssertionError("validate must not call fsync"),
        ):
            validate_ledger(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
            )

    def test_validate_does_not_complete_active_transaction(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_descriptor":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        before = tree_snapshot(self.location.run_root)
        with self.assertRaisesRegex(
            ArtifactError, "active_transaction_requires_explicit_recovery"
        ):
            validate_ledger(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
            )
        self.assertEqual(before, tree_snapshot(self.location.run_root))
        self.assertFalse(
            (
                self.location.run_root / "transactions/transaction-0/committed.json"
            ).exists()
        )

    def test_recover_completes_each_post_descriptor_crash_point(self) -> None:
        checkpoints = [
            "after_descriptor",
            "after_installs",
            "after_head",
            "after_marker_pending",
        ]
        for checkpoint in checkpoints:
            with (
                self.subTest(checkpoint=checkpoint),
                tempfile.TemporaryDirectory() as state_name,
            ):
                location, store = create_location(
                    state_root=Path(state_name),
                    candidate=self.candidate,
                    repository_id=self.repository_id,
                )
                try:

                    def crash(observed: str, expected: str = checkpoint) -> None:
                        if observed == expected:
                            raise SimulatedCrash(observed)

                    with self.assertRaises(SimulatedCrash):
                        append_batch(
                            store,
                            repository_id=self.repository_id,
                            run_id=RUN_ID,
                            batch_value=self.batch,
                            crash_hook=crash,
                        )
                    result = recover_run(location=location, store=store)
                    self.assertEqual("recovered", result.status)
                    self.assertIsNotNone(result.snapshot)
                    self.assertTrue(
                        (
                            location.run_root
                            / "transactions/transaction-0/committed.json"
                        ).is_file()
                    )
                    validate_ledger(
                        store,
                        repository_id=self.repository_id,
                        run_id=RUN_ID,
                    )
                finally:
                    store.close()

    def test_crash_after_commit_marker_is_already_committed(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_marker":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )

        result = recover_run(location=self.location, store=self.store)

        self.assertEqual("healthy", result.status)
        self.assertEqual(0, result.snapshot.head["revision"])

    def test_pre_descriptor_crash_is_not_completed(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_staged":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        before = tree_snapshot(self.location.run_root)
        result = recover_run(
            location=self.location,
            store=self.store,
            report_id="pre-descriptor-test",
        )
        self.assertEqual("recovery_required", result.status)
        self.assertTrue(result.report_saved)
        self.assertEqual(
            "recovery_requires_published_transaction_descriptor",
            result.report["invariant"] if result.report else None,
        )
        self.assertEqual(
            "transaction_unrecoverable",
            result.report["violation_kind"] if result.report else None,
        )
        self.assertEqual(
            "start_new_run",
            result.report["required_human_action"] if result.report else None,
        )
        self.assertEqual(before, tree_snapshot(self.location.run_root))
        self.assertFalse((self.location.run_root / "manifests/0.json").exists())

    def test_validate_rejects_pre_descriptor_residue_without_mutation(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_staged":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        before = tree_snapshot(self.location.run_root)

        with self.assertRaisesRegex(
            ArtifactError, "transaction_directory_requires_published_descriptor"
        ):
            validate_ledger(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
            )

        self.assertEqual(before, tree_snapshot(self.location.run_root))

    def test_non_utf8_namespace_names_produce_canonical_recovery_reports(self) -> None:
        invalid_name = "entry-\udcff"
        original_list_names = SafeDirectory.list_names
        for namespace in ("transactions", "manifests"):
            with self.subTest(namespace=namespace):

                def list_names(
                    directory: SafeDirectory,
                    relative_path: str | None = None,
                    target: str = namespace,
                ) -> list[str]:
                    if directory is self.store and relative_path == target:
                        return [invalid_name]
                    return original_list_names(directory, relative_path)

                with mock.patch.object(
                    SafeDirectory,
                    "list_names",
                    new=list_names,
                ):
                    result = recover_run(
                        location=self.location,
                        store=self.store,
                        report_id=f"non-utf8-{namespace}-test",
                    )

                self.assertEqual("recovery_required", result.status)
                self.assertIsNotNone(result.report)
                report_bytes = canonicalize(result.report)
                self.assertIn(b"filesystem-bytes-hex:ff", report_bytes)
                if result.report_saved:
                    self.assertEqual(
                        report_bytes,
                        Path(result.report_path).read_bytes()
                        if result.report_path
                        else None,
                    )
                else:
                    self.assertIsNotNone(result.report_save_error)

    def test_multiple_active_transactions_create_external_report_only(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_descriptor":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        source = self.location.run_root / "transactions/transaction-0"
        duplicate = self.location.run_root / "transactions/transaction-copy"
        shutil.copytree(source, duplicate)
        head_before = (self.location.run_root / "HEAD.json").read_bytes()
        result = recover_run(
            location=self.location,
            store=self.store,
            report_id="multiple-active-test",
        )
        self.assertEqual("recovery_required", result.status)
        self.assertTrue(result.report_saved)
        self.assertIsNotNone(result.report_path)
        self.assertEqual(
            head_before, (self.location.run_root / "HEAD.json").read_bytes()
        )
        self.assertFalse((source / "committed.json").exists())
        self.assertFalse((duplicate / "committed.json").exists())

    def test_corrupt_staged_bytes_are_not_repaired(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_descriptor":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        staged = self.location.run_root / "transactions/transaction-0/staged/0"
        staged.write_bytes(b"corrupt")
        result = recover_run(
            location=self.location,
            store=self.store,
            report_id="corrupt-staged-test",
        )
        self.assertEqual("recovery_required", result.status)
        self.assertTrue(result.report_saved)
        self.assertEqual(-1, self.batch["expected_head"]["revision"])
        self.assertEqual(self.batch["expected_head"], self._read_head())
        self.assertFalse((self.location.run_root / "manifests/0.json").exists())

    def test_malformed_descriptor_creates_external_report(self) -> None:
        def crash(checkpoint: str) -> None:
            if checkpoint == "after_descriptor":
                raise SimulatedCrash(checkpoint)

        with self.assertRaises(SimulatedCrash):
            append_batch(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
                batch_value=self.batch,
                crash_hook=crash,
            )
        descriptor_path = (
            self.location.run_root / "transactions/transaction-0/descriptor.json"
        )
        descriptor = parse_json_bytes(descriptor_path.read_bytes())
        descriptor["writes"][0]["kind"] = []
        descriptor_path.write_bytes(canonicalize(descriptor))

        result = recover_run(
            location=self.location,
            store=self.store,
            report_id="malformed-descriptor-test",
        )

        self.assertEqual("recovery_required", result.status)
        self.assertTrue(result.report_saved)
        self.assertEqual("field_must_be_nonempty_string", result.report["invariant"])
        self.assertFalse(
            (
                self.location.run_root / "transactions/transaction-0/committed.json"
            ).exists()
        )

    def test_orphan_manifest_without_transaction_record_is_rejected(self) -> None:
        append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        shutil.rmtree(self.location.run_root / "transactions/transaction-0")

        with self.assertRaisesRegex(
            ArtifactError, "manifest_must_have_transaction_descriptor"
        ):
            validate_ledger(
                self.store,
                repository_id=self.repository_id,
                run_id=RUN_ID,
            )

    def test_extra_manifest_revision_and_head_mismatch_do_not_fallback(self) -> None:
        for case in ("extra-revision", "head-mismatch"):
            with (
                self.subTest(case=case),
                tempfile.TemporaryDirectory() as state_name,
            ):
                location, store = create_location(
                    state_root=Path(state_name),
                    candidate=self.candidate,
                    repository_id=self.repository_id,
                )
                try:
                    append_batch(
                        store,
                        repository_id=self.repository_id,
                        run_id=RUN_ID,
                        batch_value=self.batch,
                    )
                    if case == "extra-revision":
                        shutil.copyfile(
                            location.run_root / "manifests/0.json",
                            location.run_root / "manifests/1.json",
                        )
                    else:
                        (location.run_root / "HEAD.json").write_bytes(
                            canonicalize({"revision": -1, "manifest_ref": None})
                        )
                    with self.assertRaises(ArtifactError):
                        validate_ledger(
                            store,
                            repository_id=self.repository_id,
                            run_id=RUN_ID,
                        )
                finally:
                    store.close()

    def test_corrupt_committed_ledger_creates_external_report(self) -> None:
        snapshot = append_batch(
            self.store,
            repository_id=self.repository_id,
            run_id=RUN_ID,
            batch_value=self.batch,
        )
        identity_id = f"{RUN_ID}/CONTEXT_RESOLVING/0"
        identity_path = (
            self.location.run_root
            / snapshot.artifact_refs[identity_id]["artifact_path"]
        )
        identity_path.unlink()
        identity_path.write_bytes(b"corrupt")
        head_before = (self.location.run_root / "HEAD.json").read_bytes()

        result = recover_run(
            location=self.location,
            store=self.store,
            report_id="committed-corruption-test",
        )

        self.assertEqual("recovery_required", result.status)
        self.assertTrue(result.report_saved)
        self.assertEqual(
            head_before, (self.location.run_root / "HEAD.json").read_bytes()
        )

    def _read_head(self) -> dict[str, Any]:
        import json

        return json.loads((self.location.run_root / "HEAD.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
