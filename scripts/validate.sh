#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if grep -RInE --exclude='validate.sh' --exclude-dir=.git \
  'sk-[A-Za-z0-9_-]+|sk-proj-|figd_|GITHUB_PERSONAL_ACCESS_TOKEN|BEGIN OPENSSH PRIVATE KEY|BEGIN RSA PRIVATE KEY' \
  "${ROOT}"; then
  echo "Potential secret found. Review before committing." >&2
  exit 1
fi

if grep -RInE --exclude='validate.sh' --exclude-dir=.git '（|）' "${ROOT}"; then
  echo "Full-width parentheses found." >&2
  exit 1
fi

find "${ROOT}/codex/skills" "${ROOT}/claude/skills" -path '*/SKILL.md' -type f -print | while read -r file; do
  grep -q '^name:' "$file" || { echo "Missing name: $file" >&2; exit 1; }
  grep -q '^description:' "$file" || { echo "Missing description: $file" >&2; exit 1; }
done

echo "Validation passed."
