---
name: review-remediation-harness
description: |
  独立reviewerを含むreview、修正、検証、fresh Final reviewをexact targetで進行する。
  Use when: user explicitly asks for a review-remediation harness, reviewer/implementer separation across a fix workflow, or a review/fix/verify/re-review loop with an independent final reviewer.
  For Issue URLs, issue-to-pr owns intake and delegates its review/fix/verify subflow here. Does not trigger on: standalone initial/final/review-only requests without remediation, PR creation only, or an ordinary Issue implementation that does not request the Harness.
---

# review-remediation-harness

この skill の詳細手順は `~/.agents/references/review-remediation-harness.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中のCLIに対応する手順・チェックリスト・注意事項に従ってください。
