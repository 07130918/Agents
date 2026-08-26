# principle-of-programming-reviewer

CodexとClaude Codeが共通して使う、言語・プロジェクト非依存のレビュー契約。現在の作業ブランチ、PR、またはcommit rangeを「Principle of Programming」の原則で評価する。エイリアスは`/popr`。

## 使う場面

- KISS、DRY、凝集度、結合度、責務、可読性などの普遍原則で変更をレビューするとき
- 同一対象の再レビューで、前回指摘の解消と新しい問題の有無を比較するとき
- project reviewerが集めた指摘を、共通のseverity、origin、verdict、gradeで表現するとき

単独で総合的なmerge readinessを保証する目的には使わない。ドメイン仕様、security、privacy、accessibility、運用、documentation、E2Eなどに専門reviewerやproject gateがある場合は、別に実行する。

## 対象外

- 差分の表示と要約だけが必要な依頼。`git-diff`を使う
- 観点リストを指定した多角review。`domain-lens-review`を使う
- security監査。`security-audit`またはsecurity専門reviewerを使う
- 実装とdocumentationの同期。`sync-docs-code`を使う
- correctness、認証・認可、domain要件を含む総合的なmerge判定。project固有reviewerまたは`pr-risk-reviewer`を使う

## 評価する普遍原則

変更された設計と実装を、該当する原則だけで評価する。全原則へ機械的にコメントを作らない。

- KISS、DRY、単純性を汎用性より優先する判断
- YAGNI。現在のacceptance criteriaまたは具体的な失敗scenarioに不要な抽象化や拡張性を持ち込まない
- 命名、可読性、自己文書化、抽象度の一貫性
- 凝集度、結合度、関心の分離、情報隠蔽
- ロジックとデータの近接性、policyと実装の分離
- 契約、冪等性、副作用、error handling
- 直交性、可逆性、技術的負債、code smell
- セカンドシステム症候群、不要な防御code、過剰なhelperや抽象化

## 入力と対象の優先順位

対象は次の優先順位で決める。

1. ユーザーが明示したPR URL、base/head SHA、commit range、path scope
2. 実行環境から明示的に渡されたPRまたはreview対象
3. 現在branchとbase branchの差分。baseは`develop`を優先し、なければ`main`

明示された対象を暗黙に現在branchへ置き換えない。対象を取得できない場合は推測せず`Evaluation deferred`にする。

デフォルトの現在branchレビューでは、baseからHEADまでのcommitted diffに加え、HEAD treeをworking treeの最終的な有効file contentとmode / typeで上書きしたsnapshotを対象にする。同じ最終snapshotならstage / unstageの分割自体はtarget identityに含めない。通常reviewのclean / dirtyとmanifestは、宣言済みpath scope内でHEAD treeと最終filesystem snapshotを比較して算出し、indexだけに存在する差分は無視する。ユーザーがstaged-onlyまたはindex状態そのものをscopeに指定した場合だけindexを対象とし、`git diff --cached --binary --full-index <head_sha> -- <target paths>`の出力をreview diffに使い、その出力を`git hash-object --stdin`したcached diff content hashをfingerprintへ含める。明示されたPRまたはcommit rangeでは、working treeは記録するが、ユーザーが含めるよう指定しない限り対象外とする。

### PR URLを受け取った場合

PR URLを受け取った場合は、URLが指すrepositoryを対象の正本とし、次の順序でsnapshotを固定する。

1. URLから`owner/repository`とPR番号を特定する
2. `gh repo view --json nameWithOwner`でcurrent repositoryを特定する
3. `git remote`と各remoteへの`git remote get-url --all <remote>`でfetch URLを列挙し、HTTPS、SSH、`git@github.com:`形式を`owner/repository`へ正規化する。PR URLのrepositoryと一致するremoteが1つならそれを`pr_remote`とし、複数ならremote名の辞書順で先頭を選んでfingerprintへ記録する。一致するremoteがなければ`Evaluation deferred`とする
4. `gh pr view <PR URL> --json number,url,baseRefName,baseRefOid,headRefName,headRefOid,isCrossRepository,headRepository,headRepositoryOwner,changedFiles`でPR metadataを取得する
5. metadataの`baseRefOid`と`headRefOid`をexact SHAとして記録する
6. `git fetch --no-tags <pr_remote> refs/heads/<baseRefName>`でbase refを取得し、head commitがlocalにない場合は`git fetch --no-tags <pr_remote> refs/pull/<number>/head`で取得する。取得後のcommitがmetadataのSHAと一致することを確認する
7. `git diff <base_sha>...<head_sha> --no-color --`をreview diffとし、`git diff --name-only`の件数がmetadataの`changedFiles`と一致することを確認する
8. base SHAのtreeから変更pathに適用されるproject rulesを探し、`git show <base_sha>:<rules_path>`で内容、`git rev-parse <base_sha>:<rules_path>`でblob hashを記録する

