# issue-to-pr

GitHub issue を起点に、調査・実装計画・実装・品質ゲート・レビュー・PR 提出までを一気通貫で進めるワークフロー。issue 本文とコメントを精読して仕様の曖昧さを潰し、スコープを宣言してから実装に入ることで、手戻りと巻き込み過ぎを防ぐ。

## 発火条件

- `/issue-to-pr <issue URL または番号>`
- issue の URL または番号とともに、次のような依頼があったとき: 「このissueに対応して」「issueをよく読み実装して」「issueから実装計画を立ててPRまで」「issue #123 を直して」

対象外 (発火しない):

- issue を伴わない単発のバグ報告や質問 (例: 「ログインできない」「このエラーの原因は?」) — `bug-investigation` や通常対応に譲る
- 差分確認だけ、PR 作成だけなど、issue を経由しない単発作業 — `git-diff` / `create-pr` に譲る
- 実装計画の相談のみで、コード変更まで求めていない依頼 — `serena` の design 分類などに譲る

## 完了条件

- この skill が発火した場合、明確なブロッカーがない限り、計画提示・スコープ宣言・ブランチ作成だけで停止してはいけない。
- issue 精読、実装、テスト、ドキュメント同期、コミット、push、PR 作成、完了報告まで同じターンで継続する。
- ユーザー確認が必要なのは、仕様が曖昧で実装すると危険な場合、認証・権限・外部操作が必要な場合、品質ゲートを通せない場合、またはユーザーが明示的に「計画だけ」「PR はまだ出さない」と依頼した場合に限る。
- 完了報告は、必須品質gateとdocumentation同期が成功し、PR URL、検証結果、残riskを提示できる状態で行う。PRを作成できなかった場合は、blocker、完了済み作業、再開に必要な具体操作を報告する。

## 実行経路

このworkflowには次の2経路があり、Harnessの有無だけでIssue intake、scope、permission、PR提出policyを変えない。

- 通常経路: 従来どおり手順1-8を実行し、手順9で`create-pr`のdefault経路へ委譲する。
- Harness委譲経路: 手順1-3でintakeを固定した後、手順4-8に相当するreview/fix/verify subflowをpersonal `review-remediation-harness`へ委譲する。`READY`なら`publish_exact_candidate`へ進み、blockerならHuman handoffで停止する。

Harness委譲はwrapper内部のcommand名に依存せず、次の入力と出力が一致するsemantic interfaceとして扱う。Personal Harnessを利用できない、または利用しない場合は通常経路を継続できる。

### Harness delegation interface

委譲前に次を固定する。

- Issueのsource identifier、取得した本文と全comment、取得時点のrevisionまたはcontent hash
- acceptance criteria、宣言済みscope、非目標
- base ref、base SHA、作業branch、委譲時点のheadまたはworking tree状態
- 許可されたfile変更、commit、scoped remote fetch、push、PR更新、外部read/writeのpermission
- Project instructionと利用可能なcontractのsource identifierまたはsnapshot

Harnessは次のどちらかだけを返す。

- `READY`: exact `base_sha`と`head_sha`、cleanなcandidate、同じtargetに結び付くrequired verification・gate・Final reviewの結果、未解決blockerがないことを返す。
- blocker: 観測した状態、停止理由、完了済みartifact、無効化したartifact、再開stateと不足inputを返す。仕様判断、scope拡大、利用不能なrequired gate、独立reviewer不在を成功へ読み替えない。

委譲後にIssue、project rule、base SHA、head SHA、scope、permissionのいずれかが変わった場合、受領済み`READY`を失効させる。変更内容をintakeへ反映し、影響するcontext、verification、gate、reviewを再実行して新しいtargetを固定するまでpublishしない。

## 手順

### 1. issue を精読する

- `gh issue view <番号> --comments` で本文と全コメントを取得する
- 番号だけが与えられた場合は現在の repo で解決する。URL が与えられた場合は `gh issue view <URL> --comments` でよい (`gh` は URL からも repo を解決できる)
- 仕様の曖昧さ、再現条件の不足、意図が読み取れない箇所があれば、着手前にユーザーへ質問する。憶測で実装を進めない
- 関連 PR やリンクされている issue があれば併せて確認する

### 2. 実装計画とスコープを宣言する

- 対象ファイル・変更範囲の見込みを明示する
- テスト方針 (単体テストの追加有無、対象ケース) を明示する
- 「やらないこと」を明示する — issue の範囲を超える改善案は後述の派生タスク提案に回し、今回のスコープには含めない
- File変更、commit、scoped remote fetch、push、PR更新、外部read/writeのうち今回許可された操作を明示する。権限が不明な副作用は許可済みと推測しない
- この宣言は作業開始前の共有であり、ユーザー確認待ちではない。ブロッカーがなければ同じターンで手順 3 へ進む

### 3. 作業ブランチを作成する

- base ブランチを決める: `develop` があれば `develop`、なければ `main` を優先する
- base ブランチを pull して最新化する
- 作業ブランチ名は `<issue番号>/<短い英語スラッグ>` 形式で作る (例: `1378/fix-login-redirect`)

