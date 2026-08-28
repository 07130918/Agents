"""作業記録を追記または読み取り検証する小さなコマンドを提供する。"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import CONTRACT_VERSION
from .canonical import canonicalize, load_json
from .contract import require_identifier
from .errors import ArtifactError
from .store import RunStore

DEFAULT_STATE_ROOT = "~/.agents/state"


class StructuredArgumentParser(argparse.ArgumentParser):
    """引数誤りも他の失敗と同じ構造化JSONへ変換する。"""

    def error(self, message: str) -> NoReturn:
        raise ArtifactError(
            record_id=None,
            field="argv",
            invariant="cli_arguments_must_be_valid",
            detail=message,
            next_action="usageを確認して引数を修正してください。",
        )


def _write_json(value: Any, *, stream: Any = sys.stdout) -> None:
    stream.buffer.write(canonicalize(value) + b"\n")
    stream.flush()


def _evidence_mapping(arguments: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, argument in enumerate(arguments):
        if "=" not in argument:
            raise ArtifactError(
                record_id=None,
                field=f"evidence[{index}]",
                invariant="evidence_argument_must_use_label_equals_path",
                detail=f"根拠指定に=がありません: {argument}",
                next_action="--evidence stdout=/path/to/stdout.log の形式で指定してください。",
            )
        label, path_value = argument.split("=", 1)
        require_identifier(label, field=f"evidence[{index}].label")
        if not path_value:
            raise ArtifactError(
                record_id=None,
                field=f"evidence[{index}].path",
                invariant="evidence_path_must_not_be_empty",
                detail="根拠fileのpathが空です。",
                next_action="正確なbytesを保存した通常fileを指定してください。",
            )
        if label in result:
            raise ArtifactError(
                record_id=None,
                field=f"evidence[{index}].label",
                invariant="evidence_labels_must_be_unique",
                detail=f"同じ根拠labelが重複しています: {label}",
                next_action="1つのlabelにつき1つのfileだけを指定してください。",
            )
        result[label] = Path(path_value)
    return result


def _store_from_args(args: argparse.Namespace, *, create: bool) -> RunStore:
    candidate_value = getattr(args, "candidate_worktree", None)
    return RunStore(
        state_root=Path(args.state_root),
        repository_id=args.repository_id,
        run_id=args.run_id,
        create=create,
        candidate_worktree=(
            Path(candidate_value) if candidate_value is not None else None
        ),
    )


def _append_command(args: argparse.Namespace) -> int:
    """作業記録要求と根拠fileを個人環境へ追記する。

    Args:
        args: 解析済みコマンド引数。

    Returns:
        成功時の終了code 0。
    """

    request = load_json(Path(args.record))
    result = _store_from_args(args, create=True).append(
        request,
        _evidence_mapping(args.evidence),
    )
    _write_json(result.as_dict(status="appended"))
    return 0


def _validate_command(args: argparse.Namespace) -> int:
    """保存済みrunを変更せず最後まで検証する。

    Args:
        args: 解析済みコマンド引数。

    Returns:
        正常時の終了code 0。
    """

    result = _store_from_args(args, create=False).validate()
    _write_json(result.as_dict(status="valid"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """appendとvalidateだけを持つ引数解析器を作る。

    Returns:
        公開コマンドの引数解析器。
    """

    parser = StructuredArgumentParser(prog="review-harness-artifacts")
    parser.add_argument("--version", action="version", version=CONTRACT_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_run_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--state-root", default=DEFAULT_STATE_ROOT)
        command.add_argument("--repository-id", required=True)
        command.add_argument("--run-id", required=True)

    append_parser = commands.add_parser(
        "append",
        help="作業記録1件と根拠fileを上書きせず追記します。",
    )
    add_run_arguments(append_parser)
    append_parser.add_argument("--candidate-worktree", required=True)
    append_parser.add_argument("--record", required=True)
    append_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="根拠labelと通常fileを指定します。複数回指定できます。",
    )
    append_parser.set_defaults(handler=_append_command)

    validate_parser = commands.add_parser(
        "validate",
        help="保存済みrunを変更せず再検証します。",
    )
    add_run_arguments(validate_parser)
    validate_parser.set_defaults(handler=_validate_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """公開コマンドを実行し、成功と失敗を常にJSONで返す。

    Args:
        argv: process引数。`None`なら`sys.argv`を使用する。

    Returns:
        成功時0、入力または保存済みrunが不正な場合2。
    """

    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except ArtifactError as error:
        _write_json(
            {
                "status": "error",
                "summary": error.detail,
                "next_actions": [error.next_action],
                "artifacts": [],
                "error": error.as_dict(),
            },
            stream=sys.stderr,
        )
        return 2
    except Exception as error:  # noqa: BLE001 - CLI境界ではJSON以外のtracebackを出さない。
        structured = ArtifactError(
            record_id=None,
            field="command",
            invariant="unexpected_command_failure",
            detail=f"{type(error).__name__}: {error}",
            next_action="同じrunへ追記せず、入力と保存先を確認してください。",
        )
        _write_json(
            {
                "status": "error",
                "summary": structured.detail,
                "next_actions": [structured.next_action],
                "artifacts": [],
                "error": structured.as_dict(),
            },
            stream=sys.stderr,
        )
        return 2