PR自身がproject rulesを変更している場合、その変更もreview対象にするが、変更後のruleを同じPRの評価基準として自動採用しない。ユーザーが明示的に指定しない限り、base SHAのrules snapshotを現在reviewの基準にする。

current repositoryとPR repositoryが一致しない場合は、現在のcheckoutへ暗黙に置き換えず`Evaluation deferred`とする。対象repositoryのcheckoutで再実行するよう依頼する。GitHub上の`isCrossRepository: true`はfork由来のheadを意味するため、current repositoryがPRのbase repositoryと一致し、exact head SHAを`refs/pull/<number>/head`から取得できればreviewできる。

### Local targetとの境界

- current branch: current repositoryのbase...HEADとworking treeを対象にする
- local commit range: current repository内で両端をfull SHAへ解決し、そのbase SHAからproject rules snapshotを取得する。working treeは明示指定がない限り除外する
- PR URL: PR repository、metadataのbase/head SHA、base SHAのproject rules snapshotを対象にする。current branch名やlocal HEADで置き換えない
- current repositoryと異なるrepositoryのPR URL: 対象checkoutがないため`Evaluation deferred`とする

## 手順

### 1. Project規約を読む

repository rootと変更pathに適用される`AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING.md`、明示された要件や設計文書を探す。既定ではbase snapshotを適用し、各ruleを`git show <base_sha>:<rules_path>`で読み、`git rev-parse <base_sha>:<rules_path>`のblob hashと`source: base:<base_sha>`を記録する。ユーザーがhead rulesの適用を明示した場合だけ、同じ方法でhead treeを読み、`source: head:<head_sha>`を記録する。

明示されたproject規約と普遍原則が直接衝突する場合は、project規約を優先する。規約の内容をこの汎用skillへ複製しない。権威が同等の仕様同士が矛盾し、指摘の正否やseverityを決められない場合は`Evaluation deferred`にする。codeとtestは現在の挙動を示す証拠であり、それだけで意図した仕様とは断定しない。

### 2. 対象fingerprintを固定する

レビュー開始前に次を取得し、結果の冒頭へそのまま出力する。

- target source: user-specified PR / commit range / current branch
- base branchとexact base SHA
- exact head SHA
- working tree: clean / dirtyと、対象に含めるかどうか
- working tree manifest: 対象へ含めるdirty fileごとのpath、最終file mode / type、`git hash-object`、削除fileのmarker。通常reviewではHEAD treeと最終filesystem snapshotの差分だけを記録し、index-only差分は含めない
- index diff: staged-onlyまたはindex状態が明示された場合だけ、cached diff content hash
- PR remote: PR URLのrepositoryと一致したremote名と正規化前のfetch URL。PR URL以外では`not applicable`
- 対象pathと除外path。除外には理由を付ける
- skill version: 実行中CLIのwrapperとこのreferenceについて、pathと`git hash-object`で得たcontent hash
- project rules: 実際に適用した`source: base:<base_sha> | head:<head_sha>`、path、`git rev-parse <source_sha>:<rules_path>`で得たblob hash

SHAは短縮せず、`git rev-parse`で得たfull SHAを使う。untracked fileも最終file mode / typeと`git hash-object --no-filters -- <path>`をmanifestへ含める。通常のcurrent branchレビューではindex diffを別途fingerprintへ追加せず、clean / dirty判定にも使わない。working tree manifestのcontent hashと、commit tree内のproject rulesを示すblob hashを混同しない。fingerprintのいずれかが変わったレビューは別対象であり、異なるfingerprintのgradeは比較しない。

