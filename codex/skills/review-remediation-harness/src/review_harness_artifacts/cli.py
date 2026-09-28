"""旧作業記録の読み取り検証だけを提供する。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import TOOL_VERSION
from .canonical import canonicalize
from .errors import ArtifactError
from .store import RunStore


class StructuredArgumentParser(argparse.ArgumentParser):
    """引数誤りを構造化JSONで返す。"""

    def error(self, message: str) -> NoReturn:
        raise ArtifactError(
            record_id=None,
            field="argv",
            invariant="cli_arguments_must_be_valid",
            detail=message,
            next_action="旧台帳は参照専用です。validateの引数とアーカイブREADMEを確認してください。",
        )


def _write_json(value: Any, *, stream: Any = sys.stdout) -> None:
    stream.buffer.write(canonicalize(value) + b"\n")
    stream.flush()


def build_parser() -> argparse.ArgumentParser:
    """保存先を明示する読取専用CLIを定義する。"""
    parser = StructuredArgumentParser(
        prog="review-harness-artifacts",
        description="旧台帳の読取検証専用。appendとcheck-targetは廃止しました。",
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="旧記録を変更せず検証します。")
    validate.add_argument(
        "--state-root", required=True, help="review-harness/を含む保存先を明示します。"
    )
    validate.add_argument("--repository-id", required=True)
    validate.add_argument("--run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """保存済み記録の限定した整合性だけを確認する。"""
    try:
        args = build_parser().parse_args(argv)
        result = RunStore(
            state_root=Path(args.state_root),
            repository_id=args.repository_id,
            run_id=args.run_id,
        ).validate()
        _write_json(result.as_dict(status="valid"))
        return 0
    except ArtifactError as error:
        _write_json(
            {
                "status": "error",
                "summary": "旧記録またはCLI引数を検証できませんでした。",
                "next_actions": [
                    "原本を変更せず、検証規則名・validate --help・アーカイブREADMEを確認してください。"
                ],
                "artifacts": [],
                "error": {"invariant": error.invariant},
            },
            stream=sys.stderr,
        )
        return 2
    except Exception as error:  # noqa: BLE001 - 保存内容をtracebackへ転載しない。
        _write_json(
            {
                "status": "error",
                "summary": f"旧記録の読取検証に失敗しました: {type(error).__name__}",
                "next_actions": ["原本を変更せず、保存先と対応版を確認してください。"],
                "artifacts": [],
            },
            stream=sys.stderr,
        )
        return 2
