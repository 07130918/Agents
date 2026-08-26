#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -L "${ROOT}/claude/skills" ] || [ ! -d "${ROOT}/claude/skills" ]; then
  echo "Missing or invalid Claude Code active skills directory: claude/skills." >&2
  exit 1
fi

if [ -e "${ROOT}/claude/agents" ] || [ -L "${ROOT}/claude/agents" ]; then
  echo "Claude Code agents must remain disabled under claude/agents.disabled." >&2
  exit 1
fi

for configuration_name in skills agents; do
  if [ ! -d "${ROOT}/claude/${configuration_name}.disabled" ]; then
    echo "Missing Claude Code disabled directory: claude/${configuration_name}.disabled" >&2
    exit 1
  fi
done

for active_skill in "${ROOT}"/claude/skills/*; do
  [ -d "${active_skill}" ] || continue
  skill_name="$(basename "${active_skill}")"
  if [ -e "${ROOT}/claude/skills.disabled/${skill_name}" ]; then
    echo "Claude Code skill cannot be both active and disabled: ${skill_name}" >&2
    exit 1
  fi
done

private_matches="$(
  find "${ROOT}/codex/skills" "${ROOT}/claude/skills" "${ROOT}/claude/skills.disabled" -maxdepth 1 -type d -name 'tp-*' -print
  find "${ROOT}/codex/agents" -maxdepth 1 -type f -name 'tp-*.toml' -print
  find "${ROOT}/claude/agents.disabled" -maxdepth 1 -type f -name 'tp-*.md' -print
  find "${ROOT}/shared/references" -maxdepth 1 -type f -name 'tp-*.md' -print
)"

if [ -n "${private_matches}" ]; then
  echo "Private tp-* skills/agents/references must not be committed:" >&2
  echo "${private_matches}" >&2
  exit 1
fi

if grep -RInE --exclude='validate.sh' --exclude-dir=.git --exclude-dir=.serena \
  '(^|[^[:alnum:]_])sk-[A-Za-z0-9_-]+|figd_|GITHUB_PERSONAL_ACCESS_TOKEN|BEGIN OPENSSH PRIVATE KEY|BEGIN RSA PRIVATE KEY' \
  "${ROOT}"; then
  echo "Potential secret found. Review before committing." >&2
  exit 1
fi

if grep -RInE --exclude='validate.sh' --exclude-dir=.git --exclude-dir=.serena '（|）' "${ROOT}"; then
  echo "Full-width parentheses found." >&2
  exit 1
fi

if ! command -v ruby >/dev/null 2>&1; then
  echo "ruby is required to validate SKILL.md YAML frontmatter." >&2
  exit 1
fi

find "${ROOT}/codex/skills" "${ROOT}/claude/skills" "${ROOT}/claude/skills.disabled" -path '*/SKILL.md' -type f -print | while read -r file; do
  ruby -ryaml -e '
    file = ARGV.fetch(0)
    content = File.read(file)
    match = content.match(/\A---\n(.*?)\n---/m)
    abort("Missing YAML frontmatter: #{file}") unless match
    YAML.safe_load(match[1], permitted_classes: [], aliases: false)
  ' "$file" || {
    echo "Invalid YAML frontmatter: $file" >&2
    exit 1
  }
  grep -q '^name:' "$file" || { echo "Missing name: $file" >&2; exit 1; }
  grep -q '^description:' "$file" || { echo "Missing description: $file" >&2; exit 1; }
done

"${ROOT}/scripts/principle-of-programming-reviewer.test.sh"

echo "Validation passed."
