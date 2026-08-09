#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
TEST_CONFIG_ROOT="${TEST_ROOT}/home"

cleanup() {
  rm -rf "${TEST_ROOT}"
}
trap cleanup EXIT

mkdir -p "${TEST_CONFIG_ROOT}/.claude/skills/tp-local-test"
printf '%s\n' 'local private skill' >"${TEST_CONFIG_ROOT}/.claude/skills/tp-local-test/SKILL.md"
mkdir -p "${TEST_CONFIG_ROOT}/.claude/skills/legacy-active"
printf '%s\n' 'legacy active skill' >"${TEST_CONFIG_ROOT}/.claude/skills/legacy-active/SKILL.md"
mkdir -p "${TEST_CONFIG_ROOT}/.claude/agents"
printf '%s\n' 'local private subagent' >"${TEST_CONFIG_ROOT}/.claude/agents/tp-local-test.md"

AGENTS_LOCAL_CONFIG_ROOT="${TEST_CONFIG_ROOT}" "${ROOT}/scripts/apply-to-local.sh" >/dev/null

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills/visualize-architecture-flow/SKILL.md" ]; then
  echo "Managed active Claude Code skills must be copied into skills." >&2
  exit 1
fi

if [ -e "${TEST_CONFIG_ROOT}/.claude/skills/legacy-active" ]; then
  echo "Unmanaged active Claude Code skills must be removed." >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills/tp-local-test/SKILL.md" ]; then
  echo "Local tp-* skills must remain available in active skills." >&2
  exit 1
fi

if [ -e "${TEST_CONFIG_ROOT}/.claude/agents" ]; then
  echo "Active Claude Code agents directory must be removed." >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills.disabled/create-pr/SKILL.md" ]; then
  echo "Managed Claude Code skills must be copied into skills.disabled." >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/agents.disabled/serena-dev.md" ]; then
  echo "Managed Claude Code agents must be copied into agents.disabled." >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/agents.disabled/tp-local-test.md" ]; then
  echo "Local tp-* agents must remain available in agents.disabled." >&2
  exit 1
fi

if ! diff -ru -x 'tp-*' "${ROOT}/claude/skills" "${TEST_CONFIG_ROOT}/.claude/skills" >/dev/null; then
  echo "Applied Claude Code active skills differ from the repository." >&2
  exit 1
fi

if ! diff -ru -x 'tp-*' "${ROOT}/claude/skills.disabled" "${TEST_CONFIG_ROOT}/.claude/skills.disabled" >/dev/null; then
  echo "Applied Claude Code disabled skills differ from the repository." >&2
  exit 1
fi

if ! diff -ru -x 'tp-*.md' "${ROOT}/claude/agents.disabled" "${TEST_CONFIG_ROOT}/.claude/agents.disabled" >/dev/null; then
  echo "Applied Claude Code disabled agents differ from the repository." >&2
  exit 1
fi

echo "Apply-to-local regression tests passed."
