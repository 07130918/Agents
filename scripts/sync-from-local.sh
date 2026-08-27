#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_CONFIG_ROOT="${AGENTS_LOCAL_CONFIG_ROOT:-${HOME}}"

if [ -L "${LOCAL_CONFIG_ROOT}/.claude/skills" ] || [ ! -d "${LOCAL_CONFIG_ROOT}/.claude/skills" ]; then
  echo "Claude Code active skills directory not found or invalid: ~/.claude/skills" >&2
  exit 1
fi

if [ -e "${LOCAL_CONFIG_ROOT}/.claude/agents" ] || [ -L "${LOCAL_CONFIG_ROOT}/.claude/agents" ]; then
  echo "Claude Code agents must be moved to ~/.claude/agents.disabled before syncing." >&2
  exit 1
fi

for configuration_name in skills agents; do
  if [ ! -d "${LOCAL_CONFIG_ROOT}/.claude/${configuration_name}.disabled" ]; then
    echo "Claude Code disabled directory not found: ~/.claude/${configuration_name}.disabled" >&2
    exit 1
  fi
done

rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${LOCAL_CONFIG_ROOT}/.agents/references/" "${ROOT}/shared/references/"
rsync -a --delete --delete-excluded \
  --exclude 'tp-*' \
  --exclude '__pycache__/' \
  --exclude '*.py[cod]' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '.mypy_cache/' \
  "${LOCAL_CONFIG_ROOT}/.agents/skills/" "${ROOT}/codex/skills/"
mkdir -p "${ROOT}/claude/skills"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${LOCAL_CONFIG_ROOT}/.claude/skills/" "${ROOT}/claude/skills/"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${LOCAL_CONFIG_ROOT}/.claude/skills.disabled/" "${ROOT}/claude/skills.disabled/"
rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${LOCAL_CONFIG_ROOT}/.claude/agents.disabled/" "${ROOT}/claude/agents.disabled/"

mkdir -p "${ROOT}/codex/agents"
rsync -a --delete --delete-excluded --exclude 'tp-*.toml' "${LOCAL_CONFIG_ROOT}/.codex/agents/" "${ROOT}/codex/agents/"

cp "${LOCAL_CONFIG_ROOT}/.codex/AGENTS.md" "${ROOT}/codex/AGENTS.md"
cp "${LOCAL_CONFIG_ROOT}/.codex/hooks.json" "${ROOT}/codex/hooks.json"
cp "${LOCAL_CONFIG_ROOT}/.claude/CLAUDE.md" "${ROOT}/claude/CLAUDE.md"

"${ROOT}/scripts/validate.sh"

echo "Synced local global AI settings into ${ROOT}"