Harnessへ委譲する場合は、ここでHarness delegation interfaceの入力を渡し、手順4-8に相当するsubflowを任せる。Harnessが`READY`またはblockerを返すまでは、呼び出し元が同じtargetへ並行して変更を加えない。`READY`を受け取ったら手順4-8を呼び出し元で再実行せず手順9へ進み、blockerなら指定された再開条件をHumanへhandoffして停止する。

### 4. 実装する

- バグ系 issue (エラー、不具合、想定外の挙動) の場合は、根本原因調査に `bug-investigation` の手順 (フィードバックループ構築→症状→ログ→コード→ランク付き仮説→計装→修正+回帰テスト→クリーンアップ) を使う
- 実装の進め方 (既存規約の確認、変更範囲を絞る、共有処理の扱い) は `serena` の implement 分類の手順を参照する
- 単体テストを実装とセットで追加する。回帰テストが書ける seam がなければ、その旨を記録する
- 変更目的が異なる実装、test、documentation、設定を混在させず、`create-pr`でcommit単位へ分けられる状態を保つ

### 5. 品質ゲートを通す

- プロジェクトの `CLAUDE.md` / `AGENTS.md` に記載されたコマンド (例: `make check`、`npm run lint`、`uv run pytest` 等) で lint / format / 型チェック / テストをすべて通す
- 通常経路でproject固有のコマンドが見つからない場合は、リポジトリの`package.json` scriptsや`Makefile`から変更scopeに妥当なコマンドを特定する
- Harness委譲経路ではpersonal Harness contractのfail-closed resolverへ従う。複数候補から変更scopeとの対応を一意に説明できないcommandは推測実行せず、候補と不足根拠をblockerとして返す

### 6. 実装とドキュメントを同期する

- `sync-docs-code` skill を実行し、base branch からの全差分について実装上の契約とリポジトリ内ドキュメントを照合する
- DB、API、UI、環境変数、設定、運用手順、architecture の変更に対応する正本を確認し、必要な更新を同じ差分へ含める
- ゲートが `BLOCKED` のままPR作成へ進まない。`PASS`または`UPDATED`になり、文書検証が成功してから次へ進む
- 文書更新は現在scopeの差分へ含め、stageとcommit分割は`create-pr`に委譲する
- 今回の差分と無関係な既存乖離は変更へ混ぜず、日本語の派生issue候補として報告する

### 7. 完了前の差分gateを通す

- `git diff --check`を実行する
- 最終diffを読み、scope外変更、秘密情報、debug用code、未処理errorがないことを確認する
- 変更に応じてedge case、認証・認可、NULL、error handling、後方互換性を確認する
- 指摘を修正した場合は、影響する品質gateを再実行する
- 必須gateの失敗または未解決のblockerが残る場合は、PR作成へ進まない

### 8. コードレビューを実行する

- 中規模以上の変更は、グローバル規約に従い `/popr` (`principle-of-programming-reviewer`) を実行する
- 指摘があれば対応し、対応しない場合は理由を明確にする

### 9. PR を提出する

- 通常経路では、candidate準備から提出まで`create-pr`のdefault経路へ委譲する
- Harnessから`READY`を受け取った経路では、同じbase/head SHAを入力として`publish_exact_candidate`だけを実行する。品質gateやdocumentation同期を含むmonolithicなdefault経路を再実行しない
- `publish_exact_candidate`の`SUCCEEDED`は提出完了として受け取る。`READY_INVALIDATED`は受領済み`READY`を失効させてHarness delegation interfaceのintakeから再開する。`NOT_PERFORMED|PARTIALLY_PERFORMED`はREADYを失効させずHarnessのpublish observation checkpointへ返し、budget内の安全な次attemptまたは停止をHarnessが決める。`RESULT_UNKNOWN`は同checkpointから自動retryせずHuman handoffへ進む
- どちらの経路も`create-pr`の共通契約と完了条件を満たし、issueをcloseするkeywordをPR本文へ含める

### 10. 完了報告する

- やったこと、PR リンク、検証結果 (品質ゲートの結果、セルフレビュー・コードレビューの結果)、次にやるべきことの候補を報告する
- issue へのコメント投稿や close はユーザーの指示があった場合のみ行う。無断で issue を操作しない

## 注意事項

- スコープ外の変更を混ぜない。手順 2 で宣言した範囲を守る
- 作業中に見つかった派生タスク (関連する改善、別のバグ、リファクタ候補) は、その場でコードに混ぜず、issue 化を日本語で提案する
- issue のコメントに機密情報や認証情報が含まれていても、それを PR 本文やコミットメッセージに転記しない

## 関連 skill

- `bug-investigation`: バグ系 issue の根本原因調査
- `serena`: 実装の進め方、設計判断が必要な場合の構造化手順
- `sync-docs-code`: PR前に変更差分と関連ドキュメントを同期するゲート
- `create-pr`: PR 作成そのもののフロー
- `git-diff`: 差分確認のみが必要な場合
- `principle-of-programming-reviewer`: 中規模以上の変更のコードレビュー