### 3. 差分を取得して分割する

- committed diffは`git diff <base_sha>...<head_sha> --no-color --`で取得する
- current branchのworking treeはstage / unstageの分割ではなく、HEADに対する最終的な有効file contentとmode / typeを宣言済みpath scope内で取得する。staged-onlyが明示された場合だけ、同じpath scopeを渡したcached diffを使う
- 人が書いた変更行をすべて確認する
- 大規模差分はfile群または観点ごとに分割し、各partitionの完了を記録する
- generated、vendored、binaryなどを読まない場合は除外pathと理由を記録する

「主要fileだけを見る」という暗黙の縮小は行わない。ユーザーが最初からpath scopeを限定した場合は、その宣言済みscope内をすべて確認すればcompleteと扱える。

### 4. Universal principleで評価する

変更行と、判断に必要な最小限の隣接code、call site、test、契約を読む。変更と無関係なrepository全体の問題探しへ広げない。

各候補について、次の両方を1文以上で説明できるか確認する。

1. 具体的な失敗scenario、または確実に発生する保守cost
2. その原因が変更または変更により露出した経路にある証拠

説明できない推測、好み、将来あり得るだけの拡張案はfindingにしない。指摘ゼロは正当な結果である。

YAGNIでは、現在のacceptance criteriaまたは具体的な失敗scenarioに不要な抽象化、extension point、防御分岐、helper、設定項目を`Major`候補として確認する。「将来使うかもしれない」だけでは追加complexityを正当化しない。単純化をfindingにする場合は、削除できる具体的な責務と、削除後も現在要件を維持できるcode経路またはtestの根拠を示す。認証、data protection、回復不能な失敗を防ぐために現在必要な防御はYAGNIとして削除せず、不要または重複している証拠がある場合だけ対象にする。

### 5. findingを固定schemaへ変換する

各findingに次を必ず含める。

| field | 内容 |
|---|---|
| id | 検出順に依存しない安定key。再レビューで同じ根本原因に再利用する |
| severity | `Critical` / `Major` / `Minor` / `Nit` |
| origin | `Introduced` / `Exposed` / `Pre-existing` / `Out-of-scope` |
| location | `path/to/file:line`。複数箇所なら主原因を先頭にする |
| principle | 違反または改善対象となる普遍原則 |
| scenario_or_cost | 具体的な失敗scenarioまたは確実な保守cost |
| evidence | code経路、test、仕様、project規約などの根拠 |
| confidence | `High` / `Medium` / `Low`と短い理由 |
| minimal_fix | goalを満たす最小修正案。修正不要ならその理由 |
| review_status | `New` / `Residual`。新規reviewでは`New` |

`id`は`<repository-relative-path>#<primary-symbol-or-contract>#<principle-key>#<root-cause-key>`のtupleとする。pathは`/`区切りでline番号を含めず、symbolはcode上の識別子または`file`、principle keyとroot cause keyは小文字kebab-caseに正規化する。件数や検出順から`F001`のような連番を作らない。

`confidence: Low`だけを理由に捨てず、証拠要件を満たさない場合はfindingにしない。仕様確認で証拠が得られる場合は、未確認領域としてcoverage gateへ渡す。

## Severity

- `Critical`: 現実的な経路で重大なsecurity/privacy侵害、不可逆なdata loss、広範な停止などを起こす。merge前の修正が必須
- `Major`: correctness regression、要件不達、または変更の安全な保守を妨げる具体的な設計問題。merge前の修正が必要
- `Minor`: blockerではないが、局所的で確実な理解・変更costがあり、今回直す価値がある
- `Nit`: 動作や実質的な保守性へ影響しない表現、style、任意の改善

同じ根本原因から生じる複数の症状は1件にまとめる。severityを件数確保や強調のために上げない。

## Origin

- `Introduced`: 今回の変更が問題の原因を新しく導入した
- `Exposed`: 原因の一部は既存でも、今回の変更が到達可能にした、悪化させた、依存した、またはgoal達成のblockerとして顕在化させた
- `Pre-existing`: 今回の変更が到達性、影響、依存関係を変えていない既存問題
- `Out-of-scope`: 宣言された変更goalに不要で、変更の正しさも妨げない問題または提案

