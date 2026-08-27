# review-remediation-harness

独立reviewerを含むreview、修正、検証、fresh Final reviewを、exact targetとappend-only artifactで接続するCLI非依存workflow。Contract versionは`2.0.0`とする。

## 使う場面

- Issueまたは明示された変更scopeをreviewし、blocking findingだけを修正してPR提出可能なcandidateへ収束させるとき。
- ImplementerとFinal reviewerを分離し、test、documentation、securityなどのrequired gateを同じtargetで照合するとき。
- 専用project reviewerやproject-local Harness fileがないrepositoryを、personal/global Harnessから汎用context解決で扱うとき。

対象外:

- Review結果の報告だけ。変更しない場合はneutral review contractを直接使う。
- 無制限にfinding 0件を目指すloop。
- Merge、deploy、risk受容、仕様決定の自動化。
- Runner、artifact store、schema validatorが存在すると仮定すること。

## 正本と責務境界

このcontractはstage接続、state、artifact、permission、retry、stop、resumeを所有する。次の意味を再定義せず、対応するpersonal/global skillまたは同じsemantic contractの結果を参照する。

| Capability | Contract | Harnessでの扱い |
| --- | --- | --- |
| Issue intake、scope、branch | `issue-to-pr` | Intake固定後のsubflowを受け取り、`READY`またはblockerを返す |
| Fingerprint、finding、severity、coverage、verdict | `principle-of-programming-reviewer` | Review artifactとして保存し、gradeを上書きしない |
| Correctnessと実害riskの総合review | personal `pr-risk-reviewer`または同じsemantic contract | Initial/Final reviewの必須generic capabilityとし、finding candidateとcoverageをpoprへ渡す |
| Documentation同期 | `sync-docs-code` | 同じtargetの`PASS`または`UPDATED`を要求する |
| Candidate準備と提出 | `create-pr` | `prepare_candidate`と`publish_exact_candidate`だけを使う |
| Project固有lens | Base側repository ruleおよび任意project reviewer | Finding candidateと`required_gates`だけを受け取る |
| Security | `security-audit`または同じsemantic contract | Risk trigger時だけrequired gateとして要求する |
| Merge、仕様、risk受容 | Human | Harnessから実行または代行しない |

このHarness自身はpersonal/global skillとして利用する。関連capabilityは実際に利用したskill/referenceのpath、capability revision、content hashを記録し、required contractまたは実行capabilityがなければ別の一般reviewへ読み替えず停止する。Project repositoryへHarness skillやcontract全文を複製しない。

## 入力

Run開始前に次を固定する。

- Repository identity、base ref、full base SHA、作業branch、headまたはworking tree fingerprint。
- Issueまたは明示scope、acceptance criteria、非目標、取得したexternal recordのrevisionとcontent hash。
- Harness contractと利用するskill/referenceのcapability revision、project instruction、CI/manifest、採用したexternal governing input。
- Permission、deadline、retry/cost limit、許可されたwrite pathとdiff上限。
- Runtimeが発行したactor、session、thread、jobの識別情報。

Issue、comment、PRなど外部sourceを取得するには、source identifier、host、credential scope、network、paid-call costを固定した`read_external_source`が必要である。Read permissionはrecordを規範入力へ採用するauthorityを与えない。

## Personal contractを固定する

Run開始時に、実際に読み込んだHarness wrapperとこのreferenceのpath、contract version、capability revision、content hashを`input_snapshot`へ保存する。関連skill/referenceも同じ形式で固定し、run中に値が変わった場合は既存のreview、verification、gate、READYを流用せず`CONTEXT_RESOLVING`から再開する。

Capability revisionは次の規則で推測なしに決める。Sourceがversionを明示する場合は`declared_version`へその値、`capability_revision`へ`version:<declared_version>`を保存する。Versionを明示しない場合は`declared_version: null`、`capability_revision: sha256:<content_sha256>`とし、content hashをcanonical revisionとして使う。SemVerなどの値を補作しない。Required capabilityはpath、capability revision、content hashをすべて固定できた場合だけresolvedにでき、対応version範囲が別途宣言されている場合だけversion互換性を判定する。

