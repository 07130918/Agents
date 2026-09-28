"""旧schema 1.0の保存済み記録を隔離領域に用意する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from review_harness_artifacts.canonical import (
    canonicalize,
    parse_json_bytes,
    sha256_hex,
)

REPOSITORY_ID = "repository-test"
RUN_ID = "run-test"


def write_record(
    state_root: Path,
    record_id: str,
    record_type: str = "review",
    *,
    references: list[Path] | None = None,
    evidence: dict[str, bytes] | None = None,
    payload: dict[str, Any] | None = None,
) -> Path:
    """廃止したappend実装を使わず、既知の旧形式を保存する。"""
    run_root = state_root / "review-harness" / REPOSITORY_ID / RUN_ID
    records = run_root / "records"
    objects = run_root / "objects" / "sha256"
    records.mkdir(parents=True, exist_ok=True)
    objects.mkdir(parents=True, exist_ok=True)
    sequence = len(list(records.iterdir()))
    stored_references = []
    for path in references or []:
        content = path.read_bytes()
        record = parse_json_bytes(content)
        stored_references.append(
            {
                "record_id": record["record_id"],
                "sequence": record["sequence"],
                "content_sha256": sha256_hex(content),
            }
        )
    stored_evidence = []
    for label, content in sorted((evidence or {}).items()):
        content_hash = sha256_hex(content)
        (objects / content_hash).write_bytes(content)
        stored_evidence.append(
            {
                "label": label,
                "content_sha256": content_hash,
                "byte_length": len(content),
                "object_path": f"objects/sha256/{content_hash}",
            }
        )
    value = {
        "schema_version": "1.0",
        "repository_id": REPOSITORY_ID,
        "run_id": RUN_ID,
        "sequence": sequence,
        "record_id": record_id,
        "record_type": record_type,
        "created_at": "2026-08-28T00:00:00Z",
        "references": stored_references,
        "evidence": stored_evidence,
        "payload": payload or {},
    }
    content = canonicalize(value)
    path = records / f"{sequence:012d}--{record_id}--{sha256_hex(content)}.json"
    path.write_bytes(content)
    return path


def replace_record(path: Path, value: dict[str, Any]) -> Path:
    """内容とfile名hashを整合的に変更し、検出限界も試験する。"""
    content = canonicalize(value)
    replacement = path.with_name(
        f"{value['sequence']:012d}--{value['record_id']}--{sha256_hex(content)}.json"
    )
    path.unlink()
    replacement.write_bytes(content)
    return replacement
