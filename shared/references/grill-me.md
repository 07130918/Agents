# Grill Me

リポジトリや成果物を残さず、計画、設計、意思決定、アイデアを会話で研ぐ軽量版。

ユーザが `grill-me` を明示的に選択した場合だけ開始する。

## 必須reference

最初の質問を出す前に `~/.agents/references/grilling.md` を最後まで読み、その設計ツリー、質問、終了条件に従う。

## 使う場面

- softwareに限らず、product、business、writing、個人の意思決定にも使える。
- まだ精密な計画になっていないideaを対象にできる。計画を先に作る必要はない。
- リポジトリ内の用語やADRを更新しながら進める必要がある場合は `grill-with-docs` を使う。

## セッションの制約

- statelessに進め、workspaceへファイルを書かない。
- 事実確認に必要ならコードや既存ドキュメントを読み取ってよいが、コードベースの存在を前提にしない。
- 計画を早く出力することを目的にせず、共通理解へ到達するまでinquiryを続ける。
- 終了時の決定と保留事項は会話内に残し、同じtaskのまま次のworkflowへ引き継ぐ。

## 関連 skill

- ドメイン用語集 (`CONTEXT.md`) や `docs/adr/` を意識した本格版: `grill-with-docs`
- バグ調査の文脈で同じ規律を使うなら: `bug-investigation` の Step 4 (3-5 個のランク付け仮説 + ファルシファイア)
- アーキテクチャ改善の grilling: `software-architecture` のワークフロー Step 3