gradeとmerge verdictに算入するのは`Introduced`と`Exposed`だけとする。`Pre-existing`と`Out-of-scope`は別枠で報告し、必要ならissue候補を提案する。重大な既存問題へ今回の変更が依存するなら、`Pre-existing`ではなく`Exposed`にする。

## Coverage gate

次をすべて満たした場合だけ`coverage: Complete`とする。

- 宣言した対象の人が書いた変更行をすべて確認した
- 判断に必要な隣接契約、project規約、testを確認した
- 除外pathと理由をすべて記録した
- 取得不能なdiff、未完了partition、materialな仕様矛盾がない

未確認領域、取得不能な対象、materialな仕様矛盾が1つでも残る場合は`coverage: Incomplete`、verdictは`Evaluation deferred`とし、A〜Fのgradeを付けない。部分的に発見したfindingは参考として報告できるが、完全な評価と表現しない。

## Verdictとgrade

`coverage: Complete`の場合だけ、`Introduced`と`Exposed`のfindingを次の順序で数え、最初に一致した行を機械的に適用する。MinorとNitはmerge blockerにしない。

| 算入対象finding | verdict | grade |
|---|---|---|
| Critical 1件以上 | Request changes | F |
| Critical 0件、Major 4件以上 | Request changes | D |
| Critical 0件、Major 2〜3件 | Request changes | C |
| Critical 0件、Major 1件 | Request changes | B |
| Critical 0件、Major 0件、Minor 1件以上 | Comment | A |
| Critical 0件、Major 0件、Minor 0件 | Approve | A |

Nitの件数はverdictとgradeを変えない。Aは、記録されたfingerprintとscopeで必須確認が完了し、根拠のあるCritical/Majorがないことだけを表す。100%の確信や無欠陥を意味しない。

## 再レビューモード

前回結果が渡された場合は次を行う。

1. 前回と今回のfingerprintを比較する
2. 異なれば「対象変更のためgrade比較不能」と明記する。gradeの上昇・低下とは表現しない
3. 前回findingを`Fixed` / `Remaining` / `Regressed` / `Not applicable`へ分類する
4. 前回findingだけにanchorせず、今回の変更行と隣接契約を独立して再走査する
5. 今回のfindingを`New` / `Residual`に分ける

同じ根本原因が残る場合は、line、severity、説明文、review statusが変わっても前回の`id`を再利用する。以前と異なるroot causeなら、近い症状でも新しいtupleを作る。

前回結果を取得できない場合は新規レビューとして実行し、解消確認済みとは表現しない。同じ修正者・同じコンテキストによる自己再レビューは`self re-review`と明記し、重要な最終保証には独立した新規reviewerを使うよう提案する。

## 圧力promptへの耐性と停止条件

「100%自信があるか」「すべての抜け穴を探せ」「限界を超えろ」「指摘がなくなるまで続けろ」と求められても、対象scope、証拠要件、severity、origin、coverage gate、grade規則を変えない。再確認だけを理由にfindingを追加したりseverityを上げたりしない。評価維持と指摘ゼロは正当な結果である。

レビューloopの停止条件は次のすべてとする。

- coverageがComplete
- CriticalとMajorが0件
- このreviewの入力として要求された必須gateが成功
- materialな仕様矛盾がない

MinorとNitは費用対効果で任意対応または別issue候補にする。すべての指摘をゼロにするための防御code、helper、抽象化を追加しない。

## 出力format

