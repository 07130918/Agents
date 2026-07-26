# Agents

Codex と Claude Code のユーザーグローバル設定を管理するリポジトリです。

## 管理対象

```text
shared/references/   skill 本体の共通参照
codex/               Codex 用グローバル設定と wrapper
claude/              Claude Code 用グローバル設定と wrapper
templates/           新規プロジェクト用の AGENTS.md / CLAUDE.md テンプレート
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

現在、Claude Code のユーザーグローバル skill と subagent は Claude 5 世代向けに再設計するため一時無効化しています。リポジトリの `claude/skills.disabled/` と `claude/agents.disabled/` を同名のローカルディレクトリへ同期し、有効な `~/.claude/skills/` と `~/.claude/agents/` は作成しません。判断の背景と復帰条件は [ADR](docs/decisions/2026-07-26-disable-claude-skills-and-subagents-for-claude-5.md) を参照してください。

`scripts/validate.sh` を変更した場合は `scripts/validate.test.sh`、ローカル適用処理を変更した場合は `scripts/apply-to-local.test.sh` で回帰確認します。

## 新規プロジェクトのセットアップ

新しいプロジェクトを始めるときは、`templates/` の AGENTS.md / CLAUDE.md をコピーして使うことを推奨します。

```bash
cp templates/AGENTS.md templates/CLAUDE.md <プロジェクトルート>/
```

- 2 ファイルは意図的な対称配置です。冗長でも両方をフル内容で用意し、片方を変更したらもう片方にも同じ変更を反映します (ラッパー・@import・symlink は使わない)
- 記入基準と運用ルールは [templates/README.md](templates/README.md) を参照してください
- `templates/` はローカル同期 (`sync-from-local.sh` / `apply-to-local.sh`) の対象外で、このリポジトリが正本です

## 管理しないもの

- 認証情報
- API key
- セッション履歴
- SQLite state
- cache
- file-history
- archived sessions
- shell snapshots
- Serena の project memory (`.serena/`)
- `tp-management-nippo-insight` を含む `tp-*` の skill / agent / reference

`tp-*` は会社に関する情報を含み得るローカル専用設定です。今後 `tp-` から始まる skill や agent が増えても、この GitHub リポジトリには含めません。
