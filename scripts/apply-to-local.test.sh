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
mkdir -p "${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs"
printf '%s\n' 'legacy duplicated format' >"${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/CONTEXT-FORMAT.md"
printf '%s\n' 'legacy duplicated format' >"${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/ADR-FORMAT.md"

AGENTS_LOCAL_CONFIG_ROOT="${TEST_CONFIG_ROOT}" "${ROOT}/scripts/apply-to-local.sh" >/dev/null

if [ ! -f "${TEST_CONFIG_ROOT}/.agents/references/grilling.md" ]; then
  echo "Shared grilling reference must be applied to local settings." >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/pyproject.toml" ] ||
  [ ! -f "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/uv.lock" ] ||
  [ ! -f "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/src/review_harness_artifacts/cli.py" ]; then
  echo "Review Harness artifact tool must be applied with its locked environment." >&2
  exit 1
fi

for runtime_cache in .venv .pytest_cache .ruff_cache .mypy_cache __pycache__; do
  if [ -e "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/${runtime_cache}" ]; then
    echo "Python runtime cache must not be applied: ${runtime_cache}" >&2
    exit 1
  fi
done

if [ ! -f "${TEST_CONFIG_ROOT}/.agents/references/grill-with-docs-context-format.md" ] ||
  [ ! -f "${TEST_CONFIG_ROOT}/.agents/references/grill-with-docs-adr-format.md" ]; then
  echo "Shared grill-with-docs formats must be applied to local settings." >&2
  exit 1
fi

if ! grep -q '^  allow_implicit_invocation: false$' "${TEST_CONFIG_ROOT}/.agents/skills/grill-me/agents/openai.yaml" ||
  ! grep -q '^  allow_implicit_invocation: false$' "${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/agents/openai.yaml"; then
  echo "Grilling skills must remain manual-only after applying local settings." >&2
  exit 1
fi

if [ -e "${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/CONTEXT-FORMAT.md" ] ||
  [ -e "${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/ADR-FORMAT.md" ]; then
  echo "Grill-with-docs formats must not be duplicated under the skill wrapper." >&2
  exit 1
fi

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
