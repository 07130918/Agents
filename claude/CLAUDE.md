# コーディングエージェント グローバル設定

全プロジェクトに適用する個人設定とworkflow索引。プロジェクト固有の規約を優先する。

## 言語

- 英語で思考し、日本語で出力する。コード内コメントと文書は周辺fileの言語を優先し、規約がなければ日本語で書く。
- コミット、PR、issue、レビューコメント、ログ、テスト説明を含む成果物は日本語で書く。

## 実行環境とコーディング規約

- Pythonは常に`uv`を使う: `uv run python`、`uv run pytest`、`uv pip install`。`python`、`python3`、素の`pip`は使わない。
- 使用できる絵文字は`✅`、`⚠️`、`❌`のみ。
- 全角カッコU+FF08/U+FF09は使わず、半角`()`を使う。
- TypeScriptで`any`を使わず、Pythonには型hintを付ける。
- `let`より`const`と宣言的な処理を優先し、nested ternaryはif文へ分ける。

## 作業原則

- 着手前に計画とscopeを宣言し、依頼と無関係な変更を混ぜない。
- goalに対する最小実装を優先し、不要な抽象化、helper、防御codeを追加しない。
- 機能実装とbug修正には、変更を検証するunit testを追加する。test seamがなければ理由を記録する。
- 外部libraryのAPIに確信がなければ、一次情報の最新documentationを確認する。
- 実装と関連documentationの乖離を確認し、必要な更新を同じ変更へ含める。
- 判断の確信度が中または低なら、根拠と未確定点を示して変更前に確認する。
- 派生課題へscopeを広げず、日本語のissue候補として報告する。
- 説明のないlogやerror貼り付けは対応依頼として全文を読み、明らかなtypoは解釈を一言添えて進める。
- 「コミットしました」「mergeしました」「続けて」は続行合図として扱う。
- merge、認証、手動確認などuser操作が必要なら、具体的な依頼を1行で伝える。

## 観測可能な完了条件

完了報告の前に、変更に該当する項目をすべて満たす。

1. Project指定のlint、format、型check、testを実行し、必須commandが成功している。
2. Bug修正とUI変更は再現手順を実環境で再実行し、期待する挙動を確認している。
3. 最終diffでscope外変更、秘密情報、debug用code、未処理errorがないことを確認している。
4. 関連documentationと実装の契約が一致している。

実行できない検証は未検証として理由とuser向け確認手順を示す。必須checkの失敗または未解決のblockerが残る状態を完了と報告しない。

## Workflow索引

依頼に一致するskillを使う。wrapperが利用できないCLIでは、同名の`~/.agents/references/<skill-name>.md`を読む。

- Issue起点で実装からPRまで: `issue-to-pr`
- Bugの原因調査: `bug-investigation`
- 現在branchのcommit、push、PR作成: `create-pr`
- Worktreeの作成、確認、merge後整理: `git-worktree-ops`
- PR前のdocumentation同期: `sync-docs-code`
- 普遍的なprogramming原則によるreview: `principle-of-programming-reviewer`
- 独立reviewerによるreview、修正、検証: `review-remediation-harness`

詳細手順をこのfileへ重複させず、対応するskillまたはreferenceを正本とする。

## Gitと成果物の共通契約

- `main`と`develop`では作業せず、issue対応branchは`<issue番号>/<slug>`を使う。
- Commitは既定でuserが行う。commitまたはPR作成まで明示された場合は、対応skillの手順に従いagentが実行する。
- Commit件名は`<prefix>: <日本語の要約>`とし、prefixは`feat|fix|chore|refactor|perf|docs|test|style|build|ci|revert`から選ぶ。末尾に句点を付けない。
- Mergeはuserが行う。merge後はbaseをfast-forwardし、merge済み作業branchをlocalとremoteから整理する。
- 完了報告には、やったこと、成果物link、検証結果、次の候補を含める。
