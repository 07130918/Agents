#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"

for configuration_name in skills agents; do
  if [ -e "${HOME_DIR}/.claude/${configuration_name}" ] || [ -L "${HOME_DIR}/.claude/${configuration_name}" ]; then
    echo "Claude Code ${configuration_name} must be moved to ~/.claude/${configuration_name}.disabled before syncing." >&2
    exit 1
  fi

  if [ ! -d "${HOME_DIR}/.claude/${configuration_name}.disabled" ]; then
    echo "Claude Code disabled directory not found: ~/.claude/${configuration_name}.disabled" >&2
    exit 1
  fi
done

rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${HOME_DIR}/.agents/references/" "${ROOT}/shared/references/"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${HOME_DIR}/.agents/skills/" "${ROOT}/codex/skills/"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${HOME_DIR}/.claude/skills.disabled/" "${ROOT}/claude/skills.disabled/"
rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${HOME_DIR}/.claude/agents.disabled/" "${ROOT}/claude/agents.disabled/"

mkdir -p "${ROOT}/codex/agents"
rsync -a --delete --delete-excluded --exclude 'tp-*.toml' "${HOME_DIR}/.codex/agents/" "${ROOT}/codex/agents/"

cp "${HOME_DIR}/.codex/AGENTS.md" "${ROOT}/codex/AGENTS.md"
cp "${HOME_DIR}/.codex/hooks.json" "${ROOT}/codex/hooks.json"
cp "${HOME_DIR}/.claude/CLAUDE.md" "${ROOT}/claude/CLAUDE.md"

"${ROOT}/scripts/validate.sh"

echo "Synced local global AI settings into ${ROOT}"
