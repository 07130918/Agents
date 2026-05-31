#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"

diff -ru -x 'tp-*.md' "${HOME_DIR}/.agents/references" "${ROOT}/shared/references" || true
diff -ru -x 'tp-*' "${HOME_DIR}/.agents/skills" "${ROOT}/codex/skills" || true
diff -ru -x 'tp-*.toml' "${HOME_DIR}/.codex/agents" "${ROOT}/codex/agents" || true
diff -u "${HOME_DIR}/.codex/AGENTS.md" "${ROOT}/codex/AGENTS.md" || true
diff -u "${HOME_DIR}/.codex/hooks.json" "${ROOT}/codex/hooks.json" || true
diff -ru -x 'tp-*' "${HOME_DIR}/.claude/skills" "${ROOT}/claude/skills" || true
diff -ru -x 'tp-*.md' "${HOME_DIR}/.claude/agents" "${ROOT}/claude/agents" || true
diff -u "${HOME_DIR}/.claude/CLAUDE.md" "${ROOT}/claude/CLAUDE.md" || true
