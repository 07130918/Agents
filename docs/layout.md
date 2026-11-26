# Layout

## Canonical Sources

`shared/references/` を skill 本体の canonical source とします。

Codex と Claude Code の `SKILL.md` は、frontmatter と `shared/references/` への参照だけを持つ薄い wrapper にします。

## Directory Mapping

```text
shared/references/ -> ~/.agents/references/
claude/CLAUDE.md -> ~/.claude/CLAUDE.md
codex/AGENTS.md -> ~/.codex/AGENTS.md (symlink -> ~/.claude/CLAUDE.md)
~/.gemini/AGENTS.md (symlink -> ~/.claude/CLAUDE.md)
codex/skills/ -> ~/.agents/skills/
codex/agents/ -> ~/.codex/agents/
codex/hooks.json -> ~/.codex/hooks.json
claude/skills/ -> ~/.claude/skills/
claude/skills.disabled/ -> ~/.claude/skills.disabled/
claude/agents.disabled/ -> ~/.claude/agents.disabled/
gemini/config/skills.json -> ~/.gemini/config/skills.json
gemini/config/hooks.json -> ~/.gemini/config/hooks.json
```

Claude Code のユーザーグローバル skill は、有効な定義を `skills/`、退避中の定義を `skills.disabled/` で管理します。`scripts/apply-to-local.sh` は両方を対応するローカルディレクトリへ同期し、subagent は `~/.claude/agents.disabled/` に配置します。新規追加と再導入の判断は [ADR](decisions/2026-07-26-disable-claude-skills-and-subagents-for-claude-5.md) を参照してください。

## Excluded Runtime State

`~/.codex`、`~/.claude`、`~/.gemini` には、履歴、認証、API key を含む MCP 設定 (`~/.gemini/config/mcp_config.json`)、cache、SQLite、shell snapshot などの runtime state が含まれます。これらは GitHub で管理しません。

各リポジトリの `.serena/` に保存される project memory と onboarding state もローカルの runtime state とし、このリポジトリでは管理・検証しません。
