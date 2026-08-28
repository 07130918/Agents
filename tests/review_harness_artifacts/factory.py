"""軽量な作業記録toolのテスト入力を生成する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from review_harness_artifacts.store import RunStore

CREATED_AT = "2026-08-28T00:00:00Z"
REPOSITORY_ID = "repository-test"
RUN_ID = "run-test"


def request(
    record_id: str,
    record_type: str,
    *,
    references: list[str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """appendへ渡す最小の作業記録要求を作る。

    Args:
        record_id: run内で一意な作業記録ID。
        record_type: 作業記録の種別。
        references: 参照する過去の作業記録ID。
        payload: 工程固有の任意データ。

    Returns:
        初期版schemaに一致する要求。
    """

    return {
        "record_id": record_id,
        "record_type": record_type,
        "created_at": CREATED_AT,
        "references": references or [],
        "payload": payload or {},
    }


def create_store(state_root: Path, *, run_id: str = RUN_ID) -> RunStore:
    """テスト用run storeを作る。

    Args:
        state_root: 隔離した保存先。
        run_id: テスト対象のrun ID。

    Returns:
        新規作成済みの保存先。
    """

    candidate = state_root.parent / f"candidate-{run_id}"
    candidate.mkdir(exist_ok=True)
    return RunStore(
        state_root=state_root,
        repository_id=REPOSITORY_ID,
        run_id=run_id,
        create=True,
        candidate_worktree=candidate,
    )


def write_evidence(root: Path, name: str, content: bytes) -> Path:
    """根拠として渡す通常fileを作る。

    Args:
        root: fileを置くdirectory。
        name: file名。
        content: 保存する正確なbytes。

    Returns:
        作成したfileのpath。
    """

    path = root / name
    path.write_bytes(content)
    return path
