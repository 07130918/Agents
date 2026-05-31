#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"

mkdir -p "${HOME_DIR}/.agents/references" "${HOME_DIR}/.agents/skills"
mkdir -p "${HOME_DIR}/.codex/agents" "${HOME_DIR}/.claude/skills" "${HOME_DIR}/.claude/agents"

rsync -a --delete --exclude 'tp-*.md' "${ROOT}/shared/references/" "${HOME_DIR}/.agents/references/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/codex/skills/" "${HOME_DIR}/.agents/skills/"
rsync -a --delete --exclude 'tp-*.toml' "${ROOT}/codex/agents/" "${HOME_DIR}/.codex/agents/"
rsync -a --delete --exclude 'tp-*' "${ROOT}/claude/skills/" "${HOME_DIR}/.claude/skills/"
rsync -a --delete --exclude 'tp-*.md' "${ROOT}/claude/agents/" "${HOME_DIR}/.claude/agents/"

cp "${ROOT}/codex/AGENTS.md" "${HOME_DIR}/.codex/AGENTS.md"
cp "${ROOT}/codex/hooks.json" "${HOME_DIR}/.codex/hooks.json"
cp "${ROOT}/claude/CLAUDE.md" "${HOME_DIR}/.claude/CLAUDE.md"

echo "Applied ${ROOT} into local global AI settings"
