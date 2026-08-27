# review-remediation-harness

独立reviewerを含むreview、修正、検証、fresh Final reviewを、exact targetとappend-only artifactで接続するCLI非依存workflow。Contract versionは`1.0.0`とする。

## 使う場面

- Issueまたは明示された変更scopeをreviewし、blocking findingだけを修正してPR提出可能なcandidateへ収束させるとき。
- ImplementerとFinal reviewerを分離し、test、documentation、securityなどのrequired gateを同じtargetで照合するとき。
- Personal/global skillがない環境で、repository rootの`REVIEW_HARNESS.md`からportableに実行するとき。

対象外:

- Review結果の報告だけ。変更しない場合はneutral review contractを直接使う。
- 無制限にfinding 0件を目指すloop。
- Merge、deploy、risk受容、仕様決定の自動化。
- Runner、artifact store、schema validatorが存在すると仮定すること。

## 正本と責務境界

このcontractはstage接続、state、artifact、permission、retry、stop、resumeを所有する。次の意味を再定義せず、bundle memberまたは同じsemantic contractの結果を参照する。

| Capability | Contract | Harnessでの扱い |
| --- | --- | --- |
| Issue intake、scope、branch | `issue-to-pr` | Intake固定後のsubflowを受け取り、`READY`またはblockerを返す |
| Fingerprint、finding、severity、coverage、verdict | `principle-of-programming-reviewer` | Review artifactとして保存し、gradeを上書きしない |
| Documentation同期 | `sync-docs-code` | 同じtargetの`PASS`または`UPDATED`を要求する |
| Candidate準備と提出 | `create-pr` | `prepare_candidate`と`publish_exact_candidate`だけを使う |
| Project固有lens | 任意project profileまたはproject reviewer | Finding candidateと`required_gates`だけを受け取る |
| Security | `security-audit`または同じsemantic contract | Risk trigger時だけrequired gateとして要求する |
| Merge、仕様、risk受容 | Human | Harnessから実行または代行しない |

Skill名はcapability実装の名前であり、installed skillを必須にしない。Bundle memberのcontract本文を直接実行して同じartifactを返せればよい。Required contractまたはcapabilityがなく同等性を確認できない場合は停止する。

## 入力

Run開始前に次を固定する。

- Repository identity、base ref、full base SHA、作業branch、headまたはworking tree fingerprint。
- Issueまたは明示scope、acceptance criteria、非目標、取得したexternal recordのrevisionとcontent hash。
- Base側portable bundle、任意profile、project instruction、CI/manifest。
- Permission、deadline、retry/cost limit、許可されたwrite pathとdiff上限。
- Runtimeが発行したactor、session、thread、jobの識別情報。

Issue、comment、PRなど外部sourceを取得するには、source identifier、host、credential scope、network、paid-call costを固定した`read_external_source`が必要である。Read permissionはrecordを規範入力へ採用するauthorityを与えない。

## Portable bundleを固定する

現在runではtargetのbase SHAにある`REVIEW_HARNESS.md`と`.review-harness/contracts/`を使う。Candidate側がbundle、profile、policyを変更しても、同じrunの権限やREADY条件を弱める入力へ昇格させない。Baseにentrypointがない場合は、Humanが内容、hash、適用runを承認したrun-local snapshotだけを代替にできる。

Contract本文を読む前に次を順に確認する。

1. Manifestの`contract_version`を実行側が対応できる。
2. Member pathがrepository-relativeで`.review-harness/contracts/`配下にあり、path traversalと重複がない。
3. 宣言memberがすべてregular fileとして存在し、symlinkがない。
4. Contracts directoryに未宣言fileがない。
5. 各memberをUTF-8 bytesとしてSHA-256計算し、manifestの`content_sha256`と一致する。
6. Required memberがHarness、neutral review、docs gate、Issue intake、candidate prepare/publishをすべて提供する。

欠落、重複、未宣言member、path traversal、symlink、version不一致、hash不一致が1つでもあればcontractを実行せず`EVALUATION_DEFERRED`にする。結果はmemberごとのpath、expected hash、observed hash、statusを持つ`context_resolution.bundle_integrity`へ保存する。自動validatorがなくても省略しない。

