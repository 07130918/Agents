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
mkdir -p "${TEST_CONFIG_ROOT}/.claude/skills.disabled/handoff-prompt"
printf '%s\n' '退避中の引き継ぎスキル' >"${TEST_CONFIG_ROOT}/.claude/skills.disabled/handoff-prompt/SKILL.md"
mkdir -p "${TEST_CONFIG_ROOT}/.claude/agents"
printf '%s\n' 'local private subagent' >"${TEST_CONFIG_ROOT}/.claude/agents/tp-local-test.md"
mkdir -p "${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs"
printf '%s\n' 'legacy duplicated format' >"${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/CONTEXT-FORMAT.md"
printf '%s\n' 'legacy duplicated format' >"${TEST_CONFIG_ROOT}/.agents/skills/grill-with-docs/ADR-FORMAT.md"

removed_paths=(
  .agents/skills/serena/SKILL.md
  .codex/agents/serena-dev.toml
  .agents/references/serena.md
  .agents/references/serena-dev-agent.md
  .claude/skills.disabled/serena/SKILL.md
  .claude/agents.disabled/serena-dev.md
)
for skill_name in testing-patterns software-architecture prompt-engineering nextjs-prisma-patterns; do
  removed_paths+=(
    ".agents/skills/${skill_name}/SKILL.md"
    ".claude/skills.disabled/${skill_name}/SKILL.md"
    ".agents/references/${skill_name}.md"
  )
done
for removed_path in "${removed_paths[@]}"; do
  mkdir -p "$(dirname "${TEST_CONFIG_ROOT}/${removed_path}")"
  printf '%s\n' '廃止済みの定義' >"${TEST_CONFIG_ROOT}/${removed_path}"
done
printf '%s\n' '[mcp_servers.serena]' 'command = "serena"' >"${TEST_ROOT}/mcp-config.toml"
cp "${TEST_ROOT}/mcp-config.toml" "${TEST_CONFIG_ROOT}/.codex/config.toml"
mkdir -p "${TEST_CONFIG_ROOT}/.gemini/config"
printf '%s\n' '{"mcpServers":{"local-only":{"command":"echo"}}}' >"${TEST_ROOT}/gemini-mcp-config.json"
cp "${TEST_ROOT}/gemini-mcp-config.json" "${TEST_CONFIG_ROOT}/.gemini/config/mcp_config.json"

AGENTS_LOCAL_CONFIG_ROOT="${TEST_CONFIG_ROOT}" "${ROOT}/scripts/apply-to-local.sh" >/dev/null

for removed_path in "${removed_paths[@]}"; do
  if [ -e "${TEST_CONFIG_ROOT}/${removed_path}" ]; then
    echo "廃止済みの定義が残っています: ${removed_path}" >&2
    exit 1
  fi
done
if ! cmp -s "${TEST_ROOT}/mcp-config.toml" "${TEST_CONFIG_ROOT}/.codex/config.toml"; then
  echo "Serena MCPの接続設定は変更せず保持してください。" >&2
  exit 1
fi
if ! cmp -s "${TEST_ROOT}/gemini-mcp-config.json" "${TEST_CONFIG_ROOT}/.gemini/config/mcp_config.json"; then
  echo "Gemini MCPのローカル設定は変更せず保持してください。" >&2
  exit 1
fi

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

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills/handoff-prompt/SKILL.md" ] ||
  [ -e "${TEST_CONFIG_ROOT}/.claude/skills.disabled/handoff-prompt" ] ||
  [ ! -f "${TEST_CONFIG_ROOT}/.agents/references/handoff-prompt.md" ]; then
  echo "引き継ぎスキルを退避先から有効な配置に切り替え、共通手順を同期してください。" >&2
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

for skill_name in create-pr bug-investigation sync-docs-code issue-to-pr review-remediation-harness; do
  if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills/${skill_name}/SKILL.md" ] ||
    [ -e "${TEST_CONFIG_ROOT}/.claude/skills.disabled/${skill_name}" ] ||
    [ ! -f "${TEST_CONFIG_ROOT}/.agents/references/${skill_name}.md" ]; then
    echo "Claude Code の有効なスキルと共通手順を同期してください: ${skill_name}" >&2
    exit 1
  fi
done

