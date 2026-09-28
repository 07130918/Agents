"""旧記録の読取互換性、破損検出、検出できない変更を確認する。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory import REPOSITORY_ID, RUN_ID, replace_record, write_record
from review_harness_artifacts.canonical import parse_json_bytes, sha256_hex
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.store import RunStore


class RunStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state_root = self.root / "state"
        self.first = write_record(
            self.state_root,
            "contract",
            "input_snapshot",
            evidence={"content": b"# old contract\n"},
        )

    def store(self, state_root: Path | None = None) -> RunStore:
        return RunStore(
            state_root=state_root or self.state_root,
            repository_id=REPOSITORY_ID,
            run_id=RUN_ID,
        )

    def test_old_records_validate_without_writes(self) -> None:
        write_record(
            self.state_root,
            "verification",
            "verification",
            references=[self.first],
            evidence={"stdout": b"\x00\xffok", "stderr": b""},
        )
        files = [path for path in self.state_root.rglob("*") if path.is_file()]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}
        result = self.store().validate()
        self.assertEqual(2, len(result.records))
        self.assertEqual(3, result.evidence_count)
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}
        self.assertEqual(before, after)

    def test_archive_root_is_readable_after_move(self) -> None:
        archive = self.root / "archives" / "review-harness" / "2026-09-28"
        archive.mkdir(parents=True)
        (self.state_root / "review-harness").rename(archive / "review-harness")
        self.assertEqual(1, len(self.store(archive).validate().records))

    def test_terminal_record_does_not_authorize_resume(self) -> None:
        write_record(
            self.state_root,
            "stopped",
            "decision",
            payload={"state": "BUDGET_EXHAUSTED"},
        )
        result = self.store().validate().as_dict(status="valid")
        message = " ".join(result["next_actions"])
        self.assertIn("参照専用", message)
        self.assertIn("再開許可", message)
        self.assertNotIn("引き続き使用", message)

    def test_payload_semantics_are_not_validated(self) -> None:
        write_record(
            self.state_root, "target", "target", payload={"git_object_format": []}
        )
        self.assertEqual(2, len(self.store().validate().records))

    def test_missing_run_is_not_created(self) -> None:
        missing = self.root / "missing"
        with self.assertRaises(ArtifactError):
            self.store(missing)
        self.assertFalse(missing.exists())

    def test_tampered_record_is_rejected(self) -> None:
        self.first.write_bytes(b"{}")
        with self.assertRaises(ArtifactError):
            self.store().validate()

    def test_changed_hash_without_filename_change_is_rejected(self) -> None:
        value = parse_json_bytes(self.first.read_bytes())
        value["payload"] = {"changed": True}
        from review_harness_artifacts.canonical import canonicalize

        self.first.write_bytes(canonicalize(value))
        with self.assertRaisesRegex(
            ArtifactError, "record_filename_must_match_content"
        ):
            self.store().validate()

    def test_tampered_evidence_is_rejected(self) -> None:
        next(self.store().objects_root.iterdir()).write_bytes(b"changed")
        with self.assertRaisesRegex(ArtifactError, "evidence_bytes_must_match"):
            self.store().validate()

    def test_missing_evidence_is_rejected(self) -> None:
        next(self.store().objects_root.iterdir()).unlink()
        with self.assertRaises(ArtifactError):
            self.store().validate()

    def test_unreferenced_evidence_is_rejected(self) -> None:
        orphan = b"orphan"
        (self.store().objects_root / sha256_hex(orphan)).write_bytes(orphan)
        with self.assertRaisesRegex(ArtifactError, "evidence_objects_must_match"):
            self.store().validate()

    def test_missing_required_evidence_label_is_rejected(self) -> None:
        write_record(
            self.state_root, "verification", "verification", evidence={"stdout": b"ok"}
        )
        with self.assertRaisesRegex(ArtifactError, "required_evidence_must_be_present"):
            self.store().validate()

    def test_gap_in_sequence_is_rejected(self) -> None:
        second = write_record(self.state_root, "review")
        second.rename(second.with_name("000000000002" + second.name[12:]))
        with self.assertRaisesRegex(ArtifactError, "record_sequences_must_start"):
            self.store().validate()

    def test_wrong_reference_hash_is_rejected(self) -> None:
        second = write_record(self.state_root, "review", references=[self.first])
        value = parse_json_bytes(second.read_bytes())
        value["references"][0]["content_sha256"] = "0" * 64
        replace_record(second, value)
        with self.assertRaisesRegex(ArtifactError, "reference_must_match_prior_record"):
            self.store().validate()

    def test_mixed_run_is_rejected(self) -> None:
        value = parse_json_bytes(self.first.read_bytes())
        value["run_id"] = "other-run"
        replace_record(self.first, value)
        with self.assertRaisesRegex(
            ArtifactError, "record_must_belong_to_selected_run"
        ):
            self.store().validate()

    def test_duplicate_record_id_is_rejected(self) -> None:
        write_record(self.state_root, "contract")
        with self.assertRaisesRegex(ArtifactError, "record_ids_must_be_unique"):
            self.store().validate()

    def test_unknown_file_is_rejected(self) -> None:
        (self.store().run_root / "unexpected.txt").write_text("unexpected")
        with self.assertRaisesRegex(ArtifactError, "run_root_must_contain_only"):
            self.store().validate()

    def test_symlink_record_is_rejected(self) -> None:
        target = self.root / "record-copy"
        self.first.rename(target)
        self.first.symlink_to(target)
        with self.assertRaisesRegex(
            ArtifactError, "store_entries_must_be_regular_files"
        ):
            self.store().validate()

    def test_symlink_state_root_is_rejected(self) -> None:
        link = self.root / "linked"
        link.symlink_to(self.state_root, target_is_directory=True)
        with self.assertRaisesRegex(ArtifactError, "store_path_must_be_real_directory"):
            self.store(link)

    def test_path_escape_identifier_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "identifier_must_be_path_safe"):
            RunStore(
                state_root=self.state_root, repository_id="../outside", run_id=RUN_ID
            )

    def test_consistent_tail_deletion_is_not_detected(self) -> None:
        tail = write_record(self.state_root, "stopped", "decision")
        self.assertEqual(2, len(self.store().validate().records))
        tail.unlink()
        self.assertEqual(1, len(self.store().validate().records))

    def test_consistent_content_rehash_is_not_detected(self) -> None:
        value = parse_json_bytes(self.first.read_bytes())
        value["payload"] = {"changed": True}
        replace_record(self.first, value)
        self.assertEqual(1, len(self.store().validate().records))


if __name__ == "__main__":
    unittest.main()
