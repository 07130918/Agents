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
scripts/diff-local.sh
scripts/apply-to-local.sh
```

## 管理しないもの

- 認証情報
- API key
- セッション履歴
- SQLite state
- cache
- file-history
- archived sessions
- shell snapshots