Bundle memberをpersonal wrapperなしで実行する場合、artifactのcontract/skill versionには`invocation_source: portable_bundle`、entrypointのpathとcontent hash、member pathとcontent hashを記録する。存在しないwrapper pathやpersonal skill versionを捏造せず、wrapper不在だけをblockerにしない。

## Project contextを解決する

### Read-only bootstrap

Context解決前は次の固定read-only inspectionだけを許可する。

- Base SHAのtree、blob、tracked path、file mode、Git objectの参照。
- Repository instruction、CI設定、manifest、lockfile、documentation、bundle、profileの読取。
- 許可済みexternal sourceのread-only取得。

Project script、package manager、build tool、test、hook、external diff/textconv、index refreshは実行しない。必要ならcontext解決後のexact commandとしてeffectとpermissionを判定する。

### 解決順と必要field

次の順に確認し、後順位のsourceで上順位の明示値を黙って上書きしない。

1. Base側portable bundle。
2. Base側の任意`.review-harness/profile.yaml`。
3. `AGENTS.md`、`CLAUDE.md`、承認済み設計書などのrepository instruction。
4. CI設定、package manifest、Makefileなどの決定的情報。
5. Authorityを確認したIssue、PR、外部decision。
6. Human承認run-local input。

最低限、source of truth、review scope、required lens、exact verification command、required gateとtrigger、permission、limitを解決する。各commandはexact text、effect、timeout、required servicesを持つ。複数候補からscopeとの対応を一意に説明できなければ推測実行しない。

Profile不在は`profile_status: absent`として記録するが、それだけでblockerにしない。Base側情報から全fieldを決定的に解決できれば`context_status: resolved`にできる。必須field不足は候補と不足根拠を記録して`EVALUATION_DEFERRED`、権威が同等の正本矛盾は`HUMAN_DECISION_REQUIRED`とする。

### External record authority

取得した各recordを次に分類し、author、role、source revision、content hash、根拠を保存する。

- `governing`: Base policyがauthor/roleを認可するか、Humanがこのrunへの採用を明示承認した。
- `evidence_only`: 取得は許可されるが、scope、permission、required gate、acceptance policyを変更するauthorityがない。
- `pending`: 採否がREADY条件へ影響し、Human判断が必要。

`evidence_only`をproject context変更へ使わない。`pending`が残る場合は`HUMAN_DECISION_REQUIRED`にする。

## Artifactを保存する

Canonical run artifactはJSONとし、candidate worktree外のrun storeへappend-onlyで保存する。会話履歴、PR本文、candidate内fileをrun stateの正本にしない。Orchestratorだけが`write_run_store`を持ち、role resultへruntime由来のproducer metadataとhashを付ける。

各artifactは最低限次を持つ。

```json
{
  "schema_version": "1.0",
  "artifact_type": "input_snapshot|target|evidence|review|change_request|remediation|verification|gate|blind_review|final_review|decision|run_manifest",
  "artifact_id": "<run_id>/<stage>/<monotonic_sequence>",
  "run_id": "<stable_run_id>",
  "stage": "<state_name>",
  "target_ref": {
    "artifact_id": "<target_artifact_id>",
    "artifact_path": "<relative_path>",
    "sha256": "<artifact_content_hash>"
  },
  "producer": {
    "role": "<role>",
    "instance_id": "<runtime_instance_id>",
    "context_id": "<runtime_context_id>",
    "parent_context_id": null,
    "fresh_context": false,
    "received_artifacts": []
  },
  "input_refs": [],
  "created_at": "<RFC3339_timestamp>",
  "payload": {}
}
```

`input_snapshot`と`target`だけは`target_ref: null`にできる。Target未解決中のdecisionとrun manifestも、理由をpayloadへ記録した場合だけnullを許す。その他は1つのtargetを参照する。

Artifact参照はRoot、Evidence、Stage、Manifestの順に限定する。後順位から前順位、同一artifact、自分を含むmanifest、未確定artifactを参照しない。保存前に参照先の存在、hash、同じrun、許可されたtarget generationを確認する。違反時はartifactをREADY根拠へ使わず`EVALUATION_DEFERRED`にする。

Target、Issue input、scope、permission、project rule、contract hashが変わった場合は新しいgenerationを作る。旧verification、gate、reviewを成功根拠へ流用しない。Historical artifactはreconciliationの参照だけに使える。

## Roleを分離する

