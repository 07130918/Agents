# create-pr

現在branchの変更を意味のある単位でcommitし、品質gateとdocumentation同期を通してから、日本語のPRを作成するworkflow。commit分割、stage、push、PR作成の手順とworkflow固有policyはこのreferenceを正本とし、commit権限とmessage形式はglobal指示の共通契約に従う。

## 使う場面

- 「PRを作って」「commitしてpushし、PRを提出して」と依頼されたとき。
- `issue-to-pr`などのworkflowから最終提出を委譲されたとき。

対象外:

- 差分確認だけの依頼。`git-diff`を使う。
- Issueの調査・実装を含む一連の対応。`issue-to-pr`を起点にする。
- PR merge。mergeはuserが行う。

## 共通契約

- PR作成依頼は、現在scopeの変更をcommit、pushしてPRを作る権限に加え、現在repositoryの解決済みfetch transport locatorだけを対象とする`fetch_remote_refs` permissionを含む。Default経路ではremote default、`develop`、`main`のread-only名前解決、選択したbaseのexact fetch、publish時の設定済みfetch refspec範囲のpruneだけを許可し、別repository、別remote、tagは含めない。またcanonical GitHub identity解決、same-repository open PR検索、post-write read-backだけを対象に、host、API locator、credential scope、network、timeout、paid-call budgetを固定した`read_external_source` permissionを含む。Merge権限は含まない。
- PRは宣言済みscopeだけを含め、無関係な整形、依存更新、別課題を混ぜない。
- 1 commitを単独revertしたとき、その変更目的だけが戻る単位に分ける。
- 各commitは単独checkout時にもbuild、型check、関連testが通る状態を保つ。後続commitがなければ動かない変更は同じcommitにまとめる。
- 同じ目的の実装と関連testは原則として同じcommitに含め、独立して説明できるdata取得・永続化、UI、refactor・設定は別commitにする。
- 各commitで対象pathを`git add <path>`または`git add -p`により明示し、`git diff --cached`で内容を確認する。
- Commit件名はglobal指示の`Gitと成果物の共通契約`に従う。
- PR titleと本文は日本語で書き、全commitと最終diffの実態を反映する。
- PR作成時は`07130918`をassigneeに設定し、変更内容に合うlabelを付ける。
- Bot reviewは指摘の根拠を検証し、妥当な指摘だけを反映する。Copilotへのreview依頼はuserが手動で行う。

## Git transport locator

Fetch permissionとGitHub publish identityを同じ概念にしない。`fetch_transport_locator`と`push_transport_locator`は、configured remote、`remote.<name>.url`、`remote.<name>.pushurl`、適用される`url.*.insteadOf`と`url.*.pushInsteadOf`をread-onlyで解決した、credentialを含まないexact effective URLである。GitのURL解決をもう一度適用してもbytesが変わらないfixed pointで、fetch用とpush用が各1件だけの場合に確定できる。0件、複数件、cycle、2回目のrewrite、embedded credential、未知remote helper、取得不能があれば推測せず停止する。

Fetchとpushはremote名でなく固定済みeffective URLをcommand引数に使う。Fetchは`git -c maintenance.auto=false fetch --no-tags <fetch_transport_locator> <source>:<destination>`相当、pushは`git push --no-verify <push_transport_locator> <head_sha>:refs/heads/<head-ref>`相当とする。これにより実行時のremote config再解決とpre-push hookを介在させない。Raw configured URL、全push URL、rewrite rule、effective locator、`core.hooksPath`と対象pre-push hookの存在をEvidenceへ保存し、publish以外のGit hookは起動しない。Embedded credentialを検出した場合は外部操作前に停止し、秘密部分を除いた診断と元値のhashだけをEvidenceへ保存してraw値を永続化しない。Prepare-only runはfetch transport locatorだけで動作し、GitHub API identityを要求しない。

## 公開phase interface

`create-pr`は次の2 phaseを公開する。これはinstalled skill内部のcommand名ではなく、personal HarnessまたはHumanが同じ入力、禁止事項、出力を使えるsemantic interfaceである。

