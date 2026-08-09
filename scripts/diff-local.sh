#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_CONFIG_ROOT="${AGENTS_LOCAL_CONFIG_ROOT:-${HOME}}"

diff -ru -x 'tp-*.md' "${LOCAL_CONFIG_ROOT}/.agents/references" "${ROOT}/shared/references" || true
diff -ru -x 'tp-*' "${LOCAL_CONFIG_ROOT}/.agents/skills" "${ROOT}/codex/skills" || true
diff -ru -x 'tp-*.toml' "${LOCAL_CONFIG_ROOT}/.codex/agents" "${ROOT}/codex/agents" || true
diff -u "${LOCAL_CONFIG_ROOT}/.codex/AGENTS.md" "${ROOT}/codex/AGENTS.md" || true
diff -u "${LOCAL_CONFIG_ROOT}/.codex/hooks.json" "${ROOT}/codex/hooks.json" || true
diff -ru -x 'tp-*' "${LOCAL_CONFIG_ROOT}/.claude/skills" "${ROOT}/claude/skills" || true
if [ -e "${LOCAL_CONFIG_ROOT}/.claude/agents" ] || [ -L "${LOCAL_CONFIG_ROOT}/.claude/agents" ]; then
  echo "Claude Code agents are still active at ${LOCAL_CONFIG_ROOT}/.claude/agents"
fi
diff -ru -x 'tp-*' "${LOCAL_CONFIG_ROOT}/.claude/skills.disabled" "${ROOT}/claude/skills.disabled" || true
diff -ru -x 'tp-*.md' "${LOCAL_CONFIG_ROOT}/.claude/agents.disabled" "${ROOT}/claude/agents.disabled" || true
diff -u "${LOCAL_CONFIG_ROOT}/.claude/CLAUDE.md" "${ROOT}/claude/CLAUDE.md" || true