| Role | 所有する責務 | 禁止事項 |
| --- | --- | --- |
| Orchestrator | State、artifact、target、budget、permission、resumeの照合 | Finding、grade、専門gate結果の捏造 |
| Initial reviewer | 初回review、coverage、required gate候補 | Code修正、外部write |
| Implementer | 確定済みrequestのscope内最小修正 | Finding資格やseverityの変更 |
| Tester | Exact command実行と結果記録 | 失敗の推測PASS、仕様判断 |
| Final reviewer | Candidate SHAのblind scan、reconciliation、最終coverage | Code修正、blind scan前のremediation説明受領 |
| Docs/Security gate | 各semantic contractの実行 | 別target結果の流用 |
| Human | 仕様、scope、risk、外部権限、merge | なし |

Final reviewerはImplementer、Initial reviewer、以前のproject reviewerと別instanceにする。Blind scanにはcandidate target、Issue/acceptance、base側規約、project contextだけを渡し、previous finding、修正説明、previous gradeを渡さない。Blind scan確定後にprevious findingを渡してreconciliationする。

Runtime由来のinstance/context metadataを取得できない、新しいinstanceを用意できない、または同じagentの自己再reviewしかできない場合は`INDEPENDENCE_BLOCKED`にする。

## Permissionとlimitを固定する

Run開始時に次を個別に記録する。

- `read_repository`: 初期true。固定read-only inspectionだけ。
- `write_run_store`: 初期true。Candidate外のappend-only storeだけ。
- `read_external_source`: 明示sourceだけtrue。Authorityは別判定。
- `write_worktree`: 変更依頼かつallowed path/limitがある場合だけtrue。
- `run_local_commands`: 解決済みexact commandだけtrue。
- `commit`、`push`、`create_or_update_pr`: 明示されたcommitまたはPR依頼の範囲だけtrue。
- `write_external_system`: 初期false。操作単位のHuman承認が必要。
- `merge`、`deploy_or_production_write`、`accept_risk_or_spec`: 初期false。Harnessはtrueにしない。

Limitsには`max_remediation_cycles: 2`、`max_same_request_attempts: 2`、`max_transient_stage_retries: 1`、required deadline、token meter値または`unsupported`、paid external call budget、allowed write paths、max changed files、max diff linesを含める。

Remediation cycleは`FIXING`直前、request別attemptは対象requestの最初のworktree変更前、transient retryは再実行前、external write attemptは外部call前にcounterを予約する。予約した試行はcrash時に戻さず、同じexecution keyを重複実行しない。Counterが上限と等しくなっただけでは進行中の試行を停止せず、その試行後も未解消で次の試行が必要になった時点で`BUDGET_EXHAUSTED`にする。

External writeはidempotency keyがあるかread-backで未実行を証明できる場合だけretryできる。成功不明のtimeoutは自動retryせず、read-backで確定できなければ`HUMAN_DECISION_REQUIRED`にする。

## Stateと実行順

次の正常系を順に実行する。各遷移はprevious state、state、stable transition ID、cause artifact、counter snapshotを持つ新しいrun manifest revisionとして保存する。

1. `CONTEXT_RESOLVING`: Bundle、input、target、project context、permission、limitを固定する。
2. `REVIEW_PENDING`: Fresh Initial reviewerがneutral reviewとrequired gate候補を返す。
3. CriticalまたはMajorがあれば`CHANGES_REQUESTED`を作り、scope/permission内だけ`FIXING`する。なければ`VERIFYING`へ進む。
4. `VERIFYING`: Working tree targetでrequired verificationを実行する。
5. `PRECOMMIT_DOCS_PENDING`: `sync-docs-code`を実行する。Mutationがあれば新targetでverificationからやり直す。
6. `CANDIDATE_COMMIT_PENDING`: `prepare_candidate`を使いcleanなcandidate SHAを固定する。
7. `TARGET_VERIFYING`: Exact candidate SHAでrequired verificationを再実行する。
8. `GATES_PENDING`: Docs、security、project gateを同じcandidate SHAで実行する。
9. `REREVIEW_PENDING`: Fresh Final reviewerのblind scan、project lens、reconciliationを行う。
10. READY条件を全て満たせば`READY`を記録する。
11. PR提出が許可されていれば`publish_exact_candidate`だけを実行する。Defaultのmonolithic `create-pr`を再実行しない。
12. Humanがreviewしてmergeする。

