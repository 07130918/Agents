#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
TEST_REPOSITORY="${TEST_ROOT}/repository"
TEST_CONFIG_ROOT="${TEST_ROOT}/home"

cleanup() {
  rm -rf "${TEST_ROOT}"
}
trap cleanup EXIT

mkdir -p "${TEST_REPOSITORY}"
rsync -a --exclude '.git' "${ROOT}/" "${TEST_REPOSITORY}/"

AGENTS_LOCAL_CONFIG_ROOT="${TEST_CONFIG_ROOT}" "${TEST_REPOSITORY}/scripts/apply-to-local.sh" >/dev/null

mkdir -p "${TEST_CONFIG_ROOT}/.claude/skills/sync-probe"
printf '%s\n' \
  '---' \
  'name: sync-probe' \
  'description: Claude Code active skillの同期テスト。' \
  '---' \
  '' \
  '# sync-probe' \
  >"${TEST_CONFIG_ROOT}/.claude/skills/sync-probe/SKILL.md"

mkdir -p "${TEST_CONFIG_ROOT}/.claude/skills/tp-sync-probe"
printf '%s\n' 'local private skill' >"${TEST_CONFIG_ROOT}/.claude/skills/tp-sync-probe/SKILL.md"

mkdir -p "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/__pycache__"
printf '%s\n' 'runtime cache' \
  >"${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/__pycache__/probe.pyc"
for runtime_cache in .venv .pytest_cache .ruff_cache .mypy_cache; do
  mkdir -p "${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/${runtime_cache}"
  printf '%s\n' 'runtime cache' \
    >"${TEST_CONFIG_ROOT}/.agents/skills/review-remediation-harness/${runtime_cache}/probe"
done

AGENTS_LOCAL_CONFIG_ROOT="${TEST_CONFIG_ROOT}" "${TEST_REPOSITORY}/scripts/sync-from-local.sh" >/dev/null

if [ ! -f "${TEST_REPOSITORY}/codex/skills/review-remediation-harness/pyproject.toml" ] ||
  [ ! -f "${TEST_REPOSITORY}/codex/skills/review-remediation-harness/uv.lock" ] ||
  [ ! -f "${TEST_REPOSITORY}/codex/skills/review-remediation-harness/src/review_harness_artifacts/cli.py" ]; then
  echo "Review Harness artifact tool must survive the local round trip." >&2
  exit 1
fi

for runtime_cache in .venv .pytest_cache .ruff_cache .mypy_cache __pycache__; do
  if [ -e "${TEST_REPOSITORY}/codex/skills/review-remediation-harness/${runtime_cache}" ]; then
    echo "Python runtime cache must not be synced: ${runtime_cache}" >&2
    exit 1
  fi
done

if [ ! -f "${TEST_REPOSITORY}/claude/skills/sync-probe/SKILL.md" ]; then
  echo "Active Claude Code skill must be synced into the repository." >&2
  exit 1
fi

if [ -e "${TEST_REPOSITORY}/claude/skills/tp-sync-probe" ]; then
  echo "Local tp-* skill must not be synced into the repository." >&2
  exit 1
fi

if [ ! -f "${TEST_REPOSITORY}/claude/skills/visualize-architecture-flow/SKILL.md" ]; then
  echo "Existing active Claude Code skill must remain in the repository." >&2
  exit 1
fi

echo "Sync-from-local regression tests passed."
