"""作業記録toolの失敗を、再試行方針付きのJSONへ変換する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn


@dataclass(frozen=True, slots=True)
class ArtifactError(Exception):
    """作業記録のどの規則に違反したかを表す。

    Attributes:
        record_id: 関連する作業記録ID。不明な場合は`None`。
        field: 違反を検出した入力または保存項目。
        invariant: 機械判定に使う安定した規則名。
        detail: 人間向けの具体的な原因。
        next_action: 安全に再試行または停止するための案内。
    """

    record_id: str | None
    field: str
    invariant: str
    detail: str
    next_action: str

    def as_dict(self) -> dict[str, str | None]:
        """標準出力へ保存できるJSON値へ変換する。

        Returns:
            失敗箇所、規則、原因、次の操作を持つ辞書。
        """

        return {
            "record_id": self.record_id,
            "field": self.field,
            "invariant": self.invariant,
            "detail": self.detail,
            "next_action": self.next_action,
        }


def fail(
    *,
    field: str,
    invariant: str,
    detail: str,
    next_action: str,
    record_id: str | None = None,
) -> NoReturn:
    """構造化された作業記録エラーを送出する。

    Args:
        field: 違反を検出した項目。
        invariant: 機械判定に使う規則名。
        detail: 人間向けの具体的な原因。
        next_action: 安全な次の操作。
        record_id: 関連する作業記録ID。

    Raises:
        ArtifactError: 常に送出する。
    """

    raise ArtifactError(record_id, field, invariant, detail, next_action)
