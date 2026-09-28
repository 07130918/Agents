"""旧作業記録と根拠bytesを変更せず、限定した整合性を確認する。"""

from __future__ import annotations

import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import canonicalize, parse_json_bytes, sha256_hex
from .contract import (
    require_identifier,
    validate_record,
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
            status: 読取検証の結果。

        Returns:
            状態、件数、次の操作、保存先を持つ辞書。
        """

        last = self.records[-1] if self.records else None
        return {
            "status": status,
            "summary": f"作業記録{len(self.records)}件と根拠{self.evidence_count}件を検証しました。",
            "next_actions": [
                "旧記録は参照専用です。整合性の確認は再開許可や完全な改変検知を意味しません。"
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
    """1つのrepositoryとrunに限定して既存記録を読む。"""

    def __init__(
        self,
        *,
        state_root: Path,
        repository_id: str,
        run_id: str,
    ) -> None:
        self.repository_id = require_identifier(repository_id, field="repository_id")
        self.run_id = require_identifier(run_id, field="run_id")
        self.state_root = state_root.expanduser().absolute()
        self.run_root = (
            self.state_root / "review-harness" / self.repository_id / self.run_id
        )
        self.records_root = self.run_root / "records"
        self.objects_root = self.run_root / "objects" / "sha256"
        self._prepare_layout()

    def validate(self) -> ValidationResult:
        """保存済みrunを変更せず、全記録と根拠を再検証する。

        Returns:
            検証済みの記録と根拠件数。

        Raises:
            ArtifactError: 形式、連番、参照、根拠bytes等に不整合がある場合。
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
                )
            raw = _read_regular_file(path, field=str(path))
            value = parse_json_bytes(raw, field=str(path))
            if canonicalize(value) != raw:
                fail(
                    field=str(path),
                    invariant="stored_record_must_be_canonical_json",
                    detail="保存済み作業記録がRFC 8785 JCSと一致しません。",
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
                )
            if record["record_id"] != match.group(
                "record_id"
            ) or content_hash != match.group("sha256"):
                fail(
                    record_id=record["record_id"],
                    field=str(path),
                    invariant="record_filename_must_match_content",
                    detail="file名のIDまたはハッシュが保存内容と一致しません。",
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
                )
            if record["record_id"] in by_id:
                fail(
                    record_id=record["record_id"],
                    field="record_id",
                    invariant="record_ids_must_be_unique",
                    detail="同じ作業記録IDが複数回保存されています。",
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
                )
        if actual_objects != referenced_objects:
            fail(
                field="objects/sha256",
                invariant="evidence_objects_must_match_references",
                detail=(
                    f"参照されていないobject: {sorted(actual_objects - referenced_objects)}; "
                    f"不足object: {sorted(referenced_objects - actual_objects)}"
                ),
                next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
            )
        return ValidationResult(
            repository_id=self.repository_id,
            run_id=self.run_id,
            run_root=self.run_root,
            records=tuple(stored_records),
            evidence_count=len(actual_objects),
        )

    def _prepare_layout(self) -> None:
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
                next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
            )
        object_entries = {entry.name for entry in (self.run_root / "objects").iterdir()}
        if object_entries != {"sha256"}:
            fail(
                field=str(self.run_root / "objects"),
                invariant="objects_directory_must_contain_only_sha256",
                detail=f"未知または不足した階層です: {sorted(object_entries)}",
                next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
            )

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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                    next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
                )
            names.add(content_hash)
        return names


def _require_directory(path: Path, *, field: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        fail(
            field=field,
            invariant="store_directory_must_exist",
            detail=str(error),
            next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
        )
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        fail(
            field=field,
            invariant="store_path_must_be_real_directory",
            detail="保存先はsymbolic linkではない実directoryである必要があります。",
            next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
            next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
        )
    for entry in entries:
        metadata = entry.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            fail(
                field=str(entry),
                invariant="store_entries_must_be_regular_files",
                detail="保存済み記録と根拠は通常fileである必要があります。",
                next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
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
                next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
            )
        return path.read_bytes()
    except ArtifactError:
        raise
    except OSError as error:
        fail(
            field=field,
            invariant="file_must_be_readable",
            detail=str(error),
            next_action="原本を編集せず、保存時の版・記録・参照先を確認してください。",
        )
