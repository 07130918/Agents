#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
TEST_HOME="${TEST_ROOT}/home"

cleanup() {
  rm -rf "${TEST_ROOT}"
}
trap cleanup EXIT

mkdir -p "${TEST_HOME}/.claude/skills/tp-local-test"
printf '%s\n' 'local private skill' >"${TEST_HOME}/.claude/skills/tp-local-test/SKILL.md"
mkdir -p "${TEST_HOME}/.claude/agents"
printf '%s\n' 'local private subagent' >"${TEST_HOME}/.claude/agents/tp-local-test.md"

HOME="${TEST_HOME}" "${ROOT}/scripts/apply-to-local.sh" >/dev/null

if [ -e "${TEST_HOME}/.claude/skills" ]; then
  echo "Active Claude Code skills directory must be removed." >&2
  exit 1
fi

if [ -e "${TEST_HOME}/.claude/agents" ]; then
  echo "Active Claude Code agents directory must be removed." >&2
  exit 1
fi

if [ ! -f "${TEST_HOME}/.claude/skills.disabled/create-pr/SKILL.md" ]; then
  echo "Managed Claude Code skills must be copied into skills.disabled." >&2
  exit 1
fi

if [ ! -f "${TEST_HOME}/.claude/agents.disabled/serena-dev.md" ]; then
  echo "Managed Claude Code agents must be copied into agents.disabled." >&2
  exit 1
fi

if [ ! -f "${TEST_HOME}/.claude/skills.disabled/tp-local-test/SKILL.md" ]; then
  echo "Local tp-* skills must remain available in skills.disabled." >&2
  exit 1
fi

if [ ! -f "${TEST_HOME}/.claude/agents.disabled/tp-local-test.md" ]; then
  echo "Local tp-* agents must remain available in agents.disabled." >&2
  exit 1
fi

if ! diff -ru -x 'tp-*' "${ROOT}/claude/skills.disabled" "${TEST_HOME}/.claude/skills.disabled" >/dev/null; then
  echo "Applied Claude Code disabled skills differ from the repository." >&2
  exit 1
fi

if ! diff -ru -x 'tp-*.md' "${ROOT}/claude/agents.disabled" "${TEST_HOME}/.claude/agents.disabled" >/dev/null; then
  echo "Applied Claude Code disabled agents differ from the repository." >&2
  exit 1
fi

echo "Apply-to-local regression tests passed."