- `prepare_candidate`: context固定、品質gate、documentation同期、stage確認、commit作成を行い、cleanなexact candidate SHAを返す。
- `publish_exact_candidate`: Harness経路の`READY`または通常経路の`DEFAULT_SUBMISSION_READY`に固定されたexact base/head SHAを照合し、同じSHAのpushとPR作成またはmetadata更新だけを行う。

通常の`create-pr`依頼は後方互換のdefault経路として、`prepare_candidate`と既存の提出前条件を満たす`DEFAULT_SUBMISSION_READY`を固定してから`publish_exact_candidate`を続けて実行する。このstatusはHarnessの`READY`を意味せず、独立Final reviewなどHarness固有の保証を主張しない。Harness callerは2 phaseの間にcandidate SHAを対象とするrequired gateとFinal reviewを実行し、Harnessの`READY`後はpublish phaseだけを呼ぶ。`READY`後にdefault経路を最初から再実行してはならない。

### Phase共通のartifact規則

- 入力と出力にはrepository、branch、base ref、full `base_sha`、full `head_sha`またはworking tree fingerprint、宣言済みscope、permission、適用したcontract revisionを含める。Fetchを行うphaseは`fetch_remote_refs`と、remote名、exact `fetch_transport_locator`、source/destination refspec、prune範囲、credential scope、timeoutを持つallowlistも含める。
- 完了済みartifactを再利用できるのは、同じtarget fingerprint、scope、contract revisionに結び付き、required statusを満たす場合だけとする。単なる完了申告や別SHAの結果を理由にstepを省略しない。
- File、index、commit、base、scope、project ruleを変更したstepは`TARGET_MUTATED`として旧target、新target、無効化対象、再開stepを呼び出し側へ返す。Default経路もこの結果を受け取るcallerとしてcontextを更新してから再開する。
- Blockerは`BLOCKED`として停止理由、完了済みartifact、再開step、不足inputを返す。Phase内でpermissionや仕様を補完しない。

### Fetch permissionと共通failure

`prepare_candidate`と`publish_exact_candidate`はfetch前に`fetch_remote_refs`とallowlistを検証する。通常のPR依頼では共通契約の範囲だけをpermissionへ固定し、Harness callerはrun manifestのより狭いpermissionをそのまま渡す。Fetchはremote名を再解決せず、exact `fetch_transport_locator`へ`git -c maintenance.auto=false fetch --no-tags`相当を実行し、Git object database、fetch中のlock/temporary metadata、`FETCH_HEAD`、許可済みremote-tracking ref以外を変更しない。

- Permissionがfalse、fetch transport locator、remote、refspec、prune範囲がallowlist外: `HUMAN_DECISION_REQUIRED`。
- Network、credential、Git capabilityが利用不能: `EVALUATION_DEFERRED`。
- Timeoutまたはtransient failure: 許可済みrefをread-backし、要求objectと更新が完了済みなら成功として再実行しない。未完了を確認できた同じexecution keyだけ1回retryし、確定不能なら`EVALUATION_DEFERRED`。
- `prepare_candidate`でfetch後のbaseが固定済み`base_sha`と異なる: `TARGET_MUTATED`。
- `publish_exact_candidate`でbase/headが固定targetと異なる: `READY_INVALIDATED`。

## 完了条件

- Project指定のlint、format、型check、testが成功している。
- 実行できない必須checkは理由と代替確認がPR本文に記録されている。
- `sync-docs-code`が`PASS`または`UPDATED`で、`BLOCKED`ではない。
- Commit済みの`<base>...HEAD`と未commit差分の両方を確認し、PR対象に未commit変更が残っていない。
- `prepare_candidate`完了時は、branch、base ref、full `base_sha`、full `head_sha`、cleanなworking tree、品質・documentation artifactの対象とcandidateへの適用関係を確認できる。
- Default経路または`publish_exact_candidate`完了時は、PR URL、assignee、label、base、headとremoteのexact head SHAを確認できる。

