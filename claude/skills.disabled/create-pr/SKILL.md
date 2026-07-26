---
name: create-pr
description: 作業ブランチの差分を確認してプルリクエストを作成。ブランチ名のプレフィックス([数字])を自動抽出してPRテンプレートに基づきタイトル・本文を日本語で生成する。`/create-pr` で呼び出される。
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(gh *), Read
---

# create-pr

この skill の詳細手順は `~/.agents/references/create-pr.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
