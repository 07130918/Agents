# Agents

Codex と Claude Code のユーザーグローバル設定を管理するリポジトリです。

## 管理対象

```text
shared/references/   skill 本体の共通参照
codex/               Codex 用グローバル設定と wrapper
claude/              Claude Code 用グローバル設定と wrapper
scripts/             同期・検証スクリプト
docs/                運用メモ
```

## 基本運用

ローカルの `~/.codex`、`~/.claude`、`~/.agents` を更新したあと、このリポジトリへ同期します。

```bash
scripts/sync-from-local.sh
scripts/validate.sh
git status
git add .
git commit -m "chore: グローバルAI設定を更新"
git push
```

GitHub 側の変更をローカル設定へ反映する場合は、内容を確認してから実行します。

```bash
scripts/validate.sh
scripts/diff-local.sh
scripts/apply-to-local.sh
```

`scripts/validate.sh` と `scripts/diff-local.sh` で `AGENTS.md` / `CLAUDE.md` / skill wrapper の意味が壊れていないことを確認してから `scripts/apply-to-local.sh` を実行します。ローカルから同期する `scripts/sync-from-local.sh` は本文を自動変換せず、同期後の `scripts/validate.sh` で禁止文字や秘密情報を検出します。

## 管理しないもの

- 認証情報
- API key
- セッション履歴
- SQLite state
- cache
- file-history
- archived sessions
- shell snapshots
- `tp-management-nippo-insight` を含む `tp-*` の skill / agent / reference

`tp-*` は会社に関する情報を含み得るローカル専用設定です。今後 `tp-` から始まる skill や agent が増えても、この GitHub リポジトリには含めません。
