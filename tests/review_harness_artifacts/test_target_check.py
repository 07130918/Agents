"""target fingerprintの再確認と#49への追記を検証する。"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import review_harness_artifacts.target_check as target_check
from factory import REPOSITORY_ID, RUN_ID, request
from review_harness_artifacts.store import RunStore
from review_harness_artifacts.target_check import _CheckProblem, _Repository

PROJECT = (
    Path(__file__).resolve().parents[2]
    / "codex"
    / "skills"
    / "review-remediation-harness"
)


class TargetCheckCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.state_root = self.root / "state"
        self.skill_path = self.root / "personal-skill.md"
        self.skill_path.write_text("# personal skill\n", encoding="utf-8")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Target Check Test")
        self.git("config", "user.email", "target-check@example.com")
        (self.repository / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
        (self.repository / "app.txt").write_text("first\n", encoding="utf-8")
        self.git("add", "AGENTS.md", "app.txt")
        self.git("commit", "-m", "initial")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str) -> str:
        """隔離repositoryでGit commandを実行する。

        Args:
            arguments: Gitへ渡す引数。

        Returns:
            標準出力の文字列。
        """

        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def fingerprint(
        self,
        *,
        kind: str = "current_branch",
        base_sha: str | None = None,
        working_entries: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """現在のtest repositoryに一致するfingerprintを作る。

        Args:
            kind: target sourceの種別。
            base_sha: commit rangeのbase。省略時は現在HEAD。
            working_entries: 対象へ含めるdirty entry。

        Returns:
            Popr schema 1.0のtarget fingerprint。
        """

        head_sha = self.git("rev-parse", "HEAD")
        selected_base = base_sha or head_sha
        identifier = (
            "main" if kind == "current_branch" else f"{selected_base}...{head_sha}"
        )
        entries = working_entries or []
        return {
            "schema_version": "1.0",
            "target_source": {"kind": kind, "identifier": identifier},
            "git_object_format": self.git("rev-parse", "--show-object-format"),
            "base": {"ref": "main", "sha": selected_base},
            "head": {"sha": head_sha},
            "working_tree": {
                "status": "dirty" if entries else "clean",
                "mode": "included",
                "entries": entries,
            },
            "index_diff": {"included": False, "content_oid": None},
            "pr_remote": None,
            "scope": {"included_paths": ["."], "excluded_paths": []},
            "skill_versions": [
                {
                    "path": str(self.skill_path),
                    "content_oid": self.git(
                        "hash-object", "--no-filters", "--", str(self.skill_path)
                    ),
                }
            ],
            "project_rules": [
                {
                    "source": "base",
                    "source_sha": selected_base,
                    "path": "AGENTS.md",
                    "blob_oid": self.git("rev-parse", f"{selected_base}:AGENTS.md"),
                }
            ],
        }

    def append_target(self, fingerprint: dict[str, Any]) -> None:
        store = RunStore(
            state_root=self.state_root,
            repository_id=REPOSITORY_ID,
            run_id=RUN_ID,
            create=True,
            candidate_worktree=self.repository,
        )
        store.append(
            request(
                "target-0",
                "target",
                payload={"popr_target_fingerprint": fingerprint},
            ),
            {},
        )

    def run_check(
        self, record_id: str = "check-1"
    ) -> subprocess.CompletedProcess[bytes]:
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
                "check-target",
                "--state-root",
                str(self.state_root),
                "--repository-id",
                REPOSITORY_ID,
                "--run-id",
                RUN_ID,
                "--candidate-worktree",
                str(self.repository),
                "--target-record-id",
                "target-0",
                "--record-id",
                record_id,
            ],
            check=False,
            capture_output=True,
            env=environment,
        )

    def stored_check_payload(self) -> dict[str, Any]:
        store = RunStore(
            state_root=self.state_root,
            repository_id=REPOSITORY_ID,
            run_id=RUN_ID,
            create=False,
        )
        return store.validate().records[-1].value["payload"]

    def test_unchanged_returns_zero_and_appends_check(self) -> None:
        self.append_target(self.fingerprint())
        status_before = self.git("status", "--porcelain=v1")
        result = self.run_check()
        status_after = self.git("status", "--porcelain=v1")
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("unchanged", json.loads(result.stdout)["status"])
        self.assertEqual("unchanged", self.stored_check_payload()["status"])
        self.assertEqual(status_before, status_after)

    def test_commit_range_is_supported(self) -> None:
        base_sha = self.git("rev-parse", "HEAD")
        (self.repository / "second.txt").write_text("second\n", encoding="utf-8")
        self.git("add", "second.txt")
        self.git("commit", "-m", "second")
        self.append_target(self.fingerprint(kind="commit_range", base_sha=base_sha))
        result = self.run_check()
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("unchanged", self.stored_check_payload()["status"])

    def test_head_change_returns_three(self) -> None:
        self.append_target(self.fingerprint())
        (self.repository / "second.txt").write_text("second\n", encoding="utf-8")
        self.git("add", "second.txt")
        self.git("commit", "-m", "second")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("changed", payload["status"])
        self.assertIn("head", payload["changed_components"])

    def test_stage_split_does_not_change_final_working_tree(self) -> None:
        app = self.repository / "app.txt"
        app.write_text("changed\n", encoding="utf-8")
        self.git("add", "app.txt")
        entry = {
            "path": "app.txt",
            "status": "present",
            "mode": "100644",
            "type": "regular",
            "content_oid": self.git("hash-object", "--no-filters", "--", "app.txt"),
        }
        self.append_target(self.fingerprint(working_entries=[entry]))
        self.git("reset", "HEAD", "--", "app.txt")
        result = self.run_check()
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("unchanged", self.stored_check_payload()["status"])

    def test_staged_new_file_returns_changed(self) -> None:
        self.append_target(self.fingerprint())
        (self.repository / "added.txt").write_text("added\n", encoding="utf-8")
        self.git("add", "added.txt")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertIn("working_tree", payload["changed_components"])
        self.assertEqual(
            "added.txt",
            payload["observed_fingerprint"]["working_tree"]["entries"][0]["path"],
        )

    def test_new_file_stage_split_does_not_change_target(self) -> None:
        added = self.repository / "added.txt"
        added.write_text("added\n", encoding="utf-8")
        entry = {
            "path": "added.txt",
            "status": "present",
            "mode": "100644",
            "type": "regular",
            "content_oid": self.git("hash-object", "--no-filters", "--", "added.txt"),
        }
        self.append_target(self.fingerprint(working_entries=[entry]))
        self.git("add", "added.txt")
        staged = self.run_check()
        self.assertEqual(0, staged.returncode, staged.stderr.decode())
        self.git("reset", "HEAD", "--", "added.txt")
        unstaged = self.run_check(record_id="check-2")
        self.assertEqual(0, unstaged.returncode, unstaged.stderr.decode())

    def test_working_tree_change_returns_three(self) -> None:
        self.append_target(self.fingerprint())
        (self.repository / "app.txt").write_text("changed\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("changed", payload["status"])
        self.assertIn("working_tree", payload["changed_components"])

    def test_assume_unchanged_does_not_hide_content_change(self) -> None:
        self.append_target(self.fingerprint())
        self.git("update-index", "--assume-unchanged", "app.txt")
        (self.repository / "app.txt").write_text("changed\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        self.assertIn("working_tree", self.stored_check_payload()["changed_components"])

    def test_skip_worktree_returns_unresolved(self) -> None:
        self.append_target(self.fingerprint())
        self.git("update-index", "--skip-worktree", "app.txt")
        (self.repository / "app.txt").write_text("changed\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(2, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("unresolved", payload["status"])
        self.assertIn("skip-worktree", payload["reasons"][0]["detail"])

    def test_stat_cache_does_not_hide_same_size_content_change(self) -> None:
        self.git("config", "core.trustctime", "false")
        self.append_target(self.fingerprint())
        app = self.repository / "app.txt"
        original = app.stat()
        app.write_text("other\n", encoding="utf-8")
        os.utime(app, ns=(original.st_atime_ns, original.st_mtime_ns))
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        self.assertIn("working_tree", self.stored_check_payload()["changed_components"])

    def test_file_mode_change_is_detected_when_repository_ignores_it(self) -> None:
        self.git("config", "core.fileMode", "false")
        self.append_target(self.fingerprint())
        app = self.repository / "app.txt"
        app.chmod(app.stat().st_mode | stat.S_IXUSR)
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        entry = self.stored_check_payload()["observed_fingerprint"]["working_tree"][
            "entries"
        ][0]
        self.assertEqual("100755", entry["mode"])

    def test_owner_execute_bit_change_is_detected(self) -> None:
        app = self.repository / "app.txt"
        app.chmod(0o744)
        self.git("add", "app.txt")
        self.git("commit", "-m", "make executable")
        self.append_target(self.fingerprint())
        app.chmod(0o655)
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        observed = self.stored_check_payload()["observed_fingerprint"]["working_tree"][
            "entries"
        ][0]
        self.assertEqual("100644", observed["mode"])

    def test_filename_with_brackets_is_compared_as_literal_path(self) -> None:
        dynamic_route = self.repository / "src" / "[id]"
        dynamic_route.mkdir(parents=True)
        page = dynamic_route / "page.tsx"
        page.write_text("export default 1;\n", encoding="utf-8")
        self.git("add", "src/[id]/page.tsx")
        self.git("commit", "-m", "add dynamic route")
        self.append_target(self.fingerprint())
        page.write_text("export default 2;\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("changed", payload["status"])
        self.assertEqual(
            "src/[id]/page.tsx",
            payload["observed_fingerprint"]["working_tree"]["entries"][0]["path"],
        )

    def test_parent_directory_symlink_returns_unresolved(self) -> None:
        directory = self.repository / "dir"
        directory.mkdir()
        tracked = directory / "file.txt"
        tracked.write_text("same\n", encoding="utf-8")
        self.git("add", "dir/file.txt")
        self.git("commit", "-m", "add nested file")
        self.append_target(self.fingerprint())
        tracked.unlink()
        directory.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "file.txt").write_text("same\n", encoding="utf-8")
        directory.symlink_to(outside, target_is_directory=True)
        result = self.run_check()
        self.assertEqual(2, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("unresolved", payload["status"])
        self.assertIn("親directory", payload["reasons"][0]["detail"])

    def test_parent_directory_swap_during_check_returns_unresolved(self) -> None:
        directory = self.repository / "dir"
        directory.mkdir()
        tracked = directory / "file.txt"
        tracked.write_text("same\n", encoding="utf-8")
        self.git("add", "dir/file.txt")
        self.git("commit", "-m", "add nested file")
        fingerprint = self.fingerprint()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "file.txt").write_text("same\n", encoding="utf-8")
        moved = self.repository / "moved-dir"
        original_open = target_check._open_parent_directory
        swapped = False

        def swap_after_open(worktree: Path, path: str) -> tuple[int, str]:
            """親directory固定直後の差し替えを再現する。

            Args:
                worktree: 対象repository root。
                path: 確認するrepository相対path。

            Returns:
                差し替え前に固定した親directoryと最終path component。
            """

            nonlocal swapped
            descriptor, leaf = original_open(worktree, path)
            if path == "dir/file.txt" and not swapped:
                directory.rename(moved)
                directory.symlink_to(outside, target_is_directory=True)
                swapped = True
            return descriptor, leaf

        with mock.patch.object(
            target_check,
            "_open_parent_directory",
            side_effect=swap_after_open,
        ):
            result = target_check.compare_target_fingerprint(
                fingerprint,
                candidate_worktree=self.repository,
                target_record_id="target-0",
            )
        self.assertEqual("unresolved", result.status)
        self.assertIn("親directory", result.reasons[0]["detail"])

    def test_git_read_does_not_lazy_fetch_missing_blob(self) -> None:
        lazy = self.repository / "lazy.txt"
        lazy.write_text("lazy\n", encoding="utf-8")
        self.git("add", "lazy.txt")
        self.git("commit", "-m", "add lazy blob")
        self.git("config", "uploadpack.allowFilter", "true")
        blob_oid = self.git("rev-parse", "HEAD:lazy.txt")
        partial = self.root / "partial"
        clone = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--no-checkout",
                self.repository.as_uri(),
                str(partial),
            ],
            check=False,
            capture_output=True,
        )
        self.assertEqual(0, clone.returncode, clone.stderr.decode())
        environment = os.environ.copy()
        environment["GIT_NO_LAZY_FETCH"] = "1"

        def blob_is_missing() -> bool:
            result = subprocess.run(
                ["git", "cat-file", "-e", blob_oid],
                cwd=partial,
                env=environment,
                check=False,
                capture_output=True,
            )
            return result.returncode != 0

        self.assertTrue(blob_is_missing())
        with self.assertRaises(_CheckProblem):
            _Repository(partial).git("cat-file", "-t", blob_oid)
        self.assertTrue(blob_is_missing())

    def test_skill_change_returns_three(self) -> None:
        self.append_target(self.fingerprint())
        self.skill_path.write_text("# changed skill\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(3, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("changed", payload["status"])
        self.assertIn("skill_versions", payload["changed_components"])

    def test_project_rule_directory_returns_unresolved(self) -> None:
        rules = self.repository / "rules"
        rules.mkdir()
        (rules / "rule.md").write_text("# rule\n", encoding="utf-8")
        self.git("add", "rules/rule.md")
        self.git("commit", "-m", "add rules")
        fingerprint = self.fingerprint()
        head_sha = fingerprint["head"]["sha"]
        fingerprint["project_rules"] = [
            {
                "source": "base",
                "source_sha": head_sha,
                "path": "rules",
                "blob_oid": self.git("rev-parse", f"{head_sha}:rules"),
            }
        ]
        self.append_target(fingerprint)
        result = self.run_check()
        self.assertEqual(2, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("unresolved", payload["status"])
        self.assertEqual("project_rules.blob_oid", payload["reasons"][0]["component"])

    def test_unsupported_target_returns_two_and_appends_reason(self) -> None:
        fingerprint = self.fingerprint()
        fingerprint["target_source"] = {
            "kind": "pull_request",
            "identifier": "https://github.com/example/repository/pull/1",
        }
        self.append_target(fingerprint)
        result = self.run_check()
        self.assertEqual(2, result.returncode, result.stderr.decode())
        payload = self.stored_check_payload()
        self.assertEqual("unresolved", payload["status"])
        self.assertEqual("target_source", payload["reasons"][0]["component"])

    def test_invalid_fingerprint_returns_two(self) -> None:
        fingerprint = self.fingerprint()
        del fingerprint["head"]
        self.append_target(fingerprint)
        result = self.run_check()
        self.assertEqual(2, result.returncode, result.stderr.decode())
        self.assertEqual("unresolved", self.stored_check_payload()["status"])


if __name__ == "__main__":
    unittest.main()
