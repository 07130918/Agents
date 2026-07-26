# Layout

## Canonical Sources

`shared/references/` を skill 本体の canonical source とします。

Codex と Claude Code の `SKILL.md` は、frontmatter と `shared/references/` への参照だけを持つ薄い wrapper にします。

## Directory Mapping

```text
shared/references/ -> ~/.agents/references/
codex/AGENTS.md -> ~/.codex/AGENTS.md
codex/skills/ -> ~/.agents/skills/
codex/agents/ -> ~/.codex/agents/
codex/hooks.json -> ~/.codex/hooks.json
claude/CLAUDE.md -> ~/.claude/CLAUDE.md
claude/skills.disabled/ -> ~/.claude/skills.disabled/
claude/agents.disabled/ -> ~/.claude/agents.disabled/
```

Claude Code のユーザーグローバル skill と subagent は、Opus 5 向けの再設計が完了するまで `skills.disabled/` と `agents.disabled/` に退避します。`scripts/apply-to-local.sh` は既存の有効なディレクトリも退避して、Claude Code がユーザーグローバル拡張を検出しない状態にします。判断の詳細は [ADR](decisions/2026-07-26-disable-claude-skills-and-subagents-for-opus-5.md) を参照してください。

## Excluded Runtime State

`~/.codex` と `~/.claude` には、履歴、認証、cache、SQLite、shell snapshot などの runtime state が含まれます。これらは GitHub で管理しません。

各リポジトリの `.serena/` に保存される project memory と onboarding state もローカルの runtime state とし、このリポジトリでは管理・検証しません。