## `prepare_candidate`

### 入力

- Repositoryと作業branch
- Fetch対象のremoteとexact `fetch_transport_locator`。Default経路は現在repositoryの`origin`設定から解決する
- 明示されたbase refとfetch前に固定したfull `base_sha`。Default経路で未指定の場合はContext固定のread-only remote解決で両方を確定する
- `fetch_remote_refs` permissionと、base解決候補、選択したbaseのsource/destination refspec、credential scope、timeoutを持つallowlist
- 宣言済みscopeとcommit permission
- Working tree、index、既存HEADの状態
- 再利用候補の品質gateとdocumentation artifact

### 1. Contextを固定する

1. `git branch --show-current`と`git status --short --branch`を確認する。
2. 現在branchが空、`HEAD`、`main`、`develop`なら停止する。
3. 入力remoteの設定が保存済み`fetch_transport_locator` Evidenceと一致することを照合する。Default経路でbase refが未指定なら、permissionで許可された`git ls-remote --symref <fetch_transport_locator> HEAD`相当のnetwork readでremote defaultを確認し、解決できなければ`refs/heads/develop`、`refs/heads/main`の順に存在を確認する。選択したbase refとremoteが返したfull SHAをfetch前の`base_sha`として固定する。明示baseでは入力`base_sha`を使い、値がなければ同じlocatorへのremote readでexact refのfull SHAを固定する。
4. Base ref、`base_sha`、`refs/heads/<base>:refs/remotes/<remote>/<base>`、credential scope、timeoutが`fetch_remote_refs` allowlist内であることを確認する。Default経路のpermissionは手順3の`HEAD`、`develop`、`main`候補と、選択後のexact refspecだけを許可する。
5. `git -c maintenance.auto=false fetch --no-tags <fetch_transport_locator> refs/heads/<base>:refs/remotes/<remote>/<base>`相当で選択したbaseだけを最新化する。
6. Fetch後の`<remote>/<base>`が固定済み`base_sha`と異なる場合は`TARGET_MUTATED`を返し、新しいbaseでcontextを固定し直すまで品質gateへ進まない。一致したbaseを比較元としてcommit済み差分、working tree、index、untracked fileを確認する。
7. `.env`、認証情報、秘密情報らしいfileが含まれる場合はcommitせず、対象を報告する。

### 2. 品質gateを通す

1. ProjectのAGENTS.md、CLAUDE.md、package script、Makefile、CIから必須commandを特定する。
2. 同じtargetの有効なartifactがない変更について、該当するlint、format、型check、unit testを実行する。
3. Bug修正またはUI変更は、再現手順を実環境で再実行する。
4. 必須checkが失敗した状態ではcommitとPR作成へ進まない。

### 3. Documentationを同期する

1. 同じtargetの有効なartifactがなければ、`sync-docs-code`を同じbase、HEAD、working treeへ実行する。
2. `PASS`または`UPDATED`と関連検証の成功を確認する。
3. `UPDATED`がtargetを変更した場合は`TARGET_MUTATED`を返し、影響する品質gateとdocumentation同期を新targetで再実行する。
4. `BLOCKED`ならPRを作成しない。

### 4. Commitを作成する

1. 最終diffを変更目的ごとに分け、commit一覧を決める。
2. 各commitで対象pathだけをstageし、`git diff --cached --check`と`git diff --cached`を確認する。
3. 共通契約に従う日本語件名でcommitする。
4. Commit後、そのcommitが単独checkout時の動作可能性を満たすか確認する。後続commitへ依存する分割なら同じcommitへまとめ直す。
5. `git status --short`を確認し、PR対象の変更が残っていれば次のcommitへ進む。
6. 全commit作成後、必要な品質gateを再実行する。

### 5. Candidateを確定する

