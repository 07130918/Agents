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
claude/skills/ -> ~/.claude/skills/
claude/agents/ -> ~/.claude/agents/
```

## Excluded Runtime State

`~/.codex` と `~/.claude` には、履歴、認証、cache、SQLite、shell snapshot などの runtime state が含まれます。これらは GitHub で管理しません。

