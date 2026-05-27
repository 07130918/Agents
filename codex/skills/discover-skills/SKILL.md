---
name: discover-skills
description: セッションパターンを分析して不足している skills・agents を発見し追加実装する。過去30日のセッションログから技術スタック・タスク種別・エラーパターンを抽出し、頻出するのに未整備のワークフローを特定して新規 skill/agent として生成する。`/discover-skills` で呼び出される。既存設定ファイルの監査・リファクタは `audit-codex-config` を使う。
disable-model-invocation: true
allowed-tools: Read Write Edit Glob Grep Bash(find *) Bash(wc *)
---

# discover-skills

この skill の詳細手順は `~/.agents/references/discover-skills.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