1. 入力remoteを使い、baseからHEADまでの変更file、差分量、commit一覧を確認する。
2. 必要に応じて入力remoteのbaseからHEADまでのdiffを読み、scope外変更がないことを確認する。
3. Working treeとindexがcleanで、`HEAD`が作業branchの先端であることを確認する。
4. Full `base_sha`とfull `head_sha`を取得し、品質gateとdocumentation artifactがこのcandidateまたは明示されたpre-commit targetへ正しく結び付くことを確認する。
5. `CANDIDATE_READY`としてbranch、base ref、`base_sha`、`head_sha`、scope、artifact参照、target mutation履歴を返す。

`prepare_candidate`はpushまたはPR作成を行わない。Harness経路では、この出力後にrequired gateとFinal reviewをexact candidate SHAへ実行する。

## `publish_exact_candidate`

### Remote repository identity

V1のremote repository identityはGitHub APIが返すimmutable node IDを使い、RFC 8785 JCS object `{"provider":"github","host":"<normalized-host>","repository_node_id":"<immutable-node-id>"}`として固定する。`host`は認証先APIに対応するASCII hostnameを小文字化し、末尾dotとdefault portを除いた値とする。`repository_node_id`は空でないexact API valueとし、owner、repository名、remote名、URL、branch、SHAをidentityの代用にしない。

Fixed `fetch_transport_locator`と`push_transport_locator`はAPI照会用locatorとしても使い、外部write前に同じ認証hostから各locatorのrepository node IDと現在のowner/nameを取得して対応をEvidenceへ保存する。V1はsame-repository PRだけを扱い、両transport locator、expected base repository、expected head repositoryのcanonical identityがすべてexactに一致しなければ外部write前に`EVALUATION_DEFERRED`で停止する。Fork PRは異なるremoteを1つのpublish operationへ暗黙に補わず、将来複数repository operationを設計するまで非対応とする。Immutable IDまたはlocatorとの対応を取得できない場合もURL hashやowner/nameから補作せず`EVALUATION_DEFERRED`にする。GitHub以外のproviderはV1の`publish_exact_candidate`対象外とする。

### 入力

- Repository、許可されたremote、exact `fetch_transport_locator`と`push_transport_locator`、両locatorから解決した同じcanonical repository identity、同じobjectを持つPRのexpected base/head repository identity、作業branch、PRのbase/head ref
- Full `base_sha`とfull `head_sha`
- Harness経路では同じbase/headに結び付く`READY` statusと根拠artifactへの参照、通常経路では`DEFAULT_SUBMISSION_READY`と提出前条件の結果
- Harness経路では、外部write前に確定したexact `title`、`body`、`draft`、重複なしソート済み`assignees`と`labels`を持つ`desired_submission`、そのRFC 8785 JCS bytesのSHA-256、対象transport locator、same-repository identity、branch、SHAと当該metadata生成policyに限定した`write_external_system` permission
- Canonical identity解決、同一repositoryのopen PR検索、post-write read-backだけを許可する`read_external_source` permissionと、GitHub host、API locator、credential scope、network、timeout、paid-call budgetのallowlist
- `fetch_remote_refs` permissionと、remoteの設定済みsource/destination refspec、prune範囲、credential scope、timeoutを持つallowlist
- Push、PR作成またはmetadata更新のpermission

### 禁止事項

- File編集、format、code生成、targetを変更し得る品質gateまたはdocumentation同期
- Stage、commit、amend、rebase、merge
- 入力と異なるcommitのpush
- 不一致をphase内で修正してpublishを続けること

### 手順