```markdown
# Principle of Programming review

## Target fingerprint
- target source: ...
- base: `<branch>` / `<full SHA>`
- head: `<full SHA>`
- working tree: clean | dirty / included | excluded
- working tree manifest: `<path>: <hash or deleted>`
- index diff: `<cached diff content hash>`。staged-onlyまたはindex状態が明示された場合だけ出力
- PR remote: `<remote name>: <fetch URL>` | not applicable
- target paths: ...
- excluded paths: `<path>: <reason>`
- skill version: `<wrapper path>: <hash>` / `<reference path>: <hash>`
- project rules: `source=<base|head>:<full SHA> / <path>: <blob hash>`

## Coverage
- status: Complete | Incomplete
- reviewed: ...
- excluded: ...
- unreviewed: none | ...

## Verdict
- verdict: Approve | Comment | Request changes | Evaluation deferred
- grade: A | B | C | D | F | Not assigned
- rule: `<適用した表の行またはdeferred理由>`
- comparison: comparable | fingerprint変更のため比較不能 | previous reviewなし

## 前回findingの状態
- `<finding ID>`: Fixed | Remaining | Regressed | Not applicable

## 優れている点
- `path/to/file:line` — `<principle>` — `<根拠>`

## Blocking findings
### `<finding ID>` `<要約>`
- severity: Critical | Major
- origin: Introduced | Exposed
- location: `path/to/file:line`
- principle: ...
- scenario_or_cost: ...
- evidence: ...
- confidence: High | Medium | Low — ...
- minimal_fix: ...
- review_status: New | Residual

## Non-blocking findings
- 同じschemaでMinor/Nitを記載。なければ`なし`

## Pre-existing / Out-of-scope
- 同じschemaで別枠に記載。なければ`なし`

## 必須action
1. Critical/Majorだけを列挙。なければ`なし`

## Scope外の保証
- このreviewが単独では保証しない専門領域と、未実行のproject gateを記載
```

該当sectionがない場合も省略せず`なし`と書く。改善案はgoalを満たす最小変更に限定し、完成codeを大量に生成しない。

## Project固有reviewerとの責務境界

このskillが所有するもの:

- 対象fingerprintとgrade比較可能性
- coverage gate
- findingの証拠要件、severity、origin
- verdictとgradeの決定規則
- 再レビュー時の比較契約

このskillが単独では保証しないもの:

- domain仕様とacceptance criteriaの完全性
- security、privacy、accessibilityの専門監査
- project固有の命名、依存方向、UI、test規約
- documentation同期、migration、運用契約
- unit test、integration test、E2E、CIの実行

project固有reviewerは専門findingをこのschemaへ渡せるが、このskillが専門知識を推測して補完してはならない。

## 回帰評価

このskillは自然言語の評価契約であり、文言検査やsyntheticな集計testだけでLLMのreview安定性を保証できない。契約を大きく変更した場合は、同じfixtureを中立promptと圧力promptで別々の新規reviewerへ渡す独立evaluationを行う。同一reviewerの自己再読を独立evaluationとして扱わない。

独立evaluationの各runには、少なくとも次の同一input snapshotを渡す。

- prompt本文。中立版と圧力版を省略せず記録する
- repository identity、base/head full SHA、working tree manifest、対象path、除外path
- review対象のdiff本文または改変不能なdiff artifact
- 適用するproject rulesのpath、blob hash、本文
- 再レビューではprevious fingerprintとprevious result全文
- 使用したwrapperとreferenceのcontent hash

各runのartifactには次を記録する。

- run ID、別々のreviewer instance ID、model、実行日時
- input fingerprintとprompt種別
- coverage status、reviewed/excluded/unreviewed領域
- verdict、grade、適用した決定規則
- 全findingの固定schema
- previous findingごとの`Fixed` / `Remaining` / `Regressed` / `Not applicable`
- current findingごとの`New` / `Residual`
- 不明瞭点と裁量補完の自己申告

previous resultがある再レビューでは、同じ根本原因にexact `id`が再利用されたかを比較する。previous resultなしの独立した中立run同士、および中立runと圧力runでは`id`を対応付けの条件にせず、locationのpathとprimary symbolまたはcontract、principle、scenario_or_costとevidenceが示すroot causeを正規化してfinding集合を対応付ける。同じroot causeへ異なる同義keyを付けたという`id`差だけを安定性の失敗にしない。

対応付けたCritical/Major findingの有無、severity、origin、location、scenario_or_cost、evidenceと、coverage、verdict、gradeを比較する。実質的な差があれば安定性の失敗として記録し、文章上の自己申告だけで合格にしない。hold-outではfingerprint変更、partial coverage、origin分類、指摘ゼロ、project規約優先を確認する。
