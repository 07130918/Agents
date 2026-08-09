#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_GLOBAL="${ROOT}/codex/AGENTS.md"
CLAUDE_GLOBAL="${ROOT}/claude/CLAUDE.md"
CREATE_PR_REFERENCE="${ROOT}/shared/references/create-pr.md"
ISSUE_TO_PR_REFERENCE="${ROOT}/shared/references/issue-to-pr.md"

if ! cmp -s "${CODEX_GLOBAL}" "${CLAUDE_GLOBAL}"; then
  echo "CodexとClaude Codeのglobal指示は同一内容である必要があります。" >&2
  exit 1
fi

for global_file in "${CODEX_GLOBAL}" "${CLAUDE_GLOBAL}"; do
  if [ "$(wc -l <"${global_file}")" -ge 200 ]; then
    echo "Global指示は200行未満である必要があります: ${global_file}" >&2
    exit 1
  fi
done

if grep -nE '確信が持てるまで|抜け穴を探す' \
  "${CODEX_GLOBAL}" "${CLAUDE_GLOBAL}" "${ISSUE_TO_PR_REFERENCE}"; then
  echo "観測できない完了条件が残っています。" >&2
  exit 1
fi

if grep -nE '^## (GitHub PR|コミットメッセージ|バグ調査)$' "${CODEX_GLOBAL}"; then
  echo "複数stepのworkflowをglobal指示へ重複定義しないでください。" >&2
  exit 1
fi

for skill_name in \
  issue-to-pr \
  bug-investigation \
  create-pr \
  git-worktree-ops \
  sync-docs-code \
  principle-of-programming-reviewer; do
  route_pattern="$(printf '`%s`' "${skill_name}")"
  if ! grep -Fq "${route_pattern}" "${CODEX_GLOBAL}"; then
    echo "Workflow索引にskillがありません: ${skill_name}" >&2
    exit 1
  fi

  if [ ! -f "${ROOT}/shared/references/${skill_name}.md" ]; then
    echo "Workflow索引のreferenceが存在しません: ${skill_name}" >&2
    exit 1
  fi
done

for required_text in \
  '07130918' \
  'git add <path>' \
  'git diff --cached' \
  'lint、format、型check、test' \
  'sync-docs-code' \
  'assignee' \
  'label'; do
  if ! grep -Fq "${required_text}" "${CREATE_PR_REFERENCE}"; then
    echo "create-prに移管すべき契約がありません: ${required_text}" >&2
    exit 1
  fi
done

if ! grep -Fq '必須gateの失敗または未解決のblockerが残る場合は、PR作成へ進まない' "${ISSUE_TO_PR_REFERENCE}"; then
  echo "issue-to-prに観測可能な停止条件がありません。" >&2
  exit 1
fi

echo "Global指示の回帰testに成功しました。"