Project repositoryのcandidateがHarness contract、permission、READY条件を変更または置換することはできない。Project側の入力はbase SHAにあるinstruction、CI/manifest、policyへ限定し、同じrunでcandidateが追加または変更したinstructionやpolicyを権限縮小またはgate省略へ使わない。

Harness wrapper、reference、required capabilityのpath、capability revision、content hashを固定できない、宣言済み対応範囲外のversion、読込失敗、run中のdriftがある場合は`EVALUATION_DEFERRED`にする。Project-localなHarness skill、`REVIEW_HARNESS.md`、contract snapshotの有無は検査せず、存在を要求しない。

## Project contextを解決する

### Read-only bootstrap

Context解決前は次の固定read-only inspectionだけを許可する。

- Base SHAのtree、blob、tracked path、file mode、Git objectの参照。
- Repository instruction、CI設定、manifest、lockfile、documentationの読取。
- 許可済みexternal sourceのread-only取得。

Project script、package manager、build tool、test、hook、external diff/textconv、index refreshは実行しない。必要ならcontext解決後のexact commandとしてeffectとpermissionを判定する。

### 解決順と必要field

次の順に確認し、後順位のsourceで上順位の明示値を黙って上書きしない。

1. `AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING.md`、承認済み設計書など、base側のrepository instruction。
2. Base側のCI設定、package manifest、Makefileなどの決定的情報。
3. Authorityを確認したIssue、PR、外部decision。
4. Human承認run-local input。

最低限、source of truth、review scope、required lens、exact verification command、required gateとtrigger、permission、limitを解決する。各commandはexact text、effect、timeout、required servicesを持つ。複数候補からscopeとの対応を一意に説明できなければ推測実行しない。

Base側情報から全fieldを決定的に解決できれば`context_status: resolved`にできる。必須field不足は候補と不足根拠を記録して`EVALUATION_DEFERRED`、権威が同等の正本矛盾は`HUMAN_DECISION_REQUIRED`とする。Humanが補完する場合はexact content、適用run、approval scopeを`human_approved_run_local` inputとして固定する。

`resolution_mode`は`repository_baseline|human_approved_run_local|mixed`のいずれかとする。Base側情報だけから解決した場合は`repository_baseline`を使う。Harness専用project profileや同等の複製metadataはcontext sourceとして採用しない。

すべてのrunで、Initial reviewerとFinal reviewerはpoprに加えてgeneric comprehensive review capabilityを実行する。Personal `pr-risk-reviewer`または同じsemantic contractを使い、少なくともcorrectnessと要件適合、認証・認可と情報漏えい、data integrityとmigration、並行性、後方互換性、error handlingと外部失敗、実害のあるperformance riskを変更scopeに応じて確認する。各観点のreviewed、not_applicable、unreviewedと根拠、finding candidateの失敗scenario、影響、証拠、confidence、最小修正を返す。Poprがcandidateを共通schema、severity、origin、verdictへ統合し、generic reviewer独自のgradeまたはmerge判断をHarnessの最終判定へ使わない。Risk triggerがあるsecurity監査やproject固有lensの代替にも使わない。Capability revisionを固定できない、実行不能、またはrequired観点にunreviewedが残る場合は`EVALUATION_DEFERRED`にする。

専用project reviewerがなく、信頼済みbase ruleも専用reviewerまたはproject固有lensを要求しない場合、Initial `review`は`project_results: []`、`project_coverage_status: not_required`、`generic_coverage_status: Complete`を、`blind_review`も同じ3 fieldとfreshなgeneric resultを記録する。信頼済みbase ruleが専用reviewerまたはproject固有lensを要求する場合は、そのcapabilityとcoverageもrequiredにし、利用不能なら`EVALUATION_DEFERRED`にする。専用reviewer不在をgeneric comprehensive reviewまたはrequired lensの省略理由にしない。

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
  "schema_version": "2.0",
  "artifact_type": "input_snapshot|target|evidence|target_check|review|change_request|remediation|verification|gate|blind_review|final_review|decision|run_manifest",
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

