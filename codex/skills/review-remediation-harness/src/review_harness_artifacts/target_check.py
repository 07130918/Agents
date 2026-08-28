"""保存済みtarget fingerprintと現在のlocal repositoryを比較する。"""

from __future__ import annotations

import copy
import os
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Literal

from .contract import require_identifier
from .errors import fail
from .store import RunStore, ValidationResult

CheckStatus = Literal["unchanged", "changed", "unresolved"]
SUPPORTED_TARGET_KINDS = {"current_branch", "commit_range"}
FINGERPRINT_FIELDS = {
    "schema_version",
    "target_source",
    "git_object_format",
    "base",
    "head",
    "working_tree",
    "index_diff",
    "pr_remote",
    "scope",
    "skill_versions",
    "project_rules",
}


@dataclass(frozen=True, slots=True)
class TargetCheckResult:
    """target fingerprintを比較した結果を保持する。"""

    status: CheckStatus
    expected_target_record_id: str
    changed_components: tuple[str, ...]
    observed_fingerprint: dict[str, Any] | None
    reasons: tuple[dict[str, str], ...]

    def as_payload(self) -> dict[str, Any]:
        """`target_check` recordへ保存するpayloadを返す。

        Returns:
            比較状態、差分項目、観測値、停止理由を持つJSON値。
        """

        return {
            "check_version": "1.0",
            "status": self.status,
            "expected_target_record_id": self.expected_target_record_id,
            "changed_components": list(self.changed_components),
            "observed_fingerprint": self.observed_fingerprint,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class TargetCheckExecution:
    """target確認結果と追記後のrun検証結果を保持する。"""

    result: TargetCheckResult
    validation: ValidationResult


@dataclass(frozen=True, slots=True)
class _CheckProblem(Exception):
    component: str
    detail: str


class _Repository:
    """対象repositoryへ書き込まないGit操作をまとめる。"""

    def __init__(self, worktree: Path) -> None:
        try:
            self.worktree = worktree.expanduser().resolve(strict=True)
        except OSError as error:
            raise _CheckProblem("repository", str(error)) from error
        if not self.worktree.is_dir():
            raise _CheckProblem("repository", "対象worktreeがdirectoryではありません。")
        root = self.git("rev-parse", "--show-toplevel").decode().strip()
        try:
            resolved_root = Path(root).resolve(strict=True)
        except OSError as error:
            raise _CheckProblem("repository", str(error)) from error
        if resolved_root != self.worktree:
            raise _CheckProblem(
                "repository",
                "--candidate-worktreeにはrepository rootを指定してください。",
            )

    def git(
        self,
        *arguments: str,
        input_bytes: bytes | None = None,
        input_file: BinaryIO | None = None,
    ) -> bytes:
        """固定したread-only環境でGit commandを実行する。

        Args:
            arguments: `git`へ渡す引数。
            input_bytes: 標準入力へ渡すbytes。
            input_file: 標準入力へ渡す固定済みfile descriptor。

        Returns:
            Git commandの標準出力。

        Raises:
            _CheckProblem: Git情報を一意に取得できない場合。
        """

        if input_bytes is not None and input_file is not None:
            raise _CheckProblem(
                "git", "標準入力はbytesまたはfileの一方だけを使います。"
            )
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_ATTR_NOSYSTEM": "1",
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_PAGER": "cat",
                "LC_ALL": "C",
            }
        )
        try:
            completed = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.fileMode=true",
                    "-c",
                    "core.fsmonitor=false",
                    *arguments,
                ],
                cwd=self.worktree,
                env=environment,
                input=input_bytes,
                stdin=input_file,
                check=False,
                capture_output=True,
            )
        except OSError as error:
            raise _CheckProblem("git", str(error)) from error
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise _CheckProblem(
                "git",
                detail or f"Git commandが終了code {completed.returncode}を返しました。",
            )
        return completed.stdout


