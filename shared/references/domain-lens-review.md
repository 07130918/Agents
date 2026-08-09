# domain-lens-review

ドメイン固有の観点 (lens) を指定した読み取り専用の多角コードレビュー workflow。観点ごとに独立したレビューを並列実行し、重要度順の統合レポートを返す。コードは一切変更しない。

## 使う場面

- 「インフラ観点でレビュー」「アルゴリズムの正当性をレビュー」など、観点を指定したレビュー依頼。
- 「infra/security/test の観点で多角レビュー」「N観点でレビュー」という依頼。
- レビュー依頼に観点リスト (「観点(厳密に): ...」等) が列挙されているとき。

## 対象外

- 汎用レビュー: `pr-risk-reviewer` agent (正確性/セキュリティ) と `principle-of-programming-reviewer` skill (設計原則) を使う。
- 上記2つの一括実行: `multi-model-code-reviewer` agent を使う。
- セキュリティ専門の網羅監査: `security-audit` を使う。
- GitHub PR 単位のレビュー: PR レビュー用の workflow を使う。

## 入力

- 観点リスト。無い場合は diff の内容から下のプリセットを基に 3〜5 観点を提案し、確認してから進める。
- レビュー対象: 既定は作業ブランチとベースブランチ (develop/main) の差分に、staged / unstaged / untracked の作業ツリー差分を加えたもの。paths や commit range が指定されたらそれに従う。
- 追加制約 (あれば): 深掘りする領域、既知の懸念、除外パス。

## 出力

- 観点別サマリ (各観点 1〜3 行)。
- 統合指摘リスト (重要度順、観点タグ、file:line、根拠、修正案)。
- 確認したが問題なしと判断した範囲。
- 推奨する次のアクション (修正順序、追加で回すべき skill)。

## 既定の制約 (全観点共通)

- 読み取り専用。ファイル変更、git の書き込み操作、フォーマット実行を禁止する (`git diff` / `git log` / `git status` は可)。
- 外部ライブラリ・フレームワークの仕様に依存する指摘は、context7 (resolve-library-id → query-docs) で最新ドキュメントを裏取りしてから確定する。
- 指摘には必ず file:line の根拠、重要度 (Critical/High/Medium/Low)、修正案を付ける。
- 憶測を含む指摘は確信度 (高/中/低) を明示する。動かして確認していないことは断定しない。
- 出力は日本語。

## 観点プリセット

| 観点 | 主なチェック |
|---|---|
| infra | IaC (Terraform)、Cloud Run/Build、CI/CD、Docker、環境変数、secrets の扱い |
| db-migration | スキーマ変更、migration の可逆性、NOT NULL/default、インデックス、N+1 |
| algorithm | 数理ロジックの正当性、収束性、境界値、数値誤差、計算量 |
| security | authn/authz、injection、秘密情報の露出、依存の脆弱性 |
| performance | ホットパス、不要な再計算/再レンダリング、メモリ、バンドル |
| ui-ux | 状態設計、アクセシビリティ、レスポンシブ、エラー表示 |
| test | テスト十分性、境界ケース、壊れやすい mock、回帰リスク |
| docs-consistency | 仕様書/README/CLAUDE.md と実装の乖離 |

プロジェクト固有の観点 (例: ゲームソルバーの理論的正当性、帳票処理の精度) は自由に追加してよい。

## 手順

1. 対象 diff を確定する。base はプロジェクトの既定 (develop/main)。
   - コミット済み差分: `git diff <base>...HEAD` と `git diff --name-status <base>...HEAD`
   - staged 差分: `git diff --cached`
   - unstaged 差分: `git diff`
   - untracked ファイル: `git ls-files --others --exclude-standard` で対象パスを列挙し、各ファイルの内容は `git diff --no-index -- /dev/null <file>` で diff に含める。`git diff --no-index` の exit code 1 は差分ありとして扱う。
2. 観点リストを確定する。ユーザー指定が無ければ提案して確認する。
3. 観点ごとに独立レビューを実行する。
   - Claude Code: Agent tool で観点ごとに subagent を並列起動する (読み取り専用を明示)。
   - Codex / subagent が使えない場合: 観点ごとに順番に実行し、観点間でコンテキストと結論を混ぜない。
   - 各レビューには下のプロンプトテンプレートを使う。
4. 全観点の結果を統合する。
   - 同一 file:line への指摘は 1 件に統合し、観点タグを併記する。
   - 観点別ではなく、修正すべき順 (重要度順) に並べる。
5. 統合レポートを返す。修正はユーザーの指示があるまで行わない。

## レビュー subagent プロンプトテンプレート

```text
あなたは「<観点>」専門のコードレビュアーです。読み取り専用で作業し、ファイルを一切変更しないでください。

対象: <base>...<head> の diff (変更ファイル: <一覧>)
観点: <観点の説明と主なチェック項目>
追加制約: <あれば>

要求:
- 指摘ごとに重要度 (Critical/High/Medium/Low)、file:line、根拠、修正案を付ける
- 外部ライブラリ仕様に依存する指摘は context7 で裏取りする
- 憶測には確信度 (高/中/低) を付ける
- 問題が無い領域も「確認した範囲」として簡潔に列挙する
- 日本語で報告する
```

## 検証

- ユーザー指定の観点がすべて実行されたか。
- すべての指摘に file:line と重要度が付いているか。
- 作業ツリーに変更が無いか (`git status` が実行前と同じ)。

## 失敗時

- subagent が起動できない場合は逐次実行に切り替える。
- diff が巨大で観点ごとのレビューが浅くなる場合は、ファイル群を分割して同一観点を複数回に分ける。
- context7 が使えない場合は、裏取りできていない指摘をその旨明示して報告する。

## 関連 skill

- `pr-risk-reviewer` agent / `principle-of-programming-reviewer` skill: 汎用2観点。中規模以上の変更では `principle-of-programming-reviewer` を先に実行し、その後に本 skill でドメイン観点を追加する。
- `multi-model-code-reviewer` agent: 上記2つの一括実行。
- `security-audit`: セキュリティ専門の網羅監査。
- `testing-patterns`: test 観点の指摘を修正する際の参照。
