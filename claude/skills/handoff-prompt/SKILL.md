---
name: handoff-prompt
description: 次の Codex/Claude セッションが迷わず再開できる handoff prompt を生成する。現在の作業ディレクトリを検査し、git 状態、PR 状態、未完了タスク、検証結果、起動中サービス、注意点を次セッションへ貼れる Markdown として出力する。「引き継ぎ」「handoff」「次セッションに渡す」「引き継ぎ用に作業まとめて」などで使う。設定へ恒久的な学びを反映する場合は session-retrospective、新規 skill 作成は create-skill を使う。
argument-hint: [current-session | branch | pr-number]
allowed-tools: Read Write Edit Glob Grep Bash(git *) Bash(gh *) Bash(docker *) Bash(find *) Bash(test *) Bash(pwd) Bash(wc *)
---

# handoff-prompt

この skill の詳細手順は `~/.agents/references/handoff-prompt.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