`input_snapshot`と`target`だけは`target_ref: null`にできる。Target未解決中のdecisionとrun manifestも、payloadに`target_status: unresolved`と`target_absence_reason`を記録した場合だけnullを許す。その他は1つのtargetを参照する。

Artifact参照は次の非循環layerに限定する。

1. Rootの`input_snapshot`と`target`はStageまたはManifestを参照しない。`target_ref`は必ずnullにする。
2. Evidenceの`evidence`はRootだけを参照できる。
3. Stageの`target_check`、`review`、`change_request`、`remediation`、`verification`、`gate`、`blind_review`、`final_review`、`decision`は、Root、Evidence、自分より小さい`monotonic_sequence`のStageだけを参照できる。
4. Manifestの`run_manifest`は確定済みRoot、Evidence、Stageを`artifact_refs`へ列挙し、直前Manifestだけを専用の`previous_manifest_ref`で参照できる。他artifactからManifestは参照されず、Manifestを`artifact_refs`へ含めない。

同一artifact、前方参照、自分を含むManifest、未確定artifactは参照しない。最初のManifestだけ`previous_manifest_ref: null`とし、以後は直前revisionへの共通refだけを許可する。Revision欠落、直前以外への飛越し、cycleを不正とする。保存前に参照先の存在、hash、同じrun、許可されたtarget generationを確認する。違反時はartifactをREADY根拠へ使わず`EVALUATION_DEFERRED`にする。

Target、Issue input、scope、permission、project rule、contract hashが変わった場合は新しいgenerationを作る。旧verification、gate、reviewを成功根拠へ流用しない。Historical artifactはreconciliationの参照だけに使える。

### 必須payloadとcheckpoint

`input_snapshot.payload`は`input_kind`、`trust_source`、`source_identifier`、`source_sha`、`source_revision`、`content_sha256`、秘密情報を除いたexact `content`を持つ。External recordには`authority_status`と`authority_basis`も必要である。Personal Harness contractと関連capabilityは実際のlocal path、`declared_version`、`capability_revision`、content hashを、project ruleはbase SHAとGit blob hashを記録する。

`target.payload`はpoprのtarget fingerprintを正本とし、repository identity、target source、exact base ref/SHA、head SHA、working tree status/mode/manifest、対象ならindex diff hash、PR remote、include/exclude scope、実際に使ったskill version、project ruleのsource/path/blob hashを持つ。Harness metadataとして`generation`、`previous_target_ref`、`transition_reason`を追加するが、popr fingerprintの意味は変更しない。

Stage artifactの必須payloadは次の通りとする。

| Artifact | 必須payload |
| --- | --- |
| `target_check` | `expected_target_ref`、`status: unchanged|changed`、`observed_components`、`changed_components`、`checked_at` |
| `evidence` | `evidence_kind`、`media_type`、`content_sha256`、`content_path`またはinline `content`、`redactions` |
| `review` | `popr_result`、`generic_risk_result`、`generic_coverage_status`、`project_results`、`project_coverage_status`、`blocking_finding_ids`、`required_gates`、`coverage_status` |
| `change_request` | `requests`。各要素は`review_finding|verification_failure|gate_failure`を識別する |
| `remediation` | request IDごとの`decision`、`minimal_change`、`planned_paths`、`test_plan`、`scope_effect` |
| `verification` | `commands`、各commandのexit codeと開始・終了時刻、`environment_snapshot_ref`、`output_refs`、`status`、`unverified_reason`、`mutated_target` |
| `gate` | `gate_name`、`declared_version`、`capability_revision`、`content_sha256`、`execution_status`、`decision_status`、`decision_policy`、`acceptance_policy_ref`、`evidence_ref`、`mutated_target` |
| `blind_review` | `blind_result`、`generic_risk_result`、`generic_coverage_status`、`blind_received_artifacts`、`project_results`、`project_coverage_status`、`required_gates`、`independence_check` |
| `final_review` | `blind_review_ref`、`reconciliation`、`popr_result`、`previous_review_ref`、`remediation_status`、`remediation_refs`、`independence_check` |
| `decision` | `decision_kind`と、その判断を再現する観測値、根拠ref、blocker、Human action。Context解決では下記の専用field |

