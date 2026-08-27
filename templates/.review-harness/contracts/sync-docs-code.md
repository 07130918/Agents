# sync-docs-code

PR提出前に、現在の変更差分が作る契約とリポジトリ内ドキュメントを照合し、同じPRで必要な文書更新と検証まで完了する。後追いの文書修正を減らすための変更単位のゲートであり、全リポジトリ監査は行わない。

## 目次

- [使う場面](#使う場面)
- [入力](#入力)
- [出力と完了ゲート](#出力と完了ゲート)
- [基本原則](#基本原則)
- [手順](#手順)
- [発火テスト例](#発火テスト例)
- [失敗時](#失敗時)
- [関連skill](#関連-skill)
- [参考資料](#参考資料)

## 使う場面

- 機能実装、バグ修正、DB、API、UI、設定、運用変更をPRへ提出する前。
- 「ドキュメントを実装に同期」「READMEやdocsも更新」「文書の更新漏れを確認」と依頼されたとき。
- `issue-to-pr`、`docs-driven-development`、`create-pr`からPR前ゲートとして呼ばれたとき。

対象外:

- 最新main全体の文書棚卸しや乖離レポートだけを求める依頼。`docs-code-consistency-audit`を使う。
- 実装変更と無関係な文言校正、翻訳、体裁調整。
- リポジトリ外のWikiやSaaS文書の更新。明示的な依頼と接続手段がある場合だけ別作業として扱う。

## 入力

- 比較元branchまたはcommit。未指定ならoriginの既定branchを使う。
- 比較元からHEADまでのcommit済み差分と、作業ツリー・indexの未コミット差分。
- リポジトリの`AGENTS.md`、`CLAUDE.md`、README、docs、生成設定、PRテンプレート。

## 出力と完了ゲート

- 変更契約と文書候補を対応付けた根拠。
- 必要な場合は、現在の変更に直接関係するリポジトリ内ドキュメントの更新。
- 文書lint、リンク、command、schemaなど変更内容に応じた検証結果。
- 最終status: `PASS`、`UPDATED`、`BLOCKED`のいずれか。

判定:

- `PASS`: 関連文書を根拠付きで確認し、更新不要と判断できる。
- `UPDATED`: 必要な文書を同じ差分へ追加し、関連検証が成功した。
- `BLOCKED`: 今回の変更に関係する乖離、正本の衝突、未検証項目が残る。PRを作成しない。

「docs変更なし」だけでは`PASS`にしない。確認した文書候補と更新不要の理由を残す。PRへ進めるのは`PASS`または`UPDATED`だけとする。

## 基本原則

- コード、テスト、schema、migration、設定は現行挙動の証拠として扱う。
- 要件定義、ADR、承認済み設計書は意図の正本になり得る。実装との差を見つけても、実装へ合わせて黙って書き換えない。
- どちらが正本か不明な変更関連の矛盾は`BLOCKED`にする。今回の差分と無関係な既存乖離は変更へ混ぜず、日本語の派生issue候補として報告する。
- 自動生成文書を直接編集しない。生成元を更新し、既存の生成commandで再生成する。
- 文書のためだけに実装scopeを広げない。反対に、実装scopeに必要な文書更新を別PRへ先送りしない。

## 手順

### 1. 比較範囲を固定する

1. `git status --short --branch`でbranchと作業ツリーを確認する。
2. `git symbolic-ref refs/remotes/origin/HEAD`を優先してbaseを決める。失敗時は`develop`、次に`main`を使う。
3. `git diff --name-status <base>...HEAD`でcommit済み差分、`git diff --name-status`と`git diff --cached --name-status`で未コミット差分を確認する。
4. rename、delete、生成物、migrationを含め、今回の変更ファイル集合を確定する。

### 2. 文書の正本と規約を見つける

1. `AGENTS.md`と`CLAUDE.md`、README、`docs/`、`.env.example`、OpenAPI、schema、migration、PRテンプレートを必要な範囲で棚卸しする。
2. 文書index、生成comment、contributing guideから、手書き文書と自動生成文書の正本を区別する。
3. `AGENTS.md`と`CLAUDE.md`の対称管理など、プロジェクト固有の同期規約を先に確認する。

### 3. 差分から契約を抽出する

ファイル名だけで判断せず、差分と関連テストから外部へ現れる契約を列挙する。

- ユーザーができること、できなくなること、画面遷移、文言、入力制約。
- API route、request、response、status、error、認証・認可。
- table、column、型、NULL、default、index、外部キー、migration、保持期間。
- 環境変数、設定値、feature flag、依存version、build・deploy手順。
- CLI、script、運用手順、監視、rollback、障害対応。
- architecture境界、directory、import規約、拡張point。

### 4. 契約を文書候補へ対応付ける

| 変更契約 | 優先して確認する文書 |
|---|---|
| DB schema・migration・seed | テーブル定義、ERD、migration・backup・restore手順 |
| API route・schema・client | OpenAPI、API設計、連携例、error一覧 |
| UI・入力制約・ユーザーフロー | 要件定義、利用guide、画面仕様、accessibility記述 |
| auth・role・permission | 権限表、security設計、API・運用手順 |
| env・config・dependency・build | `.env.example`、README、setup、deploy、対応version |
| CLI・script・job | README、contributing guide、runbook、schedule |
| architecture・directory規約 | ADR、architecture docs、`AGENTS.md`、`CLAUDE.md` |
| logging・metrics・alert | observability docs、runbook、障害対応手順 |

表にない変更も、利用者、開発者、運用者が次に参照する正本を考えて候補へ加える。

### 5. 照合して同じ差分へ反映する

1. 各契約について、既存記述が一致、不足、矛盾、対象外のどれかを判定する。
2. 不足は最小限の変更で補い、古い記述は置換する。重複した説明を別文書へ増やさない。
3. 仕様の正本と実装が衝突した場合は、issue・PRの受入条件と変更意図から正しい側を確認する。判断できなければ`BLOCKED`にする。
4. 自動生成文書は生成元を直して再生成する。
5. 文書内の例、command、path、version、制約値を実装上の識別子まで照合する。

### 6. 検証する

- プロジェクト指定のMarkdown・文書lint、link検査、schema生成、API生成を実行する。
- 文書に記載したcommand、script、route、環境変数がリポジトリに存在することを`rg`などで確認する。
- DB変更はschema、migration、bootstrap、テーブル定義の同値性を確認する。
- API変更はrequest・response schema、handler、client、API文書の同値性を確認する。
- `AGENTS.md`または`CLAUDE.md`を更新した場合は、対称管理規約に従って他方も確認する。
- 専用validatorがなければ、少なくとも`git diff --check`と更新Markdownの構文確認を行う。

### 7. ゲート結果を残す

PR本文の動作確認またはドキュメント欄へ、次を短く記載する。

```markdown
## ドキュメント同期

- status: PASS | UPDATED
- 確認した契約: {DB / API / UI / config / operationなど}
- 更新文書: {path。更新なしの場合は理由}
- 検証: {実行commandと結果}
```

内部確認では、次の形式で根拠を残す。

```markdown
| 変更契約 | 実装上の根拠 | 文書 | 判定 | 検証 |
|---|---|---|---|---|
| ... | ... | ... | 一致 / 更新 / 対象外 | ... |
```

## 発火テスト例

発火すべき:

- 「このDB migrationをPRにする前にテーブル定義書と実装を同期してください」
- 「API変更に対してREADMEとAPI設計の更新漏れを確認して直してください」
- 「実装は終わったので、関連docsを同期してからPRへ進めてください」
- 「UIの入力制約を変更したので要件定義と利用guideも合わせてください」
- 「`$sync-docs-code`でbase branchとの差分を確認してください」

発火すべきでない:

- 「最新main全体でdocsとコードの乖離を監査して報告してください」は`docs-code-consistency-audit`を使う。
- 「READMEの誤字だけ直してください」は通常の文書編集として扱う。
- 「このbranchの差分を要約してください」は`git-diff`を使う。
- 「この変更でPRを作ってください」は`create-pr`を使い、その手順内で本skillを呼ぶ。
- 「実装前に大規模機能の設計書とPR分割を作ってください」は`docs-driven-development`を使う。

## 失敗時

- 文書の正本が見つからない場合は、READMEやdocs indexを確認し、推測で新しい文書を増やさない。
- 生成commandが壊れている場合は`BLOCKED`にし、実行command、error、影響する文書を報告する。
- 外部文書だけが残る場合はリポジトリ内の同期を完了したうえで、外部更新に必要な権限と具体的な手順を1行で依頼する。
- 既存の無関係な乖離は現在のPRへ混ぜず、日本語のissueタイトルと受入条件を提案する。

## 関連 skill

- `docs-code-consistency-audit`: 最新main全体を棚卸しし、乖離を報告するとき。
- `issue-to-pr`: issue起点の実装で、このskillをPR前ゲートとして呼ぶ。
- `docs-driven-development`: 多段PRごとに設計書と実装の一致を確認するとき。
- `create-pr`: このskillが`PASS`または`UPDATED`になった後にPRを作成する。

## 参考資料

- [OpenAI: Build skills](https://developers.openai.com/codex/skills/)
- [Anthropic: Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [GitHub: Creating a pull request template](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
- [Docs as Code](https://docs-as-co.de/)