1. Harness経路の`READY`または通常経路の`DEFAULT_SUBMISSION_READY`が入力のbase/head SHAと同じtargetに結び付き、identity解決とPR read-backのexternal read、fetch、push、PR操作が許可されていることを確認する。Harness経路では`desired_submission`のJCS hash、metadata policyへの適合、operation限定の`write_external_system` permissionも照合する。
2. Fixed fetch/push transport locatorとexpected base/headのcanonical repository identityがすべて一致し、設定済みfetch refspecがpermission対象であることを確認する。`git -c maintenance.auto=false fetch --no-tags --prune <fetch_transport_locator>`後、local `HEAD`、作業branch先端、`<remote>/<base>`、working tree、indexをread-onlyで照合する。Harness callerは`fetch_remote_refs` permissionでlocator、設定済みsource/destination refspec、prune範囲を許可していなければ実行しない。
3. Local `HEAD`または作業branch先端が`head_sha`と異なる、working treeまたはindexがdirty、`<remote>/<base>`が`base_sha`と異なる場合はpushしない。
4. Remote headを`absent`、`exact`、`ancestor`、`diverged_or_ahead`に分類する。`ancestor`はremote headが入力`head_sha`のancestorである場合だけとし、`diverged_or_ahead`ではforce pushせず停止する。
5. Remote headが`absent`または`ancestor`の場合だけ、`git push --no-verify <push_transport_locator> <head_sha>:refs/heads/<head-ref>`相当のnon-force pushを実行する。Remote名やlocal作業branch名をcommandのsource/destinationにしない。`exact`ならpushを省略する。いずれもfixed push locatorのexact head refをread-backし、`head_sha`との一致を確認する。
6. Expected base repository identityで既存のopen PRをbase/head repository identity、base/head ref、head SHAから検索する。存在しなければexpected base/head repository identityの組へPRを作成し、すべて一致するPRが1件だけ存在すればtitle、本文、assignee、labelなどtargetを変えないmetadataだけを更新できる。Branch名とSHAが同じでもhead repository identityが異なるfork PRを更新対象にしない。Harness経路はintentの`desired_submission`をそのまま使い、phase内で再生成しない。Closedまたはmerged PRしかない場合は自動で再利用しない。
7. 通常経路では`.github/pull_request_template.md`があれば構造を維持する。なければ標準templateを使い、最新commitだけでなく全commitの差分からPR titleと本文を作る。Harness経路ではこの条件を満たすdesired submissionがintentで確定済みであることを検証し、phase内で作り直さない。
8. Expected base repository identityを明示してGitHubからPR URL、state、title、body、draft、assignee、label、base/head repository identity、base/head ref、base/head SHAをread-backし、入力と一致することを確認する。Harness経路ではremote headがexactであり、一意なopen PRのidentities、refs、SHAs、すべてのdesired fieldが一致する場合だけ完了とする。

### 不一致時の出力と再開

Local target、固定済みsame-repository identity、branch、SHA、inputの不一致またはpublish中のdriftは`READY_INVALIDATED`として、期待値、観測値、外部操作の有無を返す。追加変更、gate再実行、commit、force pushは行わない。呼び出し側はIssue/project contextへ戻り、新しいtargetで影響するverification、gate、Final reviewを完了して新しい`READY`を作る。Base/head identityが開始時から異なるfork PRはdriftではなくV1 capability不足として`EVALUATION_DEFERRED`にする。

Publish observationの`step_results`は次の意味へ固定する。`push: not_needed_exact`はcall前からremote headがexact、`performed`はexact refspecのpush後read-backがexact、`not_performed`はpush未開始、`ready_invalidated`はpush前のdrift、`unknown`は実行有無または結果不明を表す。`pull_request: created|updated`は当該write後のPR read-back成功、`not_performed`はwrite未開始、`partial`はPR作成済みまたは一部metadata write済みだがdesired state未達、`unknown`は実行有無または結果不明を表す。`read_back: exact`はremoteとPRの全required fieldがdesired stateと一致、`mismatch`は全required fieldを取得できたが不一致、`unknown`は1 fieldでも取得不能を表す。`external_effect_observed`は`performed|created|updated|partial`が1つでもあればtrue、なければfalseにする。ただし`unknown`は未観測effectの可能性を否定しない。

前段guardを含む次のphase result表を上から優先評価し、最初に一致したrowだけを採用する。Mutable metadataはtitle、body、assignees、labelsだけを指す。

