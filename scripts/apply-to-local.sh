#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_CONFIG_ROOT="${AGENTS_LOCAL_CONFIG_ROOT:-${HOME}}"

disable_claude_directory() {
  local configuration_name="$1"
  local active_path="${LOCAL_CONFIG_ROOT}/.claude/${configuration_name}"
  local disabled_path="${LOCAL_CONFIG_ROOT}/.claude/${configuration_name}.disabled"

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

mkdir -p "${LOCAL_CONFIG_ROOT}/.agents/references" "${LOCAL_CONFIG_ROOT}/.agents/skills"
mkdir -p "${LOCAL_CONFIG_ROOT}/.codex/agents" "${LOCAL_CONFIG_ROOT}/.claude/skills"

disable_claude_directory "agents"

rsync -a --delete --exclude 'tp-*.md' "${ROOT}/shared/references/" "${LOCAL_CONFIG_ROOT}/.agents/references/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/codex/skills/" "${LOCAL_CONFIG_ROOT}/.agents/skills/"
rsync -a --delete --exclude 'tp-*.toml' "${ROOT}/codex/agents/" "${LOCAL_CONFIG_ROOT}/.codex/agents/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/claude/skills/" "${LOCAL_CONFIG_ROOT}/.claude/skills/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/claude/skills.disabled/" "${LOCAL_CONFIG_ROOT}/.claude/skills.disabled/"
rsync -a --delete --exclude 'tp-*.md' "${ROOT}/claude/agents.disabled/" "${LOCAL_CONFIG_ROOT}/.claude/agents.disabled/"

cp "${ROOT}/codex/AGENTS.md" "${LOCAL_CONFIG_ROOT}/.codex/AGENTS.md"
cp "${ROOT}/codex/hooks.json" "${LOCAL_CONFIG_ROOT}/.codex/hooks.json"
cp "${ROOT}/claude/CLAUDE.md" "${LOCAL_CONFIG_ROOT}/.claude/CLAUDE.md"

echo "Applied ${ROOT} into local global AI settings"