def check_and_record_target(
    *,
    store: RunStore,
    target_record_id: str,
    check_record_id: str,
    candidate_worktree: Path,
) -> TargetCheckExecution:
    """保存済みtargetを現在値と比較し、結果を同じrunへ追記する。

    Args:
        store: 検証対象の#49 run store。
        target_record_id: 比較元となる`target` record ID。
        check_record_id: 新しく追記する`target_check` record ID。
        candidate_worktree: 読み取り専用で確認するrepository root。

    Returns:
        比較結果と追記後のrun検証結果。
    """

    require_identifier(target_record_id, field="target_record_id")
    require_identifier(check_record_id, field="record_id")
    current = store.validate()
    target = next(
        (
            item.value
            for item in current.records
            if item.value["record_id"] == target_record_id
        ),
        None,
    )
    if target is None:
        fail(
            record_id=target_record_id,
            field="target_record_id",
            invariant="target_record_must_exist",
            detail="指定したtarget recordが同じrunにありません。",
            next_action="validate済みのtarget record IDを指定してください。",
        )
    if target["record_type"] != "target":
        result = _unresolved(
            target_record_id,
            "target_record",
            "指定recordの種別がtargetではありません。",
        )
    else:
        expected = target["payload"].get("popr_target_fingerprint")
        result = compare_target_fingerprint(
            expected,
            candidate_worktree=candidate_worktree,
            target_record_id=target_record_id,
        )
    request = {
        "record_id": check_record_id,
        "record_type": "target_check",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "references": [target_record_id],
        "payload": result.as_payload(),
    }
    validation = store.append(request, {})
    return TargetCheckExecution(result=result, validation=validation)


def compare_target_fingerprint(
    expected_value: Any,
    *,
    candidate_worktree: Path,
    target_record_id: str,
) -> TargetCheckResult:
    """Poprのtarget fingerprintを現在のlocal repositoryと比較する。

    Args:
        expected_value: `target` recordへ保存したfingerprint。
        candidate_worktree: 現在値を取得するrepository root。
        target_record_id: 結果へ保存する比較元record ID。

    Returns:
        `unchanged`、`changed`、`unresolved`のいずれか。
    """

    try:
        expected = _validate_fingerprint(expected_value)
        repository = _Repository(candidate_worktree)
        observed = _observe_fingerprint(repository, expected)
    except _CheckProblem as error:
        return _unresolved(target_record_id, error.component, error.detail)

    changed = tuple(
        field
        for field in sorted(FINGERPRINT_FIELDS, key=lambda item: item.encode("utf-8"))
        if expected[field] != observed[field]
    )
    status: CheckStatus = "changed" if changed else "unchanged"
    return TargetCheckResult(
        status=status,
        expected_target_record_id=target_record_id,
        changed_components=changed,
        observed_fingerprint=observed,
        reasons=(),
    )


def _unresolved(
    target_record_id: str,
    component: str,
    detail: str,
) -> TargetCheckResult:
    return TargetCheckResult(
        status="unresolved",
        expected_target_record_id=target_record_id,
        changed_components=(),
        observed_fingerprint=None,
        reasons=({"component": component, "detail": detail},),
    )


def _validate_fingerprint(value: Any) -> dict[str, Any]:
    fingerprint = _object(value, FINGERPRINT_FIELDS, "fingerprint")
    if fingerprint["schema_version"] != "1.0":
        raise _CheckProblem("schema_version", "対応するfingerprint schemaは1.0です。")
    object_format = fingerprint["git_object_format"]
    if object_format not in {"sha1", "sha256"}:
        raise _CheckProblem("git_object_format", "Git object formatが不正です。")

    target_source = _object(
        fingerprint["target_source"], {"kind", "identifier"}, "target_source"
    )
    kind = target_source["kind"]
    if kind not in SUPPORTED_TARGET_KINDS:
        raise _CheckProblem(
            "target_source",
            f"初期版では未対応のtarget kindです: {kind}",
        )
    if not isinstance(target_source["identifier"], str):
        raise _CheckProblem(
            "target_source.identifier", "identifierは文字列が必要です。"
        )

    base = _object(fingerprint["base"], {"ref", "sha"}, "base")
    head = _object(fingerprint["head"], {"sha"}, "head")
    _oid(base["sha"], object_format, "base.sha")
    _oid(head["sha"], object_format, "head.sha")
    if base["ref"] is not None and not isinstance(base["ref"], str):
        raise _CheckProblem("base.ref", "base refは文字列またはnullが必要です。")
    expected_identifier = (
        target_source["identifier"]
        if kind == "current_branch"
        else f"{base['sha']}...{head['sha']}"
    )
    if kind == "commit_range" and target_source["identifier"] != expected_identifier:
        raise _CheckProblem(
            "target_source.identifier",
            "commit_range identifierがbase/head SHAと一致しません。",
        )

    working_tree = _object(
        fingerprint["working_tree"],
        {"status", "mode", "entries"},
        "working_tree",
    )
    if working_tree["status"] not in {"clean", "dirty"}:
        raise _CheckProblem("working_tree.status", "statusが不正です。")
    if working_tree["mode"] not in {"included", "excluded"}:
        raise _CheckProblem("working_tree.mode", "modeが不正です。")
    _validate_working_entries(
        working_tree["entries"],
        object_format,
        allow_entries=working_tree["mode"] == "included",
    )

    index_diff = _object(
        fingerprint["index_diff"], {"included", "content_oid"}, "index_diff"
    )
    if index_diff != {"included": False, "content_oid": None}:
        raise _CheckProblem(
            "index_diff",
            "初期版ではstaged-onlyまたはindex指定targetへ対応しません。",
        )
    if fingerprint["pr_remote"] is not None:
        raise _CheckProblem("pr_remote", "初期版ではPR targetへ対応しません。")

    _validate_scope(fingerprint["scope"])
    _validate_skill_versions(fingerprint["skill_versions"], object_format)
    _validate_project_rules(
        fingerprint["project_rules"], object_format, base["sha"], head["sha"]
    )
    return fingerprint