Targetを変更したstageは`TARGET_MUTATED`相当の結果を返し、影響するartifactをinvalidateする。Publish前後にbase/head/input driftを検出した場合はREADYを失効し、`CONTEXT_RESOLVING`から新targetを作る。

## READYと停止条件

次を全て満たす場合だけ`READY`にする。

- Bundle integrityとproject contextがresolved。
- Exact base/head SHAとclean working treeを持つcandidate targetが固定済み。
- Review coverageがCompleteで、Introduced/ExposedのCriticalとMajorが0件。
- Required verification、docs/security/project gate、project lensが同じcandidate targetで成功。
- Docs gateが`PASS`または`UPDATED`かつ`mutated_target: false`。
- External authorityに`pending`がなく、materialな仕様矛盾とunresolved blockerがない。
- Final reviewerの独立性checkが成功。

Finding 0件、A grade、100%の確信はREADY条件にしない。MinorとNitだけを理由にloopしない。

次の場合は自動継続せず対応するblockerへ遷移する。

- Target、source of truth、command、required gateを一意に固定できない: `EVALUATION_DEFERRED`または`HUMAN_DECISION_REQUIRED`。
- 仕様判断またはrisk受容が必要: `HUMAN_DECISION_REQUIRED`。
- Scope外修正が必要: `SCOPE_CHANGE_REQUIRED`。
- Test環境、権限、serviceで実行不能: `VERIFICATION_BLOCKED`。
- Fresh reviewerを確保できない: `INDEPENDENCE_BLOCKED`。
- Retry、cycle、deadline、token、cost、diff上限へ到達: `BUDGET_EXHAUSTED`。
- Required gateが未実行、失敗、利用不能、別target: `EVALUATION_DEFERRED`。

Blockerからは記録されたresume stateへだけ戻る。`EVALUATION_DEFERRED`は`CONTEXT_RESOLVING`、verification blockerは停止したverification state、independence blockerは`REREVIEW_PENDING`から再開する。Limitを黙って増やさず、変更にはHuman decision artifactを必要とする。

## Fallback

- Personal/global Harness skillなし: Root `REVIEW_HARNESS.md`を明示promptで実行する。
- Project profileなし: Base instruction、CI/manifest、Issue、Human承認inputから必須fieldを決定的に解決する。解決できればREADYへ進める。
- Codex subagentなし: 過去会話を渡さない新しいtask/sessionまたはHuman reviewerへhandoff bundleを渡す。
- Claude Code subagentなし: 別session、別CLI、Human reviewerのいずれかを使う。
- Fresh sessionなし: `INDEPENDENCE_BLOCKED`。
- Required gate実装なし: 同じsemantic contractの別実装をHumanが用意する。用意できなければ停止する。
- Worktreeなし: Cleanな単独checkoutだけを使う。Dirty共有checkoutや並行runでは停止する。
- Token meterなし: `unsupported`を記録し、cycle、retry、deadline、cost limitを適用する。

Fallbackで独立性、coverage、gate成功を偽装しない。

## 出力

- `READY`: Exact base/head、target ref、artifact hash、gate status、Final review、permission使用状況を返す。Mergeは実行しない。
- Blocker: State、原因artifact、観測値、完了済みartifact、invalidated artifact、必要なHuman action、resume stateを返す。
- `READY_INVALIDATED`: Publishを行わずexpected/observed base/head、外部操作の有無、再開先を返す。

## 検証

- Bundle memberとmanifest hashを照合した。
- 全artifactが同じrunと正しいtarget generationへ接続され、参照graphが非循環である。
- Required verificationとgateがcandidate SHAへ結び付く。
- ImplementerとFinal reviewerのinstanceが分離され、blind scanの受領artifactが制限されている。
- Critical/Major 0、coverage Complete、unresolved blockerなしを確認した。
- Retry、scope、permission、cost上限を超えた副作用がない。
- Publish時は`create-pr`のexact phase境界を使い、target mutationを行っていない。

## 関連skill

- `issue-to-pr`: Issue intakeと全体進行。
- `principle-of-programming-reviewer`: Neutral reviewの共通schemaとrubric。
- `sync-docs-code`: Documentation gate。
- `security-audit`: Risk trigger時のsecurity gate。
- `create-pr`: Candidate prepareとexact publish。