Context解決の`decision.payload`は`decision_kind: context_resolution`、`resolution_mode`、`contract_status`、`contract_ref`、`considered_sources`、`selected_sources`、`authority_decisions`、`resolved_commands`、`resolved_gates`、`unresolved_inputs`を持つ。各selected source、command、gateは対応するinput/evidence refとcontent hashを含める。候補を無視して空の`unresolved_inputs`を返さない。

`run_manifest.payload`は`revision`、`previous_manifest_ref`、`state`、`previous_state`、`transition_id`、`transition_cause_ref`、`current_target_generation`、`current_target_ref`、`input_refs`、`artifact_refs`と各refの`current|historical|invalidated`、`permissions`、`limits`、`counters`、`input_source`、`contract_status`、`contract_ref`、`context_status`、`resolution_mode`、`project_context_refs`、`context_resolution_ref`、`last_completed_stage`、`resume_state`、`blocker`を持つ。`artifact_refs`へManifestを含めない。最初のrevisionだけ`previous_manifest_ref: null`を許し、以後は直前Manifestのpathとhashを参照する。

`input_source: issue`では`issue_ref`を必須にして`scope_input_ref: null`、`explicit_scope`では`scope_input_ref`を必須にして`issue_ref: null`とする。`contract_status`は`resolved|unavailable|drifted`とし、`resolved`だけhash付き`contract_ref`を持てる。`context_status: resolved`には`contract_status: resolved`、external authority確定、必須fieldの完全解決、空でない`project_context_refs`、`context_resolution_ref`を要求する。各state遷移、target generation変更、stage完了、blocker、外部副作用の前後で新revisionをappend-only保存する。

Orchestratorはtarget依存stageの開始前と完了後、外部writeの前後、resume、Final review開始前、READY判定前に`target_check`を保存する。Publish前はfetch後のbase refも、PR作成後はremoteのexact base/headも照合する。Checkは保存済みtargetだけでなく、input refs、contract/project rule hash、external source revisionも現在値と比較する。差分または再取得不能があれば旧artifactをREADY根拠へ使わず、該当blockerを記録する。

## Roleを分離する

| Role | 所有する責務 | 禁止事項 |
| --- | --- | --- |
| Orchestrator | State、artifact、target、budget、permission、resumeの照合 | Finding、grade、専門gate結果の捏造 |
| Initial reviewer | Poprとgeneric comprehensive review、coverage、required gate候補 | Code修正、外部write |
| Implementer | 確定済みrequestのscope内最小修正 | Finding資格やseverityの変更 |
| Tester | Exact command実行と結果記録 | 失敗の推測PASS、仕様判断 |
| Final reviewer | Candidate SHAのpoprとgeneric comprehensive blind scan、reconciliation、最終coverage | Code修正、blind scan前のremediation説明受領 |
| Docs/Security gate | 各semantic contractの実行 | 別target結果の流用 |
| Human | 仕様、scope、risk、外部権限、merge | なし |

Final reviewerはImplementer、Initial reviewer、以前のproject reviewerと別instanceにする。Blind scanにはcandidate target、Issue/acceptance、base側規約、project contextだけを渡し、previous finding、修正説明、previous gradeを渡さない。Blind scan確定後にprevious findingを渡してreconciliationする。

Runtime由来のinstance/context metadataを取得できない、新しいinstanceを用意できない、または同じagentの自己再reviewしかできない場合は`INDEPENDENCE_BLOCKED`にする。

## Permissionとlimitを固定する

Run開始時に次を個別に記録する。

- `read_repository`: 初期true。固定read-only inspectionだけ。
- `write_run_store`: 初期true。Candidate外のappend-only storeだけ。
- `read_external_source`: 明示sourceだけtrue。Authorityは別判定。
- `fetch_remote_refs`: 初期false。CommitまたはPR依頼で明示されたrepository identity、remote、refspec、prune範囲だけtrueにできる。
- `write_worktree`: 変更依頼かつallowed path/limitがある場合だけtrue。
- `run_local_commands`: 解決済みexact commandだけtrue。
- `commit`、`push`、`create_or_update_pr`: 明示されたcommitまたはPR依頼の範囲だけtrue。
- `write_external_system`: 初期false。操作単位のHuman承認が必要。
- `merge`、`deploy_or_production_write`、`accept_risk_or_spec`: 初期false。Harnessはtrueにしない。

