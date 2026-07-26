---
name: create-skill
description: Codex と Claude Code の両方で使える skill を作成・更新する。共通 reference + CLI 別 SKILL.md wrapper 構成、frontmatter 設計、発火条件、supporting files、検証まで行う。「skillを作って」「手順をskill化」「Claude/Codex両対応」と言われたときに使う。
argument-hint: skill-name [scope]
allowed-tools: Read Write Edit Glob Grep Bash(find *) Bash(wc *) Bash(mkdir *)
---

# create-skill

この skill の詳細手順は `~/.agents/references/create-skill.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