def _object(value: Any, fields: set[str], component: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _CheckProblem(component, "JSON objectが必要です。")
    if set(value) != fields:
        missing = sorted(fields - set(value))
        extra = sorted(set(value) - fields)
        raise _CheckProblem(
            component,
            f"required field不一致です。不足: {missing}; 未知: {extra}",
        )
    return value


def _oid(value: Any, object_format: str, component: str) -> str:
    length = 40 if object_format == "sha1" else 64
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _CheckProblem(component, f"{object_format}のGit OIDが必要です。")
    return value


def _repository_path(value: Any, component: str, *, allow_root: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise _CheckProblem(component, "repository相対pathが不正です。")
    if value == "." and allow_root:
        return value
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise _CheckProblem(component, "絶対path、空segment、.、..は使用できません。")
    return value


def _scope_path(value: Any, component: str, *, allow_root: bool = False) -> str:
    """初期版で扱えるliteralなscope pathを検証する。

    Args:
        value: 検証するJSON値。
        component: 問題発生時に報告するcomponent名。
        allow_root: repository rootを表す`.`を許可するか。

    Returns:
        検証済みのrepository相対path。
    """

    path = _repository_path(value, component, allow_root=allow_root)
    if path.startswith(":") or any(character in path for character in "*?["):
        raise _CheckProblem(component, "初期版のscopeはliteral pathだけを扱います。")
    return path


def _validate_scope(value: Any) -> None:
    scope = _object(value, {"included_paths", "excluded_paths"}, "scope")
    included = scope["included_paths"]
    excluded = scope["excluded_paths"]
    if not isinstance(included, list) or not included:
        raise _CheckProblem("scope.included_paths", "1件以上のpathが必要です。")
    included_paths = [
        _scope_path(item, "scope.included_paths", allow_root=True) for item in included
    ]
    if included_paths != _sorted_unique(included_paths):
        raise _CheckProblem("scope.included_paths", "pathはUTF-8順で重複不可です。")
    if not isinstance(excluded, list):
        raise _CheckProblem("scope.excluded_paths", "配列が必要です。")
    excluded_paths: list[str] = []
    for item in excluded:
        entry = _object(item, {"path", "reason"}, "scope.excluded_paths")
        excluded_paths.append(_scope_path(entry["path"], "scope.excluded_paths"))
        if not isinstance(entry["reason"], str) or not entry["reason"]:
            raise _CheckProblem("scope.excluded_paths.reason", "理由が必要です。")
    if excluded_paths != _sorted_unique(excluded_paths):
        raise _CheckProblem("scope.excluded_paths", "pathはUTF-8順で重複不可です。")


def _validate_working_entries(
    value: Any,
    object_format: str,
    *,
    allow_entries: bool,
) -> None:
    if not isinstance(value, list):
        raise _CheckProblem("working_tree.entries", "配列が必要です。")
    if not allow_entries and value:
        raise _CheckProblem("working_tree.entries", "excludedではentriesを空にします。")
    paths: list[str] = []
    for item in value:
        if not isinstance(item, dict) or item.get("status") not in {
            "present",
            "deleted",
        }:
            raise _CheckProblem("working_tree.entries", "entry statusが不正です。")
        if item["status"] == "present":
            entry = _object(
                item,
                {"path", "status", "mode", "type", "content_oid"},
                "working_tree.entries",
            )
            _entry_type_and_mode(entry["type"], entry["mode"], "working_tree.entries")
            _oid(
                entry["content_oid"], object_format, "working_tree.entries.content_oid"
            )
        else:
            entry = _object(
                item,
                {"path", "status", "head_mode", "head_type", "head_content_oid"},
                "working_tree.entries",
            )
            _entry_type_and_mode(
                entry["head_type"], entry["head_mode"], "working_tree.entries"
            )
            _oid(
                entry["head_content_oid"],
                object_format,
                "working_tree.entries.head_content_oid",
            )
        paths.append(_repository_path(entry["path"], "working_tree.entries.path"))
    if paths != _sorted_unique(paths):
        raise _CheckProblem("working_tree.entries", "pathはUTF-8順で重複不可です。")


def _entry_type_and_mode(value_type: Any, mode: Any, component: str) -> None:
    allowed = {"regular": {"100644", "100755"}, "symlink": {"120000"}}
    if value_type not in allowed or mode not in allowed[value_type]:
        raise _CheckProblem(component, "file typeとmodeの組み合わせが不正です。")


def _validate_skill_versions(value: Any, object_format: str) -> None:
    if not isinstance(value, list):
        raise _CheckProblem("skill_versions", "配列が必要です。")
    paths: list[str] = []
    for item in value:
        entry = _object(item, {"path", "content_oid"}, "skill_versions")
        path = entry["path"]
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise _CheckProblem("skill_versions.path", "absolute pathが必要です。")
        paths.append(path)
        _oid(entry["content_oid"], object_format, "skill_versions.content_oid")
    if paths != _sorted_unique(paths):
        raise _CheckProblem("skill_versions", "pathはUTF-8順で重複不可です。")


def _validate_project_rules(
    value: Any,
    object_format: str,
    base_sha: str,
    head_sha: str,
) -> None:
    if not isinstance(value, list):
        raise _CheckProblem("project_rules", "配列が必要です。")
    keys: list[str] = []
    for item in value:
        entry = _object(
            item,
            {"source", "source_sha", "path", "blob_oid"},
            "project_rules",
        )
        source = entry["source"]
        expected_sha = (
            base_sha if source == "base" else head_sha if source == "head" else None
        )
        if expected_sha is None or entry["source_sha"] != expected_sha:
            raise _CheckProblem(
                "project_rules.source_sha", "sourceとSHAが一致しません。"
            )
        path = _repository_path(entry["path"], "project_rules.path")
        keys.append(f"{source}\x00{path}")
        _oid(entry["blob_oid"], object_format, "project_rules.blob_oid")
    if keys != _sorted_unique(keys):
        raise _CheckProblem("project_rules", "source/pathはUTF-8順で重複不可です。")


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values), key=lambda item: item.encode("utf-8"))


