"""4つの公開コマンドを別プロセスから実行して検証する。"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from factory import RUN_ID, create_location, valid_batch

PROJECT = (
    Path(__file__).resolve().parents[2]
    / "codex"
    / "skills"
    / "review-remediation-harness"
)


def run_cli(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    """利用者と同じく、uv経由で公開コマンドを実行する。

    Args:
        arguments: 公開コマンドへ渡す引数。

    Returns:
        終了コードと標準入出力を持つ実行結果。
    """

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--isolated",
            "--frozen",
            "--project",
            str(PROJECT),
            "review-harness-artifacts",
            *arguments,
        ],
        check=False,
        capture_output=True,
        env=environment,
    )


def decode_output(result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    stream = result.stdout if result.stdout else result.stderr
    return json.loads(stream)


class CliTests(unittest.TestCase):
    def test_canonicalize_returns_bytes_hash_and_derived_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            source = Path(temporary_name) / "value.json"
            source.write_bytes(b'{"b":1,"a":2}')
            result = run_cli("canonicalize", "--input", str(source))
        self.assertEqual(0, result.returncode, result.stderr.decode())
        value = decode_output(result)
        self.assertEqual("canonicalized", value["status"])
        self.assertEqual(13, value["byte_length"])
        self.assertTrue(value["destination_path"].startswith("objects/sha256/"))

    def test_append_validate_and_recover_healthy_run(self) -> None:
        repository_id, batch = valid_batch()
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            batch_path = Path(state_name) / "batch.json"
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            common = [
                "--state-root",
                state_name,
                "--repository-id",
                repository_id,
                "--run-id",
                RUN_ID,
            ]
            appended = run_cli(
                "append",
                *common,
                "--candidate-worktree",
                candidate_name,
                "--batch",
                str(batch_path),
            )
            validated = run_cli("validate", *common)
            recovered = run_cli(
                "recover",
                *common,
                "--candidate-worktree",
                candidate_name,
            )
        self.assertEqual(0, appended.returncode, appended.stderr.decode())
        self.assertEqual("appended", decode_output(appended)["status"])
        self.assertEqual(0, validated.returncode, validated.stderr.decode())
        self.assertEqual("valid", decode_output(validated)["status"])
        self.assertEqual(0, recovered.returncode, recovered.stderr.decode())
        self.assertEqual("healthy", decode_output(recovered)["status"])

    def test_cli_error_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            source = Path(temporary_name) / "duplicate.json"
            source.write_bytes(b'{"a":1,"a":2}')
            result = run_cli("canonicalize", "--input", str(source))
        self.assertEqual(2, result.returncode)
        value = decode_output(result)
        self.assertEqual("error", value["status"])
        self.assertEqual(
            {"artifact_id", "field", "invariant", "detail"},
            set(value["error"]),
        )

    def test_validate_reports_pre_descriptor_transaction_as_invalid(self) -> None:
        repository_id, _ = valid_batch()
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            _location, store = create_location(
                state_root=Path(state_name),
                candidate=Path(candidate_name),
                repository_id=repository_id,
            )
            try:
                store.ensure_directory("transactions/transaction-residue/staged")
                store.write_exclusive(
                    "transactions/transaction-residue/staged/0", b"residue"
                )
            finally:
                store.close()

            result = run_cli(
                "validate",
                "--state-root",
                state_name,
                "--repository-id",
                repository_id,
                "--run-id",
                RUN_ID,
                "--report-id",
                "validate-residue-test",
            )

        self.assertEqual(2, result.returncode, result.stderr.decode())
        value = decode_output(result)
        self.assertEqual("invalid", value["status"])
        self.assertEqual(
            "transaction_directory_requires_published_descriptor",
            value["report"]["invariant"],
        )
        self.assertEqual(
            "transaction_unrecoverable",
            value["report"]["violation_kind"],
        )
        self.assertEqual(
            "transaction-residue",
            value["report"]["transaction_id"],
        )

    def test_validate_prioritizes_unrecoverable_residue_over_active_ambiguity(
        self,
    ) -> None:
        repository_id, _ = valid_batch()
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            _location, store = create_location(
                state_root=Path(state_name),
                candidate=Path(candidate_name),
                repository_id=repository_id,
            )
            try:
                for transaction_id in ("active-a", "active-b"):
                    store.ensure_directory(f"transactions/{transaction_id}")
                    store.write_exclusive(
                        f"transactions/{transaction_id}/descriptor.json", b"{}"
                    )
                store.ensure_directory("transactions/descriptorless")
            finally:
                store.close()

            result = run_cli(
                "validate",
                "--state-root",
                state_name,
                "--repository-id",
                repository_id,
                "--run-id",
                RUN_ID,
                "--report-id",
                "mixed-residue-test",
            )

        self.assertEqual(2, result.returncode, result.stderr.decode())
        value = decode_output(result)
        self.assertEqual("invalid", value["status"])
        self.assertEqual(
            "transaction_unrecoverable",
            value["report"]["violation_kind"],
        )
        self.assertEqual("descriptorless", value["report"]["transaction_id"])

    def test_validate_emits_json_for_non_utf8_transaction_name(self) -> None:
        repository_id, _ = valid_batch()
        with (
            tempfile.TemporaryDirectory() as state_name,
            tempfile.TemporaryDirectory() as candidate_name,
        ):
            location, store = create_location(
                state_root=Path(state_name),
                candidate=Path(candidate_name),
                repository_id=repository_id,
            )
            store.ensure_directory("transactions")
            store.close()
            transactions = location.run_root / "transactions"
            descriptor = os.open(transactions, os.O_RDONLY)
            try:
                try:
                    os.mkdir(b"transaction-\xff", dir_fd=descriptor)
                except OSError as error:
                    self.skipTest(f"filesystem does not accept non-UTF8 names: {error}")
            finally:
                os.close(descriptor)

            result = run_cli(
                "validate",
                "--state-root",
                state_name,
                "--repository-id",
                repository_id,
                "--run-id",
                RUN_ID,
                "--report-id",
                "non-utf8-cli-test",
            )

        self.assertEqual(2, result.returncode, result.stderr.decode())
        self.assertEqual("invalid", decode_output(result)["status"])
        self.assertIn(b"filesystem-bytes-hex:ff", result.stdout)


if __name__ == "__main__":
    unittest.main()
