"""利用者と同じuv経由でappendとvalidateを確認する。"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from factory import REPOSITORY_ID, RUN_ID, request

PROJECT = (
    Path(__file__).resolve().parents[2]
    / "codex"
    / "skills"
    / "review-remediation-harness"
)


def run_cli(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    """公開コマンドを隔離したuv環境で実行する。

    Args:
        arguments: 公開コマンドへ渡す引数。

    Returns:
        終了code、標準出力、標準エラー出力。
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


def output_value(result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    stream = result.stdout if result.stdout else result.stderr
    return json.loads(stream)


class CliTests(unittest.TestCase):
    def test_append_then_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            record_path = root / "record.json"
            content_path = root / "contract.md"
            candidate = root / "candidate"
            candidate.mkdir()
            record_path.write_text(
                json.dumps(request("contract", "input_snapshot")),
                encoding="utf-8",
            )
            content_path.write_bytes(b"# contract\n")
            common = [
                "--state-root",
                str(root / "state"),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
            ]
            appended = run_cli(
                "append",
                *common,
                "--candidate-worktree",
                str(candidate),
                "--record",
                str(record_path),
                "--evidence",
                f"content={content_path}",
            )
            validated = run_cli("validate", *common)
        self.assertEqual(0, appended.returncode, appended.stderr.decode())
        self.assertEqual("appended", output_value(appended)["status"])
        self.assertEqual(0, validated.returncode, validated.stderr.decode())
        self.assertEqual("valid", output_value(validated)["status"])

    def test_error_contains_reason_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            record_path = root / "record.json"
            candidate = root / "candidate"
            candidate.mkdir()
            record_path.write_text(
                json.dumps(request("contract", "input_snapshot")),
                encoding="utf-8",
            )
            result = run_cli(
                "append",
                "--state-root",
                str(root / "state"),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
                "--candidate-worktree",
                str(candidate),
                "--record",
                str(record_path),
            )
        self.assertEqual(2, result.returncode)
        value = output_value(result)
        self.assertEqual("error", value["status"])
        self.assertTrue(value["next_actions"])
        self.assertEqual(
            "required_evidence_must_be_present",
            value["error"]["invariant"],
        )

    def test_duplicate_evidence_label_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            record_path = root / "record.json"
            content_path = root / "contract.md"
            candidate = root / "candidate"
            candidate.mkdir()
            record_path.write_text(
                json.dumps(request("contract", "input_snapshot")),
                encoding="utf-8",
            )
            content_path.write_bytes(b"# contract\n")
            result = run_cli(
                "append",
                "--state-root",
                str(root / "state"),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
                "--candidate-worktree",
                str(candidate),
                "--record",
                str(record_path),
                "--evidence",
                f"content={content_path}",
                "--evidence",
                f"content={content_path}",
            )
        self.assertEqual(2, result.returncode)
        self.assertEqual(
            "evidence_labels_must_be_unique",
            output_value(result)["error"]["invariant"],
        )


if __name__ == "__main__":
    unittest.main()