Limitsには`max_remediation_cycles: 2`、`max_same_request_attempts: 2`、`max_transient_stage_retries: 1`、required deadline、token meter値または`unsupported`、paid external call budget、allowed write paths、max changed files、max diff linesを含める。

Remediation cycleは`FIXING`直前、request別attemptは対象requestの最初のworktree変更前、transient retryは再実行前、external write attemptは外部call前にcounterを予約する。予約した試行はcrash時に戻さず、同じexecution keyを重複実行しない。Counterが上限と等しくなっただけでは進行中の試行を停止せず、その試行後も未解消で次の試行が必要になった時点で`BUDGET_EXHAUSTED`にする。

External writeはidempotency keyがあるかread-backで未実行を証明できる場合だけretryできる。成功不明のtimeoutは自動retryせず、read-backで確定できなければ`HUMAN_DECISION_REQUIRED`にする。

`fetch_remote_refs`は`prepare_candidate`と`publish_exact_candidate`が要求するnetwork readとlocal Git metadata更新専用である。実行前にnormalized repository identity、remote名とURL、source/destination refspec、`prune`の有無、credential scope、timeoutをallowlistへ固定する。Fetchは`--no-tags`かつ自動maintenance無効で実行し、許可するlocal writeはGit object database、fetch中のlock/temporary metadata、`FETCH_HEAD`、宣言したremote-tracking ref namespaceだけとする。Working tree、index、local branch、tag、Git configを変更しない。`run_local_commands`や`read_repository`へ暗黙に含めない。Permissionがfalse、remote identityまたはrefspecが不一致、credentialまたはnetworkが利用不能ならfetchせず、前2者は`HUMAN_DECISION_REQUIRED`、後者は`EVALUATION_DEFERRED`にする。

Fetchのtimeoutまたはtransient failureでは、許可したrefをread-backして要求されたobjectとref更新が完了済みなら成功として再実行しない。未完了を確認でき、同じallowlistとexecution keyを使う場合だけ`max_transient_stage_retries`の範囲で1回retryできる。Fetch後にbaseまたはinput refが変わった場合は成功を流用せず`CONTEXT_RESOLVING`、READY後のpublish checkpointなら`READY_INVALIDATED`へ進む。

## Stateと実行順

次の正常系を順に実行する。各遷移はprevious state、state、stable transition ID、cause artifact、counter snapshotを持つ新しいrun manifest revisionとして保存する。

1. `CONTEXT_RESOLVING`: Harness contract、input、target、project context、permission、limitを固定する。
2. `REVIEW_PENDING`: Fresh Initial reviewerがpopr、generic comprehensive review、任意project lensとrequired gate候補を返す。
3. CriticalまたはMajorがあれば`CHANGES_REQUESTED`を作り、scope/permission内だけ`FIXING`する。なければ`VERIFYING`へ進む。
4. `VERIFYING`: Working tree targetでrequired verificationを実行する。
5. `PRECOMMIT_DOCS_PENDING`: `sync-docs-code`を実行する。Mutationがあれば新targetでverificationからやり直す。
6. `CANDIDATE_COMMIT_PENDING`: `fetch_remote_refs`とcommit permissionを確認し、`prepare_candidate`を使いcleanなcandidate SHAを固定する。
7. `TARGET_VERIFYING`: Exact candidate SHAでrequired verificationを再実行する。
8. `GATES_PENDING`: Docs、security、project gateを同じcandidate SHAで実行する。
9. `REREVIEW_PENDING`: Fresh Final reviewerのpoprとgeneric comprehensive blind scan、必要なproject lens、reconciliationを行う。
10. READY条件を全て満たせば`READY`を記録する。
11. PR提出が許可されていれば、`fetch_remote_refs`、push、PR permissionを確認して`publish_exact_candidate`だけを実行する。Defaultのmonolithic `create-pr`を再実行しない。
12. Humanがreviewしてmergeする。

