"""利用者と同じuv経由で、読取検証と廃止経路の拒否を確認する。"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from factory import REPOSITORY_ID, RUN_ID, write_record

PROJECT = (
    Path(__file__).resolve().parents[2] / "codex/skills/review-remediation-harness"
)


def run_cli(*arguments: str) -> subprocess.CompletedProcess[bytes]:
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
    return json.loads(result.stdout if result.stdout else result.stderr)


class CliTests(unittest.TestCase):
    def test_validate_does_not_print_payload_or_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_record(
                root,
                "old",
                "input_snapshot",
                payload={"note": "private-payload-marker"},
                evidence={"content": b"private-evidence-marker"},
            )
            before = {
                path: path.read_bytes() for path in root.rglob("*") if path.is_file()
            }
            result = run_cli(
                "validate",
                "--state-root",
                str(root),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
            )
            after = {
                path: path.read_bytes() for path in root.rglob("*") if path.is_file()
            }
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("valid", output_value(result)["status"])
        self.assertEqual(before, after)
        self.assertNotIn(b"private-payload-marker", result.stdout)
        self.assertNotIn(b"private-evidence-marker", result.stdout)

    def test_retired_commands_do_not_create_or_change_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_record(root, "old")
            for command in ("append", "check-target"):
                for state in (root, root / "missing"):
                    with self.subTest(command=command, existing=state == root):
                        before = {
                            path: path.read_bytes()
                            for path in root.rglob("*")
                            if path.is_file()
                        }
                        result = run_cli(
                            command,
                            "--state-root",
                            str(state),
                            "--repository-id",
                            REPOSITORY_ID,
                            "--run-id",
                            RUN_ID,
                        )
                        self.assertEqual(2, result.returncode)
                        self.assertEqual(
                            "cli_arguments_must_be_valid",
                            output_value(result)["error"]["invariant"],
                        )
                        after = {
                            path: path.read_bytes()
                            for path in root.rglob("*")
                            if path.is_file()
                        }
                        self.assertEqual(before, after)
                        self.assertFalse((root / "missing").exists())

    def test_validation_errors_do_not_print_invalid_payload(self) -> None:
        invalid_payloads = (
            b'{"private-field-marker":123456789012345678901234567890}',
            b'{"private-field-marker":"private-value-marker","private-field-marker":0}',
        )
        for content in invalid_payloads:
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                path = write_record(root, "old")
                path.write_bytes(content)
                before = (path.read_bytes(), path.stat().st_mtime_ns)
                result = run_cli(
                    "validate",
                    "--state-root",
                    str(root),
                    "--repository-id",
                    REPOSITORY_ID,
                    "--run-id",
                    RUN_ID,
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual({"invariant"}, set(output_value(result)["error"]))
                for marker in (
                    b"private-field-marker",
                    b"private-value-marker",
                    b"123456789012345678901234567890",
                ):
                    self.assertNotIn(marker, result.stdout + result.stderr)
                self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_argument_error_does_not_echo_input(self) -> None:
        result = run_cli("private-argument-marker")
        self.assertEqual(2, result.returncode)
        self.assertEqual(
            "cli_arguments_must_be_valid", output_value(result)["error"]["invariant"]
        )
        self.assertNotIn(b"private-argument-marker", result.stdout + result.stderr)

    def test_state_root_must_be_explicit(self) -> None:
        result = run_cli(
            "validate", "--repository-id", REPOSITORY_ID, "--run-id", RUN_ID
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual(
            "cli_arguments_must_be_valid", output_value(result)["error"]["invariant"]
        )

    def test_missing_record_returns_error_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            result = run_cli(
                "validate",
                "--state-root",
                str(missing),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
            )
            self.assertFalse(missing.exists())
        self.assertEqual(2, result.returncode)
        self.assertEqual("error", output_value(result)["status"])

    def test_version(self) -> None:
        result = run_cli("--version")
        self.assertEqual(0, result.returncode)
        self.assertEqual(b"2.0.0\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
