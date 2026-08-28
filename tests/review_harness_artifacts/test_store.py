"""追記、参照、根拠bytes、改変検出の回帰テストを行う。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factory import REPOSITORY_ID, create_store, request, write_evidence
from review_harness_artifacts.canonical import (
    canonicalize,
    parse_json_bytes,
    sha256_hex,
)
from review_harness_artifacts.errors import ArtifactError
from review_harness_artifacts.store import RunStore


class RunStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_root = self.root / "state"
        self.evidence_root = self.root / "evidence"
        self.evidence_root.mkdir()
        self.store = create_store(self.state_root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def append_input(self, record_id: str = "contract") -> None:
        content = write_evidence(
            self.evidence_root,
            f"{record_id}.md",
            b"# personal contract\n",
        )
        self.store.append(
            request(record_id, "input_snapshot"),
            {"content": content},
        )

    def test_append_and_validate_roundtrip(self) -> None:
        self.append_input()
        result = self.store.append(
            request("review-1", "review", references=["contract"]),
            {},
        )
        self.assertEqual(2, len(result.records))
        self.assertEqual([0, 1], [item.value["sequence"] for item in result.records])
        self.assertEqual(
            "contract", result.records[1].value["references"][0]["record_id"]
        )
        self.assertEqual(
            result.records[0].content_sha256,
            result.records[1].value["references"][0]["content_sha256"],
        )

    def test_binary_and_empty_evidence_are_preserved_exactly(self) -> None:
        stdout = write_evidence(self.evidence_root, "stdout.bin", b"\x00\xffoutput")
        stderr = write_evidence(self.evidence_root, "stderr.log", b"")
        result = self.store.append(
            request("verification-1", "verification"),
            {"stdout": stdout, "stderr": stderr},
        )
        evidence = {item["label"]: item for item in result.records[0].value["evidence"]}
        self.assertEqual(0, evidence["stderr"]["byte_length"])
        self.assertEqual(
            sha256_hex(b"\x00\xffoutput"), evidence["stdout"]["content_sha256"]
        )

    def test_input_snapshot_requires_exact_content(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "required_evidence_must_be_present"):
            self.store.append(request("contract", "input_snapshot"), {})

    def test_remediation_requires_patch(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "required_evidence_must_be_present"):
            self.store.append(request("fix-1", "remediation"), {})

    def test_verification_requires_stdout_and_stderr(self) -> None:
        stdout = write_evidence(self.evidence_root, "stdout.log", b"ok\n")
        with self.assertRaisesRegex(ArtifactError, "required_evidence_must_be_present"):
            self.store.append(
                request("verification-1", "verification"),
                {"stdout": stdout},
            )

    def test_future_or_missing_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError,
            "reference_must_point_to_prior_record_in_same_run",
        ):
            self.store.append(
                request("review-1", "review", references=["future-review"]),
                {},
            )

    def test_self_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "record_must_not_reference_itself"):
            self.store.append(
                request("review-1", "review", references=["review-1"]),
                {},
            )

    def test_reference_to_another_run_is_rejected(self) -> None:
        self.append_input("shared-name")
        other = create_store(self.state_root, run_id="other-run")
        with self.assertRaisesRegex(
            ArtifactError,
            "reference_must_point_to_prior_record_in_same_run",
        ):
            other.append(
                request("review-1", "review", references=["shared-name"]),
                {},
            )

    def test_record_id_cannot_be_reused(self) -> None:
        self.append_input()
        with self.assertRaisesRegex(ArtifactError, "record_id_must_not_be_reused"):
            self.store.append(request("contract", "review"), {})

    def test_tampered_record_is_rejected(self) -> None:
        self.append_input()
        record_path = self.store.validate().records[0].path
        record_path.write_bytes(b"{}")
        with self.assertRaises(ArtifactError):
            self.store.validate()

    def test_tampered_evidence_is_rejected(self) -> None:
        self.append_input()
        object_path = next(self.store.objects_root.iterdir())
        object_path.write_bytes(b"changed")
        with self.assertRaisesRegex(
            ArtifactError, "evidence_bytes_must_match_length_and_hash"
        ):
            self.store.validate()

    def test_missing_evidence_is_rejected(self) -> None:
        self.append_input()
        next(self.store.objects_root.iterdir()).unlink()
        with self.assertRaises(ArtifactError):
            self.store.validate()

    def test_unreferenced_evidence_is_rejected(self) -> None:
        self.append_input()
        orphan = b"orphan"
        (self.store.objects_root / sha256_hex(orphan)).write_bytes(orphan)
        with self.assertRaisesRegex(
            ArtifactError, "evidence_objects_must_match_references"
        ):
            self.store.validate()

    def test_gap_in_sequence_is_rejected(self) -> None:
        self.append_input()
        self.store.append(request("review-1", "review"), {})
        second = self.store.validate().records[1].path
        second.rename(second.with_name("000000000002" + second.name[12:]))
        with self.assertRaisesRegex(
            ArtifactError,
            "record_sequences_must_start_at_zero_without_gaps",
        ):
            self.store.validate()

    def test_wrong_reference_hash_is_rejected(self) -> None:
        self.append_input()
        self.store.append(request("review-1", "review", references=["contract"]), {})
        second = self.store.validate().records[1].path
        value = parse_json_bytes(second.read_bytes())
        value["references"][0]["content_sha256"] = "0" * 64
        changed = canonicalize(value)
        replacement = second.with_name(
            f"000000000001--review-1--{sha256_hex(changed)}.json"
        )
        second.unlink()
        replacement.write_bytes(changed)
        with self.assertRaisesRegex(ArtifactError, "reference_must_match_prior_record"):
            self.store.validate()

    def test_unknown_file_in_run_is_rejected(self) -> None:
        (self.store.run_root / "unexpected.txt").write_text(
            "unexpected", encoding="utf-8"
        )
        with self.assertRaisesRegex(
            ArtifactError,
            "run_root_must_contain_only_expected_directories",
        ):
            self.store.validate()

    def test_symlink_evidence_is_rejected(self) -> None:
        target = write_evidence(self.evidence_root, "target.md", b"content")
        link = self.evidence_root / "link.md"
        link.symlink_to(target)
        with self.assertRaisesRegex(ArtifactError, "input_must_be_regular_file"):
            self.store.append(
                request("contract", "input_snapshot"),
                {"content": link},
            )

    def test_symlink_state_root_is_rejected(self) -> None:
        real = self.root / "real-state"
        real.mkdir()
        link = self.root / "linked-state"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ArtifactError, "store_path_must_not_be_symlink"):
            RunStore(
                state_root=link,
                repository_id=REPOSITORY_ID,
                run_id="run-symlink",
                create=True,
            )

    def test_path_escape_identifier_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ArtifactError,
            "identifier_must_be_path_safe",
        ):
            RunStore(
                state_root=self.state_root,
                repository_id="../outside",
                run_id="run-invalid",
                create=True,
            )

    def test_run_store_inside_candidate_is_rejected(self) -> None:
        candidate = self.root / "candidate-inside"
        candidate.mkdir()
        with self.assertRaisesRegex(
            ArtifactError,
            "run_store_must_be_outside_candidate_worktree",
        ):
            RunStore(
                state_root=candidate,
                repository_id=REPOSITORY_ID,
                run_id="run-inside",
                create=True,
                candidate_worktree=candidate,
            )


if __name__ == "__main__":
    unittest.main()