Targetを変更したstageは`TARGET_MUTATED`相当の結果を返し、影響するartifactをinvalidateする。Publish前後にbase/head/input driftを検出した場合はREADYを失効し、`CONTEXT_RESOLVING`から新targetを作る。

各stageの失敗と差戻しは次のように一意に扱う。

- `VERIFYING`または`TARGET_VERIFYING`: 信頼済み期待値に結び付く修正可能な失敗は`verification_failure` requestを作って`CHANGES_REQUESTED`へ進む。期待値または仕様が不明なら`HUMAN_DECISION_REQUIRED`、環境、権限、serviceで実行不能なら`VERIFICATION_BLOCKED`へ進む。Commandが許可済みlocal writeでtargetを変更した場合、working tree検証は新targetを固定して`VERIFYING`、candidate検証は`CANDIDATE_COMMIT_PENDING`へ戻る。Base、scope、rule、inputが変わった場合は`CONTEXT_RESOLVING`へ戻る。
- `PRECOMMIT_DOCS_PENDING`: `PASS`またはsame-targetの`UPDATED`はcandidate準備へ進む。文書を実変更した場合は新targetの`VERIFYING`、project ruleまたはinputを変更した場合は`CONTEXT_RESOLVING`へ戻る。正本矛盾は`HUMAN_DECISION_REQUIRED`、実行失敗または利用不能は`EVALUATION_DEFERRED`にする。
- `GATES_PENDING`: Same-targetのrequired gate成功は`REREVIEW_PENDING`へ進む。信頼済み期待値に結び付く修正可能な`BLOCKED`は`gate_failure` requestを作って`CHANGES_REQUESTED`へ進む。仕様選択、risk受容、外部副作用判断は`HUMAN_DECISION_REQUIRED`、未実行、実行失敗、利用不能、別targetは`EVALUATION_DEFERRED`にする。許可済みgateがtargetを変更した場合は`CANDIDATE_COMMIT_PENDING`、base、scope、rule、inputを変更した場合は`CONTEXT_RESOLVING`へ戻る。
- `REREVIEW_PENDING`: Candidate project resultが新しいrequired gateを返した場合はblind artifactを保持して`GATES_PENDING`へ戻る。`New`、`Remaining`、`Regressed`のCriticalまたはMajorがありbudget内ならreview findingを参照する`change_request`を作って`CHANGES_REQUESTED`へ進む。Coverage不足は`EVALUATION_DEFERRED`、仕様矛盾は`HUMAN_DECISION_REQUIRED`、独立性不足は`INDEPENDENCE_BLOCKED`にする。新gateがtargetを変更した場合はblind artifactをinvalidateし、新targetでFinal reviewを最初から行う。

`CHANGES_REQUESTED`へ入る前にsource review、verification、gate artifactを参照する`change_request`を確定する。Expected behaviorが不明、scopeまたはwrite permission外、次のattemptがlimit超過の場合は`FIXING`へ進まず、それぞれHumanまたは対応blockerへ遷移する。

## READYと停止条件

次を全て満たす場合だけ`READY`にする。

- Harness contract hashとproject contextがresolved。
- Exact base/head SHAとclean working treeを持つcandidate targetが固定済み。
- Poprとgeneric comprehensive reviewのcoverageがCompleteで、Introduced/ExposedのCriticalとMajorが0件。
- Required verification、docs/security/project gateと、解決済みrequired lensが同じcandidate targetで成功。専用project lensが不要なrunも`project_coverage_status: not_required`、`generic_coverage_status: Complete`でなければならない。
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
- Required gateが未実行、実行失敗、利用不能、別target、または修正可能なfailureへ分類できない: `EVALUATION_DEFERRED`。信頼済み期待値へ結び付く修正可能なfailureは`CHANGES_REQUESTED`へ進む。

Blockerからは記録されたresume stateへだけ戻る。`EVALUATION_DEFERRED`は`CONTEXT_RESOLVING`、verification blockerは停止したverification state、independence blockerは`REREVIEW_PENDING`を再開候補にするが、次の再検証に成功するまで遷移しない。Limitを黙って増やさず、変更にはHuman decision artifactを必要とする。

Resumeでは次を順に行う。

