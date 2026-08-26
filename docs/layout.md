# Layout

## Canonical Sources

`shared/references/` を skill 本体の canonical source とします。

Codex と Claude Code の `SKILL.md` は、frontmatter と `shared/references/` への参照だけを持つ薄い wrapper にします。

`shared/evals/`には、shared referenceの評価契約を検証するfixtureを置きます。fixtureはリポジトリ内のtest専用で、ユーザーグローバル設定へは同期しません。

## Directory Mapping

```text
shared/references/ -> ~/.agents/references/
codex/AGENTS.md -> ~/.codex/AGENTS.md
codex/skills/ -> ~/.agents/skills/
codex/agents/ -> ~/.codex/agents/
codex/hooks.json -> ~/.codex/hooks.json
claude/CLAUDE.md -> ~/.claude/CLAUDE.md
claude/skills/ -> ~/.claude/skills/
claude/skills.disabled/ -> ~/.claude/skills.disabled/
claude/agents.disabled/ -> ~/.claude/agents.disabled/
```

Claude Code の既存ユーザーグローバル skill とsubagentは、Claude 5 世代向けの再設計が完了するまで `skills.disabled/` と `agents.disabled/` に退避します。新規skillは作成時にClaude Codeへ反映するかをユーザーへ確認し、明示されたwrapperだけを `claude/skills/` で管理します。`scripts/apply-to-local.sh` は管理対象のactive skillだけを `~/.claude/skills/` に同期し、Claude Code agentは引き続き有効化しません。判断の詳細は [ADR](decisions/2026-07-26-disable-claude-skills-and-subagents-for-claude-5.md) を参照してください。

## Excluded Runtime State

`~/.codex` と `~/.claude` には、履歴、認証、cache、SQLite、shell snapshot などの runtime state が含まれます。これらは GitHub で管理しません。

各リポジトリの `.serena/` に保存される project memory と onboarding state もローカルの runtime state とし、このリポジトリでは管理・検証しません。
