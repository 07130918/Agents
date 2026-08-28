"""個人環境へ作業記録と根拠bytesを上書きせず保存する。"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION
from .canonical import canonicalize, parse_json_bytes, sha256_hex
from .contract import (
    require_identifier,
    validate_record,
    validate_request,
)
from .errors import ArtifactError, fail

RECORD_FILE_PATTERN = re.compile(
    r"(?P<sequence>\d{12})--(?P<record_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})--"
    r"(?P<sha256>[0-9a-f]{64})\.json\Z"
)
EXPECTED_RUN_ENTRIES = {"records", "objects"}


@dataclass(frozen=True, slots=True)
class StoredRecord:
    """検証済み作業記録と保存位置を保持する。"""

    value: dict[str, Any]
    content_sha256: str
    path: Path


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """1つのrunを最後まで検証した結果を保持する。"""

    repository_id: str
    run_id: str
    run_root: Path
    records: tuple[StoredRecord, ...]
    evidence_count: int

    def as_dict(self, *, status: str) -> dict[str, Any]:
        """コマンドが返す小さなJSONへ変換する。

        Args:
            status: `appended`または`valid`。

        Returns:
            状態、件数、次の操作、保存先を持つ辞書。
        """

        last = self.records[-1] if self.records else None
        return {
            "status": status,
            "summary": f"作業記録{len(self.records)}件と根拠{self.evidence_count}件を検証しました。",
            "next_actions": [
                "次の工程を記録する前に、このrun_idを引き続き使用してください。"
            ],
            "artifacts": [str(self.run_root)],
            "repository_id": self.repository_id,
            "run_id": self.run_id,
            "record_count": len(self.records),
            "evidence_count": self.evidence_count,
            "last_record": (
                None
                if last is None
                else {
                    "record_id": last.value["record_id"],
                    "sequence": last.value["sequence"],
                    "content_sha256": last.content_sha256,
                    "path": str(last.path),
                }
            ),
        }


class RunStore:
    """1つのrepositoryとrunに限定した追記型保存先を操作する。"""

    def __init__(
        self,
        *,
        state_root: Path,
        repository_id: str,
        run_id: str,
        create: bool,
        candidate_worktree: Path | None = None,
    ) -> None:
        self.repository_id = require_identifier(repository_id, field="repository_id")
        self.run_id = require_identifier(run_id, field="run_id")
        self.state_root = state_root.expanduser().absolute()
        self.run_root = (
            self.state_root / "review-harness" / self.repository_id / self.run_id
        )
        self.records_root = self.run_root / "records"
        self.objects_root = self.run_root / "objects" / "sha256"
        if candidate_worktree is not None:
            self._reject_candidate_store(candidate_worktree)
        self._prepare_layout(create=create)

    def append(
        self,
        request_value: Any,
        evidence_paths: Mapping[str, Path],
    ) -> ValidationResult:
        """作業記録1件と根拠bytesを上書きせず追記する。

        既存runを最初に再検証し、参照先のID、通し番号、内容ハッシュは
        保存済み記録からtool側で補完する。入力側にhashを要求しない。

        Args:
            request_value: 記録ID、種別、日時、参照ID、payloadを持つJSON値。
            evidence_paths: 根拠labelと読み取り元fileの対応。

        Returns:
            追記後に全体を再検証した結果。
        """

        current = self.validate()
        request = validate_request(request_value)
        record_id = request["record_id"]
        by_id = {stored.value["record_id"]: stored for stored in current.records}
        if record_id in by_id:
            fail(
                record_id=record_id,
                field="record_id",
                invariant="record_id_must_not_be_reused",
                detail="同じrunですでに使用された作業記録IDです。",
                next_action="新しい安定したrecord_idを指定してください。",
            )
        references: list[dict[str, Any]] = []
        for reference_id in sorted(
            request["references"], key=lambda item: item.encode("utf-8")
        ):
            referenced = by_id.get(reference_id)
            if referenced is None:
                fail(
                    record_id=record_id,
                    field="references",
                    invariant="reference_must_point_to_prior_record_in_same_run",
                    detail=f"同じrunの確定済み過去記録が見つかりません: {reference_id}",
                    next_action="未来、自分自身、別runではなく、validate済みの過去record_idを指定してください。",
                )
            references.append(
                {
                    "record_id": reference_id,
                    "sequence": referenced.value["sequence"],
                    "content_sha256": referenced.content_sha256,
                }
            )
        evidence, contents = self._prepare_evidence(evidence_paths)
        record = {
            "schema_version": SCHEMA_VERSION,
            "repository_id": self.repository_id,
            "run_id": self.run_id,
            "sequence": len(current.records),
            "record_id": record_id,
            "record_type": request["record_type"],
            "created_at": request["created_at"],
            "references": references,
            "evidence": evidence,
            "payload": request["payload"],
        }
        validate_record(record)
        record_bytes = canonicalize(record)
        record_hash = sha256_hex(record_bytes)
        record_path = self.records_root / (
            f"{record['sequence']:012d}--{record_id}--{record_hash}.json"
        )
        for content_hash, content in contents.items():
            self._write_content_object(content_hash, content)
        _write_exclusive(record_path, record_bytes)
        return self.validate()

    def validate(self) -> ValidationResult:
        """保存済みrunを変更せず、全記録と根拠を再検証する。

        Returns:
            検証済みの記録と根拠件数。

        Raises:
            ArtifactError: 改変、欠落、追加、参照切れ、通し番号不整合がある場合。
        """

        self._validate_layout()
        record_paths = _regular_files(self.records_root, field="records")
        stored_records: list[StoredRecord] = []
        by_id: dict[str, StoredRecord] = {}
        referenced_objects: set[str] = set()
        for expected_sequence, path in enumerate(
            sorted(record_paths, key=lambda item: item.name)
        ):
            match = RECORD_FILE_PATTERN.fullmatch(path.name)
            if match is None:
                fail(
                    field=str(path),
                    invariant="record_filename_must_match_schema",
                    detail="作業記録file名から通し番号、ID、内容ハッシュを復元できません。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            raw = _read_regular_file(path, field=str(path))
            value = parse_json_bytes(raw, field=str(path))
            if canonicalize(value) != raw:
                fail(
                    field=str(path),
                    invariant="stored_record_must_be_canonical_json",
                    detail="保存済み作業記録がRFC 8785 JCSと一致しません。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            record = validate_record(value)
            content_hash = sha256_hex(raw)
            filename_sequence = int(match.group("sequence"))
            if (
                filename_sequence != expected_sequence
                or record["sequence"] != expected_sequence
            ):
                fail(
                    record_id=record["record_id"],
                    field="sequence",
                    invariant="record_sequences_must_start_at_zero_without_gaps",
                    detail=(
                        f"期待する通し番号は{expected_sequence}ですが、file名は"
                        f"{filename_sequence}、本文は{record['sequence']}です。"
                    ),
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            if record["record_id"] != match.group(
                "record_id"
            ) or content_hash != match.group("sha256"):
                fail(
                    record_id=record["record_id"],
                    field=str(path),
                    invariant="record_filename_must_match_content",
                    detail="file名のIDまたはハッシュが保存内容と一致しません。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            if (
                record["repository_id"] != self.repository_id
                or record["run_id"] != self.run_id
            ):
                fail(
                    record_id=record["record_id"],
                    field="repository_id|run_id",
                    invariant="record_must_belong_to_selected_run",
                    detail="作業記録が保存先のrepositoryまたはrunと一致しません。",
                    next_action="別runの記録を混ぜず、新しいrunを開始してください。",
                )
            if record["record_id"] in by_id:
                fail(
                    record_id=record["record_id"],
                    field="record_id",
                    invariant="record_ids_must_be_unique",
                    detail="同じ作業記録IDが複数回保存されています。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            self._validate_record_references(record, by_id)
            referenced_objects.update(self._validate_record_evidence(record))
            stored = StoredRecord(record, content_hash, path)
            stored_records.append(stored)
            by_id[record["record_id"]] = stored
        object_paths = _regular_files(self.objects_root, field="objects/sha256")
        actual_objects = {path.name for path in object_paths}
        for object_name in actual_objects:
            if re.fullmatch(r"[0-9a-f]{64}", object_name) is None:
                fail(
                    field=str(self.objects_root / object_name),
                    invariant="evidence_object_name_must_be_sha256",
                    detail="根拠object名がSHA-256ではありません。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
        if actual_objects != referenced_objects:
            fail(
                field="objects/sha256",
                invariant="evidence_objects_must_match_references",
                detail=(
                    f"参照されていないobject: {sorted(actual_objects - referenced_objects)}; "
                    f"不足object: {sorted(referenced_objects - actual_objects)}"
                ),
                next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
            )
        return ValidationResult(
            repository_id=self.repository_id,
            run_id=self.run_id,
            run_root=self.run_root,
            records=tuple(stored_records),
            evidence_count=len(actual_objects),
        )

    def _prepare_layout(self, *, create: bool) -> None:
        if create:
            _ensure_directory(self.state_root, parents=True, field="state_root")
            current = self.state_root
            for name in (
                "review-harness",
                self.repository_id,
                self.run_id,
                "records",
            ):
                current = current / name
                _ensure_directory(current, parents=False, field=str(current))
            objects = self.run_root / "objects"
            _ensure_directory(objects, parents=False, field=str(objects))
            _ensure_directory(
                self.objects_root, parents=False, field=str(self.objects_root)
            )
            return
        for path in (
            self.state_root,
            self.state_root / "review-harness",
            self.state_root / "review-harness" / self.repository_id,
            self.run_root,
            self.records_root,
            self.run_root / "objects",
            self.objects_root,
        ):
            _require_directory(path, field=str(path))

    def _reject_candidate_store(self, candidate_worktree: Path) -> None:
        try:
            candidate = candidate_worktree.expanduser().resolve(strict=True)
        except OSError as error:
            fail(
                field="candidate_worktree",
                invariant="candidate_worktree_must_exist",
                detail=str(error),
                next_action="対象repositoryの実在するworktreeを指定してください。",
            )
        if not candidate.is_dir():
            fail(
                field="candidate_worktree",
                invariant="candidate_worktree_must_be_directory",
                detail="対象worktreeはdirectoryである必要があります。",
                next_action="対象repositoryのroot directoryを指定してください。",
            )
        planned_run_root = self.run_root.resolve(strict=False)
        if planned_run_root == candidate or candidate in planned_run_root.parents:
            fail(
                field="state_root",
                invariant="run_store_must_be_outside_candidate_worktree",
                detail="作業記録の保存先が対象worktree内にあります。",
                next_action="既定の~/.agents/stateまたは対象外のstate rootを使用してください。",
            )

    def _validate_layout(self) -> None:
        for path in (
            self.run_root,
            self.records_root,
            self.run_root / "objects",
            self.objects_root,
        ):
            _require_directory(path, field=str(path))
        run_entries = {entry.name for entry in self.run_root.iterdir()}
        if run_entries != EXPECTED_RUN_ENTRIES:
            fail(
                field=str(self.run_root),
                invariant="run_root_must_contain_only_expected_directories",
                detail=(
                    f"不足: {sorted(EXPECTED_RUN_ENTRIES - run_entries)}; "
                    f"未知: {sorted(run_entries - EXPECTED_RUN_ENTRIES)}"
                ),
                next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
            )
        object_entries = {entry.name for entry in (self.run_root / "objects").iterdir()}
        if object_entries != {"sha256"}:
            fail(
                field=str(self.run_root / "objects"),
                invariant="objects_directory_must_contain_only_sha256",
                detail=f"未知または不足した階層です: {sorted(object_entries)}",
                next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
            )

    def _prepare_evidence(
        self,
        evidence_paths: Mapping[str, Path],
    ) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
        evidence: list[dict[str, Any]] = []
        contents: dict[str, bytes] = {}
        for label in sorted(evidence_paths, key=lambda item: item.encode("utf-8")):
            require_identifier(label, field="evidence.label")
            source = evidence_paths[label].expanduser().absolute()
            content = _read_regular_file(source, field=f"evidence[{label}]")
            content_hash = sha256_hex(content)
            contents[content_hash] = content
            evidence.append(
                {
                    "label": label,
                    "content_sha256": content_hash,
                    "byte_length": len(content),
                    "object_path": f"objects/sha256/{content_hash}",
                }
            )
        return evidence, contents

    def _write_content_object(self, content_hash: str, content: bytes) -> None:
        path = self.objects_root / content_hash
        if path.exists() or path.is_symlink():
            existing = _read_regular_file(path, field=str(path))
            if existing != content:
                fail(
                    field=str(path),
                    invariant="content_addressed_object_must_match_hash",
                    detail="同じSHA-256の保存先に異なるbytesがあります。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            return
        _write_exclusive(path, content)

    def _validate_record_references(
        self,
        record: dict[str, Any],
        prior_by_id: Mapping[str, StoredRecord],
    ) -> None:
        for reference in record["references"]:
            prior = prior_by_id.get(reference["record_id"])
            if prior is None:
                fail(
                    record_id=record["record_id"],
                    field="references",
                    invariant="reference_must_point_to_prior_record_in_same_run",
                    detail=f"確定済み過去記録が見つかりません: {reference['record_id']}",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            if (
                reference["sequence"] != prior.value["sequence"]
                or reference["content_sha256"] != prior.content_sha256
            ):
                fail(
                    record_id=record["record_id"],
                    field="references",
                    invariant="reference_must_match_prior_record",
                    detail=f"参照先の通し番号または内容ハッシュが一致しません: {reference['record_id']}",
                    next_action="toolが生成した参照を使用してください。",
                )

    def _validate_record_evidence(self, record: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        for evidence in record["evidence"]:
            content_hash = evidence["content_sha256"]
            path = self.objects_root / content_hash
            content = _read_regular_file(path, field=str(path))
            if (
                len(content) != evidence["byte_length"]
                or sha256_hex(content) != content_hash
            ):
                fail(
                    record_id=record["record_id"],
                    field=f"evidence[{evidence['label']}]",
                    invariant="evidence_bytes_must_match_length_and_hash",
                    detail="根拠bytesの長さまたはSHA-256が保存済み参照と一致しません。",
                    next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
                )
            names.add(content_hash)
        return names


def _ensure_directory(path: Path, *, parents: bool, field: str) -> None:
    if path.is_symlink():
        fail(
            field=field,
            invariant="store_path_must_not_be_symlink",
            detail="作業記録の保存先にsymbolic linkは使用できません。",
            next_action="実directoryを指定してください。",
        )
    try:
        path.mkdir(mode=0o700, parents=parents, exist_ok=True)
    except OSError as error:
        fail(
            field=field,
            invariant="store_directory_must_be_creatable",
            detail=str(error),
            next_action="保存先と権限を確認してください。",
        )
    _require_directory(path, field=field)


def _require_directory(path: Path, *, field: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        fail(
            field=field,
            invariant="store_directory_must_exist",
            detail=str(error),
            next_action="正しいstate root、repository_id、run_idを指定してください。",
        )
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail(
            field=field,
            invariant="store_path_must_be_real_directory",
            detail="保存先はsymbolic linkではない実directoryである必要があります。",
            next_action="実directoryを指定してください。",
        )


def _regular_files(directory: Path, *, field: str) -> list[Path]:
    result: list[Path] = []
    try:
        entries = list(directory.iterdir())
    except OSError as error:
        fail(
            field=field,
            invariant="store_directory_must_be_readable",
            detail=str(error),
            next_action="保存先の読み取り権限を確認してください。",
        )
    for entry in entries:
        metadata = entry.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            fail(
                field=str(entry),
                invariant="store_entries_must_be_regular_files",
                detail="保存済み記録と根拠は通常fileである必要があります。",
                next_action="壊れたrunへ追記せず、新しいrunを開始してください。",
            )
        result.append(entry)
    return result


def _read_regular_file(path: Path, *, field: str) -> bytes:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            fail(
                field=field,
                invariant="input_must_be_regular_file",
                detail="symbolic linkやdirectoryは根拠fileとして読めません。",
                next_action="正確なbytesを持つ通常fileを指定してください。",
            )
        return path.read_bytes()
    except ArtifactError:
        raise
    except OSError as error:
        fail(
            field=field,
            invariant="file_must_be_readable",
            detail=str(error),
            next_action="fileの存在と読み取り権限を確認してください。",
        )


def _write_exclusive(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        fail(
            field=str(path),
            invariant="stored_files_must_not_be_overwritten",
            detail="保存先fileがすでに存在します。",
            next_action="同じrunへ再試行する前にvalidateし、新しいrecord_idを使用してください。",
        )
    except OSError as error:
        fail(
            field=str(path),
            invariant="stored_file_must_be_writable",
            detail=str(error),
            next_action="保存先の空き容量と権限を確認してください。",
        )