1. 最大revisionのManifestを読み、`previous_manifest_ref`を直前revisionへ順に辿って欠落、飛越し、cycleがないことを確認する。各Manifestのcontent hash、transition、counter、全artifact refに加えて`project_context_refs`と`context_resolution_ref`のhashを検証し、`artifact_refs`にManifestが含まれないことも確認する。
2. Repository identity、base ref/SHA、branch、head SHA、working tree status/mode/manifestをread-onlyで再取得する。
3. External authoritative inputをsourceから再取得し、revisionとcontent hashを照合する。権限または安定したrevisionがなく再検証できなければ成功扱いしない。
4. 新しい`target_check`を現在のtarget、input、contract/project rule、external revisionへ接続して保存する。
5. Manifestのcurrent target generationと再取得値を比較し、driftがあれば新target/input snapshotを作り、依存artifactを`invalidated`として`CONTEXT_RESOLVING`へ戻す。
6. Driftがない場合だけ、同じtarget generation、input refs、contract hashを持つ完了artifactを再利用する。外部副作用もbranch、commit、PRの実状態をread-onlyで照合する。
7. `last_completed_stage`を単独cursorにせず、manifest stateと確定済みtransitionから状態機械を再評価する。検証不能、manifest chain破損、曖昧な実状態は`EVALUATION_DEFERRED`または`HUMAN_DECISION_REQUIRED`にする。

## Fallback

- Project-local Harness skill/entrypointなし: 正常系。Personal/global Harnessを使い、project側に複製しない。
- Repository context不足: Base instruction、CI/manifest、governing Issueから必須fieldを決定的に解決する。未解決fieldはHuman承認run-local inputで補完し、用意できなければ停止する。
- Project reviewerなし: Personal `pr-risk-reviewer`または同じsemantic contractでgeneric comprehensive reviewを行う。信頼済みruleが専用lensを要求せず、generic coverageがCompleteならproject coverageは`not_required`にできる。
- Codex subagentなし: 過去会話を渡さない新しいtask/sessionまたはHuman reviewerへhandoff bundleを渡す。
- Claude Code subagentなし: 別session、別CLI、Human reviewerのいずれかを使う。
- Fresh sessionなし: `INDEPENDENCE_BLOCKED`。
- Required gate実装なし: 同じsemantic contractの別実装をHumanが用意する。用意できなければ停止する。
- Git remote fetch不可: 許可済みremote/refへのnetwork、credential、Git metadata writeを回復して再開する。Base/ref一致を再検証できなければcandidate準備またはpublishを続けない。
- Worktreeなし: Cleanな単独checkoutだけを使う。Dirty共有checkoutや並行runでは停止する。
- Token meterなし: `unsupported`を記録し、cycle、retry、deadline、cost limitを適用する。

Fallbackで独立性、coverage、gate成功を偽装しない。

## 出力

- `READY`: Exact base/head、target ref、artifact hash、gate status、Final review、permission使用状況を返す。Mergeは実行しない。
- Blocker: State、原因artifact、観測値、完了済みartifact、invalidated artifact、必要なHuman action、resume stateを返す。
- `READY_INVALIDATED`: Publishを行わずexpected/observed base/head、外部操作の有無、再開先を返す。

## 検証

- Harness wrapper/reference、generic comprehensive reviewer、required capabilityのpath、capability revision、content hashを固定した。
- 全artifactが同じrunと正しいtarget generationへ接続され、参照graphが非循環である。
- Required verificationとgateがcandidate SHAへ結び付く。
- ImplementerとFinal reviewerのinstanceが分離され、blind scanの受領artifactが制限されている。
- Critical/Major 0、poprとgeneric comprehensive coverage Complete、unresolved blockerなしを確認した。
- Retry、scope、permission、cost上限を超えた副作用がない。
- Publish時は`create-pr`のexact phase境界を使い、target mutationを行っていない。

## 関連skill

- `issue-to-pr`: Issue intakeと全体進行。
- `principle-of-programming-reviewer`: Neutral reviewの共通schemaとrubric。
- `sync-docs-code`: Documentation gate。
- `security-audit`: Risk trigger時のsecurity gate。
- `create-pr`: Candidate prepareとexact publish。