def _observe_fingerprint(
    repository: _Repository,
    expected: dict[str, Any],
) -> dict[str, Any]:
    observed = copy.deepcopy(expected)
    object_format = repository.git("rev-parse", "--show-object-format").decode().strip()
    if object_format not in {"sha1", "sha256"}:
        raise _CheckProblem(
            "git_object_format", "現在のGit object formatを解決できません。"
        )
    observed["git_object_format"] = object_format

    for component in ("base", "head"):
        _require_commit(repository, expected[component]["sha"], component)
    current_head = repository.git("rev-parse", "HEAD").decode().strip()
    _oid(current_head, object_format, "head.sha")
    observed["head"]["sha"] = current_head

    kind = expected["target_source"]["kind"]
    if kind == "current_branch":
        branch = repository.git("symbolic-ref", "--short", "HEAD").decode().strip()
        observed["target_source"]["identifier"] = branch
    else:
        observed["target_source"]["identifier"] = (
            f"{expected['base']['sha']}...{current_head}"
        )

    observed["working_tree"] = _observe_working_tree(repository, expected)
    observed["skill_versions"] = _observe_skill_versions(
        repository, expected["skill_versions"]
    )
    observed["project_rules"] = _observe_project_rules(
        repository,
        expected["project_rules"],
        current_head=current_head,
    )
    return observed


def _require_commit(repository: _Repository, oid: str, component: str) -> None:
    try:
        repository.git("cat-file", "-e", f"{oid}^{{commit}}")
    except _CheckProblem as error:
        raise _CheckProblem(
            component, f"保存済みcommitを取得できません: {error.detail}"
        ) from error