| 条件 | `external_effect_observed` | 許可する`push / pull_request / read_back` | Phase result | 次の安全なstep |
| --- | --- | --- | --- | --- |
| External write開始後に実行有無、結果、またはrequired read-backが1つでも不明 | step statusから導出 | Field意味と矛盾しない値で、少なくとも1つが`unknown` | `RESULT_UNKNOWN` | 自動retryせずHuman handoff |
| External write前にtarget/input drift | false | `ready_invalidated / not_performed / {mismatch,unknown}` | `READY_INVALIDATED` | READYを失効し、新targetで再評価 |
| External effect後に全stepを確定でき、target/input drift | true | `{performed,not_needed_exact} / {created,updated,partial,not_performed} / mismatch`かつ少なくとも1 stepがeffect済み | `READY_INVALIDATED` | 追加writeせずREADYを失効し、新targetで再評価 |
| Remote `exact`、一意のopen PRがexpected identity/ref/SHA、draft、全metadataにexact | step statusから導出 | `{performed,not_needed_exact} / {created,updated,not_performed} / exact` | `SUCCEEDED` | なし |
| Remote `absent`または`ancestor`、PR `absent`、write未開始 | false | `not_performed / not_performed / mismatch` | `NOT_PERFORMED` | Exact refspecをnon-force push後、PRを作成 |
| Remote `exact`、PR `absent` | step statusから導出 | `{performed,not_needed_exact} / not_performed / mismatch` | `PARTIALLY_PERFORMED` | Pushをskipし、PRを作成 |
| Remote `exact`、一意のopen PRがexpected identity/ref/SHAとdraftにexact、mutable metadataだけ不一致 | step statusから導出 | `{performed,not_needed_exact} / {created,partial,not_performed} / mismatch` | `PARTIALLY_PERFORMED` | Pushをskipし、同じPRのmutable metadataだけをidempotentに設定 |
| Draft不一致、複数PR、diverged remote、または上記rowに一意に一致しない既知状態 | step statusから導出 | 上記のfield意味と矛盾しない値 | `RESULT_UNKNOWN` | 自動retryせずHuman handoff |

`NOT_PERFORMED`と`PARTIALLY_PERFORMED`はstep別結果とfull read-backを返す。Harness callerはREADYを失効させずobservation checkpointを保存し、budget内で表の次stepだけを開始できる。

Fetchのpermission、利用不能、timeoutはPhase共通failureへ従う。PushまたはPR操作のtimeoutで外部結果が不明な場合は同じ操作を推測retryせず、remoteとPRをread-backして確定できなければHuman handoffで停止する。

### 既存の提出操作との対応

通常経路で使っていたpush、`gh pr create`、`gh pr view`は、このphaseの照合と禁止事項を満たす場合に限って実行する。Pushはfixed `push_transport_locator`だけを対象に、`--no-verify`とexact `<head_sha>:refs/heads/<head-ref>` refspecを使い、push後のremote headが同じSHAであることを確認する。

## 標準PR本文

```markdown
## 概要

{変更の目的と結果}

## 変更内容

- {主要な変更}

## 動作確認

- {実行commandと結果}

## ドキュメント同期

- status: PASS | UPDATED
- 確認した契約: {対象}
- 更新文書: {pathまたは更新不要の理由}
- 検証: {commandと結果}

## レビュー観点

- {重点的に確認してほしい点}
```

## 失敗時

- GitHub認証が無ければ、完了済みcommitと実行すべき`gh auth login`を示して停止する。
- 品質gateまたはdocumentation同期が失敗したらPRを作らず、失敗commandと再開条件を報告する。
- Push後にPR作成だけ失敗した場合はremote headをread-backし、branch URL、観測したSHA、PR作成から再開できる条件を示す。
- Commitでは`--no-verify`を使わない。Publish pushでは未分類のpre-push hookを起動しないため、固定済みcontractどおり`--no-verify`を必須にする。

## 関連skill

- `issue-to-pr`: Issue起点の調査と実装。
- `sync-docs-code`: PR前のdocumentation同期gate。
- `git-diff`: 差分確認だけを行う。
- `git-worktree-ops`: 独立worktreeの作成とmerge後整理。
