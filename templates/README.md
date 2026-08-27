# AI エージェント設定テンプレート

新規プロジェクト用の AGENTS.md / CLAUDE.md テンプレート。
約 9 ヶ月分の会話ログ (Claude Code 8,587 + Codex 1,172 プロンプト、Codex 2,201 セッション) と
既存約 30 リポジトリの設定ファイルの分析結果 (2026-07-05) をもとに作成。

## 構成と設計判断

| ファイル | 役割 |
|---|---|
| AGENTS.md | Codex が読むプロジェクト共通指示 (フル内容) |
| CLAUDE.md | Claude Code が読むプロジェクト共通指示 (フル内容) |
| REVIEW_HARNESS.md | Personal skillに依存しないreview-remediation Harnessのentrypoint兼manifest |
| .review-harness/contracts/ | CLI非依存contractのreview済みexact snapshot |

- 2 ファイルは**意図的な対称配置**。冗長になるが、各ツールがネイティブに読むファイルを
  それぞれ完全な形で用意する。ラッパー・@import・symlink は使わない
- テンプレートの本文は 2 ファイルで完全に同一。プロジェクトで運用する中で、ツール固有の行
  (サブエージェント指定など) だけが意図した差分になる
- ドリフト対策: 両ファイル冒頭の「対称管理」ルール + グローバル設定の
  「片方を更新したらもう片方も更新する」ルール + レビュー時に `diff CLAUDE.md AGENTS.md` で乖離確認

## 使い方

```bash
cp ~/Desktop/Agents/templates/AGENTS.md ~/Desktop/Agents/templates/CLAUDE.md <プロジェクトルート>/
```

1. 片方の {{ }} を埋め、該当しないセクションを削除する
2. もう片方へ同じ内容を反映し、ツール固有の行だけ調整する
3. 記入基準はファイル冒頭のコメント参照 (200 行以内 / 「消したらエージェントがミスするか?」テスト)
4. 記入が終わったら説明コメントを削除する

## Portable review Harness

Independent reviewerを含むreview、修正、検証をpersonal skillなしでも実行するprojectでは、entrypointとcontract directoryを必ず同時にコピーする。

```bash
cp ~/Desktop/Agents/templates/REVIEW_HARNESS.md <プロジェクトルート>/
mkdir -p <プロジェクトルート>/.review-harness
cp -R ~/Desktop/Agents/templates/.review-harness/contracts <プロジェクトルート>/.review-harness/
```

実行前に`REVIEW_HARNESS.md`のintegrity手順で全memberのSHA-256を照合する。Snapshotをproject側で直接編集せず、project固有のsource of truth、command、gateは任意の`.review-harness/profile.yaml`へ分離する。Profileがなくてもrepository情報から必須inputを一意に解決できれば実行でき、曖昧なら推測せず停止する。

## 書いてはいけないもの

グローバル設定 (~/.claude/CLAUDE.md / ~/.codex/AGENTS.md) が常時ロードされるため、
以下をプロジェクトファイルに再掲しない (ドリフトの原因になる):

- 言語ルール (日本語出力など) / uv / 絵文字 3 種 / 全角カッコ禁止
- コミットメッセージ形式 / Git・PR 運用 / レビュー実行 (/popr)

例外: チームメンバーもエージェントを使うリポジトリでは、メンバー共通で守るべき規約
(成果物の日本語統一など) を「実装規約」セクションに書いてよい。

## メンテナンス

- 旧世代ファイル (企画書型・300 行超) をこの構成へ移行する際は、ロードマップ/ビジネスモデルは
  docs/ へ、条件付きの長い手順は skill へ逃がす
- このテンプレートを更新しても、各プロジェクトへコピー済みのファイルには反映されない
- テンプレート自体を変更するときも AGENTS.md と CLAUDE.md の両方を同時に更新する
- テンプレートの正本はこのリポジトリ (Agents) で管理する。ローカル同期 (`sync-from-local.sh` / `apply-to-local.sh`) の対象外