def _observe_working_tree(
    repository: _Repository,
    expected: dict[str, Any],
) -> dict[str, Any]:
    scope = expected["scope"]
    pathspecs = [
        path if path == "." else f":(literal){path}" for path in scope["included_paths"]
    ]
    pathspecs.extend(
        f":(exclude,literal){entry['path']}" for entry in scope["excluded_paths"]
    )
    _reject_skip_worktree(repository, pathspecs)
    entries: list[dict[str, Any]] = []
    head_entries = _head_entries(repository, pathspecs)
    head_paths = {entry["path"] for entry in head_entries}
    for head_entry in head_entries:
        current_entry = _working_entry(
            repository,
            head_entry["path"],
            head_entry=head_entry,
        )
        if current_entry is None:
            raise _CheckProblem("working_tree", "HEAD追跡fileの状態を取得できません。")
        expected_present = {
            "path": head_entry["path"],
            "status": "present",
            "mode": head_entry["mode"],
            "type": head_entry["type"],
            "content_oid": head_entry["content_oid"],
        }
        if current_entry != expected_present:
            entries.append(current_entry)
    indexed = _nul_paths(
        repository.git("ls-files", "--cached", "-z", "--", *pathspecs),
        "working_tree",
    )
    untracked = _nul_paths(
        repository.git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *pathspecs,
        ),
        "working_tree",
    )
    for path in _sorted_unique(indexed + untracked):
        if path in head_paths:
            continue
        current_entry = _working_entry(repository, path)
        if current_entry is not None:
            entries.append(current_entry)
    entries.sort(key=lambda entry: entry["path"].encode("utf-8"))
    status_value = "dirty" if entries else "clean"
    if expected["working_tree"]["mode"] == "excluded":
        return {"status": status_value, "mode": "excluded", "entries": []}
    return {"status": status_value, "mode": "included", "entries": entries}


def _reject_skip_worktree(repository: _Repository, pathspecs: list[str]) -> None:
    """Sparse checkout対象を通常のworking treeとして誤判定しない。

    Args:
        repository: 読み取り対象repository。
        pathspecs: 確認対象を限定するliteral pathspec。

    Raises:
        _CheckProblem: Scope内にskip-worktree entryがある場合。
    """

    content = repository.git("ls-files", "-v", "-z", "--", *pathspecs)
    if not content:
        return
    if not content.endswith(b"\x00"):
        raise _CheckProblem("working_tree", "Git index出力がNUL終端ではありません。")
    for item in content[:-1].split(b"\x00"):
        tag, separator, raw_path = item.partition(b" ")
        if separator != b" " or len(tag) != 1:
            raise _CheckProblem("working_tree", "Git index entryを解析できません。")
        if tag.upper() == b"S":
            path = raw_path.decode("utf-8", errors="replace")
            raise _CheckProblem(
                "working_tree",
                f"skip-worktree entryは初期版で比較できません: {path}",
            )


def _head_entries(
    repository: _Repository,
    pathspecs: list[str],
) -> list[dict[str, str]]:
    """HEAD treeからscope内の追跡fileを取得する。

    Args:
        repository: 読み取り対象repository。
        pathspecs: 確認対象を限定するliteral pathspec。

    Returns:
        Path、mode、type、content OIDを持つ追跡file一覧。

    Raises:
        _CheckProblem: Popr schemaで表せないentryを含む場合。
    """

    content = repository.git("ls-tree", "-r", "-z", "HEAD", "--", *pathspecs)
    if not content:
        return []
    if not content.endswith(b"\x00"):
        raise _CheckProblem("working_tree", "HEAD tree出力がNUL終端ではありません。")
    entries: list[dict[str, str]] = []
    for item in content[:-1].split(b"\x00"):
        metadata, separator, raw_path = item.partition(b"\t")
        parts = metadata.decode("ascii", errors="strict").split()
        if separator != b"\t" or len(parts) != 3:
            raise _CheckProblem("working_tree", "HEAD tree entryを解析できません。")
        mode, object_type, content_oid = parts
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _CheckProblem(
                "working_tree", "UTF-8で表せないpathは初期版で扱えません。"
            ) from error
        _repository_path(path, "working_tree")
        if object_type != "blob":
            raise _CheckProblem(
                "working_tree",
                f"初期版で表せないGit entryです: {path}: {object_type}",
            )
        value_type = "symlink" if mode == "120000" else "regular"
        _entry_type_and_mode(value_type, mode, "working_tree")
        entries.append(
            {
                "path": path,
                "mode": mode,
                "type": value_type,
                "content_oid": content_oid,
            }
        )
    return entries