create_pr_skill="${TEST_CONFIG_ROOT}/.claude/skills/create-pr/SKILL.md"
if ! grep -qx 'disable-model-invocation: true' "${create_pr_skill}" ||
  grep -q '^allowed-tools:' "${create_pr_skill}"; then
  echo "create-pr は手動呼び出し専用とし、ツールの権限は Claude Code の設定に従ってください。" >&2
  exit 1
fi

if [ ! -f "${TEST_CONFIG_ROOT}/.claude/skills.disabled/codex-review/SKILL.md" ]; then
  echo "Managed Claude Code skills must be copied into skills.disabled." >&2
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

for linked_agents in "${TEST_CONFIG_ROOT}/.codex/AGENTS.md" "${TEST_CONFIG_ROOT}/.gemini/AGENTS.md"; do
  if [ ! -L "${linked_agents}" ] || [ "$(readlink "${linked_agents}")" != "${TEST_CONFIG_ROOT}/.claude/CLAUDE.md" ]; then
    echo "AGENTS.md must be a symlink to ~/.claude/CLAUDE.md: ${linked_agents}" >&2
    exit 1
  fi
done

if ! cmp -s "${ROOT}/gemini/config/skills.json" "${TEST_CONFIG_ROOT}/.gemini/config/skills.json"; then
  echo "Applied Gemini skills.json differs from the repository." >&2
  exit 1
fi

if ! cmp -s "${ROOT}/gemini/config/hooks.json" "${TEST_CONFIG_ROOT}/.gemini/config/hooks.json"; then
  echo "Applied Gemini hooks.json differs from the repository." >&2
  exit 1
fi

gemini_pre_cmd="$(jq -r '.["env-guard"].PreToolUse[0].hooks[0].command' "${TEST_CONFIG_ROOT}/.gemini/config/hooks.json")"
gemini_post_cmd="$(jq -r '.["auto-format"].PostToolUse[0].hooks[0].command' "${TEST_CONFIG_ROOT}/.gemini/config/hooks.json")"
claude_pre_cmd="$(jq -r '.hooks.PreToolUse[0].hooks[0].command' "${ROOT}/claude/settings.example.json")"

if [ "$(printf '%s' '{"toolCall":{"name":"write_file","args":{"Path":"/tmp/app/.env"}}}' | sh -c "${gemini_pre_cmd}" | jq -r '.decision')" != "deny" ]; then
  echo "Gemini env-guard hook must deny .env edits." >&2
  exit 1
fi

if [ "$(printf '%s' '{"toolCall":{"name":"edit_file","args":{"Path":"/tmp/app/.env.local"}}}' | sh -c "${gemini_pre_cmd}" | jq -r '.decision')" != "deny" ]; then
  echo "Gemini env-guard hook must deny .env.local edits." >&2
  exit 1
fi

if [ "$(printf '%s' '{"toolCall":{"name":"write_file","args":{"Path":"/tmp/app/.env.example"}}}' | sh -c "${gemini_pre_cmd}" | jq -r '.decision')" != "allow" ]; then
  echo "Gemini env-guard hook must allow .env.example edits." >&2
  exit 1
fi

if [ "$(printf '%s' '{"toolCall":{"name":"write_file","args":{"Path":"/tmp/app/src/index.ts"}}}' | sh -c "${gemini_pre_cmd}" | jq -r '.decision')" != "allow" ]; then
  echo "Gemini env-guard hook must allow regular file edits." >&2
  exit 1
fi

if [ "$(printf '%s' '{"toolCall":{"name":"write_file","args":{"Path":"/tmp/app/src/nonexistent.ts"}}}' | sh -c "${gemini_post_cmd}")" != "{}" ]; then
  echo "Gemini auto-format hook must return {} on stdout." >&2
  exit 1
fi

set +e
printf '%s' '{"tool_input":{"file_path":"/tmp/app/.env"}}' | sh -c "${claude_pre_cmd}" >/dev/null 2>&1
claude_env_status=$?
printf '%s' '{"tool_input":{"file_path":"/tmp/app/.env.example"}}' | sh -c "${claude_pre_cmd}" >/dev/null 2>&1
claude_example_status=$?
set -e
if [ "${claude_env_status}" -ne 2 ] || [ "${claude_example_status}" -ne 0 ]; then
  echo "Claude Code PreToolUse .env guard did not return expected exit codes." >&2
  exit 1
fi

echo "Apply-to-local regression tests passed."
