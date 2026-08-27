# Agents Repository Guidelines

このリポジトリは、ユーザーグローバルの Codex / Claude Code 設定を管理するための作業場所です。

## 方針

- 実体のある手順は `shared/references/` に置く。
- Codex 用 wrapper は `codex/skills/*/SKILL.md` に置く。
- skill を新規作成するときは、Claude Code にも反映するかをユーザーへ必ず確認する。反映する場合は Claude Code 用 wrapper を `claude/skills/*/SKILL.md` に置く。
- 明示確認されていない既存の Claude Code 用 wrapper は、Opus 5 向けの再設計が完了するまで `claude/skills.disabled/*/SKILL.md` に退避する。
- Claude Code 用 subagent は、Opus 5 向けの再設計が完了するまで `claude/agents.disabled/*.md` に退避する。
- 新規プロジェクト用の AGENTS.md / CLAUDE.md テンプレートは `templates/` に置き、2 ファイルを同一内容で対称管理する (ラッパー・@import は使わない)。ローカル同期の対象外で、このリポジトリが正本。
- Portable Harness templateは`templates/REVIEW_HARNESS.md`と`templates/.review-harness/contracts/`を正本とする。Contract memberは対応する`shared/references/`のexact snapshotとし、更新時はmanifestのSHA-256も同時に更新する。
- 認証情報、履歴、SQLite、cache、file-history は管理しない。
- `tp-management-nippo-insight` を含む `tp-*` で始まる skill / agent / reference は、会社に関する情報を含み得るためこの GitHub リポジトリでは管理しない。
- ローカルで設定を更新したら `scripts/sync-from-local.sh` でこのリポジトリへ同期する。

## 同期先

- `codex/AGENTS.md` -> `~/.codex/AGENTS.md`
- `codex/skills/` -> `~/.agents/skills/`
- `codex/agents/` -> `~/.codex/agents/`
- `codex/hooks.json` -> `~/.codex/hooks.json`
- `claude/CLAUDE.md` -> `~/.claude/CLAUDE.md`
- `claude/skills/` -> `~/.claude/skills/`
- `claude/skills.disabled/` -> `~/.claude/skills.disabled/`
- `claude/agents.disabled/` -> `~/.claude/agents.disabled/`
- `shared/references/` -> `~/.agents/references/`

## 注意

- `~/.codex/config.toml` は secrets を含みやすいため、実物は管理しない。
- `codex/config.example.toml` は構成の参考だけに使う。
- `tp-*` のローカル専用 skill / agent は GitHub に含めない。同期スクリプトと `.gitignore` で除外する。
- Claude Code の既存ユーザーグローバル skill と subagent を一時無効化し、明示確認した新規skillだけを有効化する理由は `docs/decisions/2026-07-26-disable-claude-skills-and-subagents-for-claude-5.md` を参照する。
- GitHub に push する前に `scripts/validate.sh` を実行する。
