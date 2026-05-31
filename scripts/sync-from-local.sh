#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="${HOME}"

rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${HOME_DIR}/.agents/references/" "${ROOT}/shared/references/"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${HOME_DIR}/.agents/skills/" "${ROOT}/codex/skills/"
rsync -a --delete --delete-excluded --exclude 'tp-*' "${HOME_DIR}/.claude/skills/" "${ROOT}/claude/skills/"
rsync -a --delete --delete-excluded --exclude 'tp-*.md' "${HOME_DIR}/.claude/agents/" "${ROOT}/claude/agents/"

mkdir -p "${ROOT}/codex/agents"
rsync -a --delete --delete-excluded --exclude 'tp-*.toml' "${HOME_DIR}/.codex/agents/" "${ROOT}/codex/agents/"

cp "${HOME_DIR}/.codex/AGENTS.md" "${ROOT}/codex/AGENTS.md"
cp "${HOME_DIR}/.codex/hooks.json" "${ROOT}/codex/hooks.json"
cp "${HOME_DIR}/.claude/CLAUDE.md" "${ROOT}/claude/CLAUDE.md"

find "${ROOT}/shared/references" "${ROOT}/codex" "${ROOT}/claude" \
  -type f \( -name '*.md' -o -name '*.toml' -o -name '*.json' \) \
  -exec perl -CS -0pi -e 's/\x{ff08}/(/g; s/\x{ff09}/)/g' {} +

echo "Synced local global AI settings into ${ROOT}"
