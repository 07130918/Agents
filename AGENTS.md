# Agents Repository Guidelines

このリポジトリは、ユーザーグローバルの Codex / Claude Code 設定を管理するための作業場所です。

## 方針

- 実体のある手順は `shared/references/` に置く。
- Codex 用 wrapper は `codex/skills/*/SKILL.md` に置く。
- Claude Code 用 wrapper は `claude/skills/*/SKILL.md` に置く。
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
- `claude/agents/` -> `~/.claude/agents/`
- `shared/references/` -> `~/.agents/references/`

## 注意

- `~/.codex/config.toml` は secrets を含みやすいため、実物は管理しない。
- `codex/config.example.toml` は構成の参考だけに使う。
- `tp-*` のローカル専用 skill / agent は GitHub に含めない。同期スクリプトと `.gitignore` で除外する。
- GitHub に push する前に `scripts/validate.sh` を実行する。
