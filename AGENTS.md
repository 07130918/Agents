# Agents Repository Guidelines

このリポジトリは、ユーザーグローバルの Codex / Claude Code 設定を管理するための作業場所です。

## 方針

- 実体のある手順は `shared/references/` に置く。
- Codex 用 wrapper は `codex/skills/*/SKILL.md` に置く。
- Claude Code 用 wrapper は、Opus 5 向けの再設計が完了するまで `claude/skills.disabled/*/SKILL.md` に退避する。
- Claude Code 用 subagent は、Opus 5 向けの再設計が完了するまで `claude/agents.disabled/*.md` に退避する。
- 新規プロジェクト用の AGENTS.md / CLAUDE.md テンプレートは `templates/` に置き、2 ファイルを同一内容で対称管理する (ラッパー・@import は使わない)。ローカル同期の対象外で、このリポジトリが正本。
- 認証情報、履歴、SQLite、cache、file-history は管理しない。
- `tp-management-nippo-insight` を含む `tp-*` で始まる skill / agent / reference は、会社に関する情報を含み得るためこの GitHub リポジトリでは管理しない。
- ローカルで設定を更新したら `scripts/sync-from-local.sh` でこのリポジトリへ同期する。

## 同期先

- `codex/AGENTS.md` -> `~/.codex/AGENTS.md`
- `codex/skills/` -> `~/.agents/skills/`
- `codex/agents/` -> `~/.codex/agents/`
- `codex/hooks.json` -> `~/.codex/hooks.json`
- `claude/CLAUDE.md` -> `~/.claude/CLAUDE.md`
- `claude/skills.disabled/` -> `~/.claude/skills.disabled/`
- `claude/agents.disabled/` -> `~/.claude/agents.disabled/`
- `shared/references/` -> `~/.agents/references/`

## 注意

- `~/.codex/config.toml` は secrets を含みやすいため、実物は管理しない。
- `codex/config.example.toml` は構成の参考だけに使う。
- `tp-*` のローカル専用 skill / agent は GitHub に含めない。同期スクリプトと `.gitignore` で除外する。
- Claude Code のユーザーグローバル skill と subagent を一時無効化している理由と復帰条件は `docs/decisions/2026-07-26-disable-claude-skills-and-subagents-for-opus-5.md` を参照する。
- GitHub に push する前に `scripts/validate.sh` を実行する。