def _nul_paths(content: bytes, component: str) -> list[str]:
    if not content:
        return []
    if not content.endswith(b"\x00"):
        raise _CheckProblem(component, "Gitのpath出力がNUL終端ではありません。")
    try:
        paths = [item.decode("utf-8") for item in content[:-1].split(b"\x00")]
    except UnicodeDecodeError as error:
        raise _CheckProblem(
            component, "UTF-8で表せないpathは初期版で扱えません。"
        ) from error
    return [_repository_path(path, component) for path in paths]


def _working_entry(
    repository: _Repository,
    path: str,
    *,
    head_entry: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    try:
        parent_descriptor, leaf = _open_parent_directory(repository.worktree, path)
    except FileNotFoundError:
        if head_entry is None:
            return None
        return {
            "path": path,
            "status": "deleted",
            "head_mode": head_entry["mode"],
            "head_type": head_entry["type"],
            "head_content_oid": head_entry["content_oid"],
        }
    try:
        try:
            metadata = os.stat(leaf, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            if head_entry is None:
                return None
            return {
                "path": path,
                "status": "deleted",
                "head_mode": head_entry["mode"],
                "head_type": head_entry["type"],
                "head_content_oid": head_entry["content_oid"],
            }
        except OSError as error:
            raise _CheckProblem(path, str(error)) from error

        link_target: str | None = None
        if stat.S_ISLNK(metadata.st_mode):
            mode = "120000"
            value_type = "symlink"
            try:
                link_target = os.readlink(leaf, dir_fd=parent_descriptor)
            except OSError as error:
                raise _CheckProblem(path, str(error)) from error
            content_oid = (
                repository.git(
                    "hash-object",
                    "--stdin",
                    input_bytes=os.fsencode(link_target),
                )
                .decode()
                .strip()
            )
            observed_metadata = metadata
        elif stat.S_ISREG(metadata.st_mode):
            flags = os.O_RDONLY | os.O_NOFOLLOW
            try:
                descriptor = os.open(leaf, flags, dir_fd=parent_descriptor)
            except OSError as error:
                raise _CheckProblem(path, str(error)) from error
            with os.fdopen(descriptor, "rb") as input_file:
                opened_before = os.fstat(input_file.fileno())
                if not stat.S_ISREG(opened_before.st_mode):
                    raise _CheckProblem(path, "確認中にfile typeが変わりました。")
                mode = "100755" if opened_before.st_mode & stat.S_IXUSR else "100644"
                value_type = "regular"
                content_oid = (
                    repository.git("hash-object", "--stdin", input_file=input_file)
                    .decode()
                    .strip()
                )
                observed_metadata = os.fstat(input_file.fileno())
                if _metadata_identity(opened_before) != _metadata_identity(
                    observed_metadata
                ):
                    raise _CheckProblem(
                        path, "確認中にfile内容またはmetadataが変わりました。"
                    )
        else:
            raise _CheckProblem(path, "初期版ではregular fileとsymlinkだけを扱います。")
        _ensure_path_stable(
            repository.worktree,
            path,
            parent_descriptor=parent_descriptor,
            metadata=observed_metadata,
            link_target=link_target,
        )
    finally:
        os.close(parent_descriptor)
    return {
        "path": path,
        "status": "present",
        "mode": mode,
        "type": value_type,
        "content_oid": content_oid,
    }


def _open_parent_directory(worktree: Path, path: str) -> tuple[int, str]:
    """Symlinkを辿らずrepository rootから親directoryを固定する。

    Args:
        worktree: 解決済みrepository root。
        path: Repository相対path。

    Returns:
        固定した親directoryのfile descriptorと最終path component。

    Raises:
        FileNotFoundError: 親directoryが存在しない場合。
        _CheckProblem: 親directoryを安全に固定できない場合。
    """

    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise _CheckProblem(
            "working_tree", "Symlinkを辿らないfile openを利用できません。"
        )
    parts = PurePosixPath(path).parts
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        current_descriptor = os.open(worktree, flags)
    except OSError as error:
        raise _CheckProblem("working_tree", str(error)) from error
    try:
        for part in parts[:-1]:
            try:
                next_descriptor = os.open(
                    part,
                    flags,
                    dir_fd=current_descriptor,
                )
            except FileNotFoundError:
                raise
            except OSError as error:
                raise _CheckProblem(
                    "working_tree",
                    f"親directoryを安全に開けません: {path}: {error}",
                ) from error
            os.close(current_descriptor)
            current_descriptor = next_descriptor
        return current_descriptor, parts[-1]
    except Exception:
        os.close(current_descriptor)
        raise


def _ensure_path_stable(
    worktree: Path,
    path: str,
    *,
    parent_descriptor: int,
    metadata: os.stat_result,
    link_target: str | None,
) -> None:
    """Hash取得後も同じ親directoryとfileがpathに存在するか確認する。

    Args:
        worktree: 解決済みrepository root。
        path: Repository相対path。
        parent_descriptor: Hash取得に使った固定済み親directory。
        metadata: Hash取得に使ったfile metadata。
        link_target: Symlinkの場合のlink target。

    Raises:
        _CheckProblem: 確認中にpathが差し替えられた場合。
    """

    try:
        current_parent, leaf = _open_parent_directory(worktree, path)
    except (FileNotFoundError, _CheckProblem) as error:
        raise _CheckProblem(
            path, f"確認中に親directoryが変わりました: {error}"
        ) from error
    try:
        if _inode_identity(os.fstat(parent_descriptor)) != _inode_identity(
            os.fstat(current_parent)
        ):
            raise _CheckProblem(path, "確認中に親directoryが差し替えられました。")
        try:
            current_metadata = os.stat(
                leaf,
                dir_fd=current_parent,
                follow_symlinks=False,
            )
        except OSError as error:
            raise _CheckProblem(path, f"確認中にfileが変わりました: {error}") from error
        if _metadata_identity(metadata) != _metadata_identity(current_metadata):
            raise _CheckProblem(path, "確認中にfileが差し替えられました。")
        if link_target is not None:
            try:
                current_target = os.readlink(leaf, dir_fd=current_parent)
            except OSError as error:
                raise _CheckProblem(path, str(error)) from error
            if current_target != link_target:
                raise _CheckProblem(path, "確認中にsymlink targetが変わりました。")
    finally:
        os.close(current_parent)


def _inode_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _metadata_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _observe_skill_versions(
    repository: _Repository,
    expected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for entry in expected:
        path = Path(entry["path"])
        try:
            metadata = path.lstat()
        except OSError as error:
            raise _CheckProblem(entry["path"], str(error)) from error
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise _CheckProblem(entry["path"], "skill sourceは通常fileが必要です。")
        content_oid = (
            repository.git("hash-object", "--no-filters", "--", str(path))
            .decode()
            .strip()
        )
        observed.append({"path": entry["path"], "content_oid": content_oid})
    return observed


def _observe_project_rules(
    repository: _Repository,
    expected: list[dict[str, Any]],
    *,
    current_head: str,
) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for entry in expected:
        _require_blob(repository, entry["blob_oid"], "project_rules.blob_oid")
        source_sha = entry["source_sha"]
        if entry["source"] == "head":
            source_sha = current_head
        _require_commit(repository, source_sha, "project_rules")
        try:
            blob_oid = (
                repository.git("rev-parse", f"{source_sha}:{entry['path']}")
                .decode()
                .strip()
            )
        except _CheckProblem as error:
            raise _CheckProblem(
                "project_rules",
                f"規約fileを取得できません: {entry['path']}: {error.detail}",
            ) from error
        _require_blob(repository, blob_oid, "project_rules.blob_oid")
        observed.append(
            {
                "source": entry["source"],
                "source_sha": source_sha,
                "path": entry["path"],
                "blob_oid": blob_oid,
            }
        )
    return observed


def _require_blob(repository: _Repository, oid: str, component: str) -> None:
    """Git objectがproject ruleを表すblobであることを確認する。

    Args:
        repository: Objectを取得するrepository。
        oid: 確認するGit object ID。
        component: 問題発生時に報告するcomponent名。

    Raises:
        _CheckProblem: Objectを取得できない、またはblobではない場合。
    """

    object_type = repository.git("cat-file", "-t", oid).decode().strip()
    if object_type != "blob":
        raise _CheckProblem(component, f"project ruleはblobが必要です: {object_type}")
