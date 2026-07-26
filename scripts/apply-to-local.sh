#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"

disable_claude_directory() {
  local configuration_name="$1"
  local active_path="${HOME_DIR}/.claude/${configuration_name}"
  local disabled_path="${HOME_DIR}/.claude/${configuration_name}.disabled"

  mkdir -p "${disabled_path}"

  if [ -L "${active_path}" ] || { [ -e "${active_path}" ] && [ ! -d "${active_path}" ]; }; then
    echo "Cannot disable Claude Code ${configuration_name} because ${active_path} is not a regular directory." >&2
    exit 1
  fi

  if [ -d "${active_path}" ]; then
    rsync -a --remove-source-files "${active_path}/" "${disabled_path}/"
    find "${active_path}" -depth -type d -empty -delete
  fi

  if [ -e "${active_path}" ]; then
    echo "Could not move every Claude Code ${configuration_name} entry into ${disabled_path}." >&2
    exit 1
  fi
}

mkdir -p "${HOME_DIR}/.agents/references" "${HOME_DIR}/.agents/skills"
mkdir -p "${HOME_DIR}/.codex/agents" "${HOME_DIR}/.claude"

disable_claude_directory "skills"
disable_claude_directory "agents"

rsync -a --delete --exclude 'tp-*.md' "${ROOT}/shared/references/" "${HOME_DIR}/.agents/references/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/codex/skills/" "${HOME_DIR}/.agents/skills/"
rsync -a --delete --exclude 'tp-*.toml' "${ROOT}/codex/agents/" "${HOME_DIR}/.codex/agents/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/claude/skills.disabled/" "${HOME_DIR}/.claude/skills.disabled/"
rsync -a --delete --exclude 'tp-*.md' "${ROOT}/claude/agents.disabled/" "${HOME_DIR}/.claude/agents.disabled/"

cp "${ROOT}/codex/AGENTS.md" "${HOME_DIR}/.codex/AGENTS.md"
cp "${ROOT}/codex/hooks.json" "${HOME_DIR}/.codex/hooks.json"
cp "${ROOT}/claude/CLAUDE.md" "${HOME_DIR}/.claude/CLAUDE.md"

echo "Applied ${ROOT} into local global AI settings"
