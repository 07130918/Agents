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
- Full runner、state orchestrator、agent launcherが存在すると仮定すること。

## 正本と責務境界

このcontractはstage接続、state、artifact、permission、retry、stop、resumeを所有する。次の意味を再定義せず、対応するpersonal/global skillまたは同じsemantic contractの結果を参照する。

| Capability | Contract | Harnessでの扱い |
| --- | --- | --- |
| Issue intake、scope、branch | `issue-to-pr` | Intake固定後のsubflowを受け取り、`READY`またはblockerを返す |
| Fingerprint、finding、severity、coverage、verdict | `principle-of-programming-reviewer` | Review artifactとして保存し、gradeを上書きしない |
| Correctnessと実害riskの総合review | personal `pr-risk-reviewer`または同じsemantic contract | Initial/Final reviewの必須generic capabilityとし、finding candidateとcoverageをpoprへ渡す |
| Documentation同期 | `sync-docs-code` | 同じtargetの`PASS`または`UPDATED`を要求する |
| Candidate準備と提出 | `create-pr` | Harness内では`prepare_candidate`だけを使い、`READY`後の`publish_exact_candidate`は呼び出し元へ返す |
| Project固有lens | Base側repository ruleおよび任意project reviewer | Finding candidateと`required_gates`だけを受け取る |
| Security | `security-audit`または同じsemantic contract | Risk trigger時だけrequired gateとして要求する |
| Merge、仕様、risk受容 | Human | Harnessから実行または代行しない |

このHarness自身はpersonal/global skillとして利用する。関連capabilityは実際に利用したskill/referenceのpath、capability revision、content hashを記録し、required contractまたは実行capabilityがなければ別の一般reviewへ読み替えず停止する。Project repositoryへHarness skillやcontract全文を複製しない。

## 入力

Run開始前に次を固定する。

- Run store用repository identity、base ref、full base SHA、作業branch、headまたはworking tree fingerprint。
- Issueまたは明示scope、acceptance criteria、非目標、取得したexternal recordのrevisionとcontent hash。
- Harness contractと利用するskill/referenceのcapability revision、project instruction、CI/manifest、採用したexternal governing input。
- Permission、deadline、retry/cost limit、許可されたwrite pathとdiff上限。
- Runtimeが発行したactor、session、thread、jobの識別情報。

Issue、comment、PRなど外部sourceを取得するには、source identifier、host、credential scope、network、paid-call costを固定した`read_external_source`が必要である。Read permissionはrecordを規範入力へ採用するauthorityを与えない。

## Personal contractを固定する

Run開始時に、実際に読み込んだHarness wrapperとこのreferenceのpath、contract version、capability revision、content hashを`input_snapshot`へ保存する。関連skill/referenceも同じ形式で固定し、run中に値が変わった場合は既存のreview、verification、gate、READYを流用せず`CONTEXT_RESOLVING`から再開する。

Capability revisionは次の規則で推測なしに決める。`required_capability`は`content_format: jcs_json`、exact `content: {"capability_name":"<nonempty>","declared_version":"<nonempty>"|null,"sources":[{"canonical_realpath":"<absolute_realpath>","content":"<exact_UTF-8_text>","content_sha256":"<sha256>"}]}`、`source_identifier: skill:<capability_name>`とする。`sources`は実際に読み込んだ全sourceをrealpathのUTF-8 byte順で重複なく持ち、各hashを保存textのUTF-8 bytesと一致させる。Sourceがversionを明示する場合は`source_revision`へ`version:<declared_version>`を保存する。Versionを明示しない場合は`declared_version: null`、`source_revision: sha256:<content_sha256>`とし、source実体を含むouter content hashをcanonical revisionとして使う。SemVerなどの値を補作しない。Required capabilityはidentity、path、revision、content hashをすべて固定できた場合だけresolvedにでき、対応version範囲が別途宣言されている場合だけversion互換性を判定する。

Project repositoryのcandidateがHarness contract、permission、READY条件を変更または置換することはできない。Project側の入力はbase SHAにあるinstruction、CI/manifest、policyへ限定し、同じrunでcandidateが追加または変更したinstructionやpolicyを権限縮小またはgate省略へ使わない。

Harness wrapper、reference、required capabilityのpath、capability revision、content hashを固定できない、宣言済み対応範囲外のversion、読込失敗、run中のdriftがある場合は`EVALUATION_DEFERRED`にする。Project-localなHarness skill、`REVIEW_HARNESS.md`、contract snapshotの有無は検査せず、存在を要求しない。

## Project contextを解決する

### Read-only bootstrap

Context解決前は次の固定read-only inspectionだけを許可する。

- Base SHAのtree、blob、tracked path、file mode、Git objectの参照。
- Current refとHEAD、index entryとindex diff、working tree statusの参照。
- 対象scope内のtracked/untracked path、file mode/type、symlink target、raw content bytesとfilterなしcontent hashの参照。
- Repository instruction、CI設定、manifest、lockfile、documentationの読取。
- 許可済みexternal sourceのread-only取得。

Git inspectionではoptional lockとindex refreshを無効化し、external diff、textconv、clean/smudge filter、hook、pager、`hash-object -w`などwriteまたは外部processを起動し得る機能を使わない。Working tree contentはfilesystemからraw bytesとして読み、Gitでhashする場合はfilterを明示的に無効化する。Project script、package manager、build tool、testは実行しない。必要ならcontext解決後のexact commandとしてeffectとpermissionを判定する。

### 解決順と必要field

次の順に確認し、後順位のsourceで上順位の明示値を黙って上書きしない。

1. 対象pathへ適用されるbase側の`AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING.md`と、それらが正本として明示的に参照する文書。参照されていない設計書は自動採用せず、`evidence_only`またはHuman承認run-local inputとして扱う。
2. Base側のCI設定、package manifest、Makefileなどの決定的情報。
3. Authorityを確認したIssue、PR、外部decision。
4. Human承認run-local input。

最低限、source of truth、review scope、required lens、exact verification command、required gateとtrigger、permission、limitを解決する。各commandはexact text、effects、timeout、required servicesを持つ。複数候補からscopeとの対応を一意に説明できなければ推測実行しない。

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

Artifact writer/validatorはpersonal Codex skill内の`~/.agents/skills/review-remediation-harness/`へ配置し、`uv run --isolated --frozen --project ~/.agents/skills/review-remediation-harness review-harness-artifacts <command>`で実行する。既定のruntime state rootは`~/.agents/state`、run rootは`<runtime_state_root>/review-harness/<repository_id>/<run_id>/`とする。Testまたは明示的なrun-local隔離で`--state-root`を変更できるが、writerとrecoveryはcandidate worktreeのabsolute realpathを受け取り、run rootがcandidate配下なら書き込まず停止する。Project repositoryへartifact tool、state、Harness専用fileを配置しない。

CLIの責務は次に固定する。

- `canonicalize`: Strict JSON parseとJCS serializationを行い、canonical bytesのSHA-256、byte length、content-addressed object pathを返す。Ledgerを変更しない。
- `append`: Version付きbatchをpreflight validationし、single-writer transaction、object/Manifest install、HEAD CAS、commit markerまで実行する。State選択、producer metadata、外部source contentを補作しない。
- `validate`: Existing runをread-onlyで検査する。Active transactionを完了せず、recovery reportを含むfileを作らない。破損時は同じschemaのreport valueを標準出力へ返せる。
- `recover`: Commit markerのないactive descriptorを検査し、一意に完了できる1 transactionだけを完了する。完了不能またはledger破損ではcanonical ledgerを変更せず、ledger外recovery reportをexclusive createする。Rollback、repair、orphan objectの再接続をしない。

Tool version 1.0のappend batchは次のexact top-level shapeを使う。`writes`はwrite index順で、`manifest`を最後の1件だけ持つ。Callerはdestination path、SHA-256、byte length、write indexを指定せず、writerがcanonical bytesから導出する。`artifact_json`の`content`はJSON object、`attachment|evidence_bytes`の`content_base64`はraw bytesのcanonical base64表現とし、両形式を同じentryへ混在させない。Artifact envelope、sequence、ref、timestamp、producerはOrchestratorが完全な値を渡し、writerは推測補完しない。

```json
{
  "batch_version": "1.0",
  "transaction_id": "<transaction_id>",
  "expected_head": {"revision": -1, "manifest_ref": null},
  "writes": [
    {
      "kind": "object",
      "content_type": "artifact_json",
      "artifact_id": "<artifact_id>",
      "content": {}
    },
    {
      "kind": "object",
      "content_type": "attachment|evidence_bytes",
      "artifact_id": null,
      "content_base64": "<base64>"
    },
    {
      "kind": "manifest",
      "content_type": "artifact_json",
      "artifact_id": "<manifest_artifact_id>",
      "content": {}
    }
  ]
}
```

Immutable descriptorは`descriptor_version: 1.0`、repository/run/transaction ID、expected/proposed head、next Manifest revision、sequence start/end、完全なwrite setを持つ。Write set entryは`write_index`、`kind`、`staged_path`、`destination_path`、`sha256`、`byte_length`、`artifact_id`、`content_type`だけを持つ。Commit markerは`marker_version: 1.0`、transaction ID、descriptor SHA-256、committed headだけを持つ。Tool-owned batch、descriptor、markerはunknown fieldを拒否する。ArtifactのContract version `2.0.0`と保存schema `2.0`は別定数であり、同じ文字列へ丸めない。

ToolはPOSIXのadvisory file lock、directory-relative no-follow open、directory/file sync、atomic no-replace install、atomic replaceを保証できるDarwin/Linux filesystemだけを対象にする。Writerはrun namespaceを作成する前にruntime state root直下の隔離probeで各primitiveを実測し、finallyで既知probe fileとdirectoryを削除する。Probe実行またはcleanup、primitive、durabilityを保証できないruntime/filesystemでは`capability_unavailable`としてrun ledgerへ書き込まず停止する。Distributed lock、network filesystem、Windows互換を推測実装しない。

Path解決時にstate rootとcandidate worktreeのfilesystem identity (`st_dev`, `st_ino`)を固定する。以後は同じstate root identityをdirectory descriptorで再確認し、run storeとrecovery report storeの全directory componentをdescriptor-relativeに開くたびcandidate identityへ入っていないことを確認する。Resolve後のrenameまたはpath置換でcandidate inodeが将来のstore pathへ移動した場合は、candidate内へ書き込まず停止する。

Schema 2.0のJSON bytesは[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)のJSON Canonicalization Scheme (JCS)で直列化する。UTF-8、BOMなし、末尾改行なしとし、object key順、string escape、Unicode、number表現、空白はJCSへ従う。Duplicate key、lone surrogate、NaN、Infinity、I-JSONで正確に表せないnumberは拒否し、losslessな大整数やdecimalが必要ならschemaでstringとして表す。Hashはこの保存済みcanonical bytesへSHA-256を適用する。Writerとvalidatorが同じ論理値を別bytesで受理する独自canonical化を定義しない。

`input_snapshot`のvalidatorは保存済み`content`と`content_sha256`、locator、authority fieldの内部整合を検証する。保存値が外部sourceの全文と一致するかの再取得、credential、authority判断はOrchestratorとtarget checkerの責務であり、offline validatorが成功を補作しない。再取得結果を固定できなければHarnessは別stageで`EVALUATION_DEFERRED`にする。

同様にartifact validatorは`popr_target_fingerprint`を変換せず保持し、required top-level shape、共通ref、保存済みattachmentのhash/length/Git OID bindingを検証するが、poprが所有するtarget source、base/head、working treeの意味論を再定義しない。Current repositoryからの再取得とfingerprint全componentのsemantic consistencyは#50のtarget checkerが所有する。Target checkerの結果なしにartifact validator単独の成功をexact targetまたはREADYの保証として扱わない。

Run store用repository identityはpopr fingerprintへ暗黙に含めない。Bootstrapで`git rev-parse --path-format=absolute --git-common-dir`相当からGit common directoryのabsolute realpathを取得し、JCS value `{"identity_kind":"git_common_dir_realpath","identity_value":"<absolute-realpath>"}`を`input_kind: repository_identity`のinput snapshotとして固定する。取得不能、non-Git、またはrun途中のidentity変更は推測補完せず`EVALUATION_DEFERRED`にする。Worktree pathではなくGit common directoryを使うため同一repositoryのworktreeは同じidentityになり、repositoryを移動した場合は別run namespaceになる。Fetch、push、PRに使うremote repository identityはcreate-pr contractとpermission setが別途所有し、このlocal store identityをremote identityへ変換しない。

各artifactは最低限次を持つ。

```json
{
  "schema_version": "2.0",
  "artifact_type": "input_snapshot|target|evidence|target_check|review|change_request|remediation|verification|gate|blind_review|final_review|decision|run_manifest",
  "artifact_id": "<run_id>/<stage>/<monotonic_sequence>",
  "run_id": "<stable_run_id>",
  "monotonic_sequence": 0,
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
    "model": null,
    "received_artifacts": []
  },
  "input_refs": [],
  "created_at": "<RFC3339_timestamp>",
  "payload": {}
}
```

`input_snapshot`と`target`だけは`target_ref: null`にできる。Target未解決中のdecisionとrun manifestも、payloadに`target_status: unresolved`と`target_absence_reason`を記録した場合だけnullを許す。その他は1つのtargetを参照する。

`producer.role`は`orchestrator|initial_reviewer|project_reviewer|implementer|tester|final_reviewer|docs_gate|security_gate|ci|human`のいずれかとする。`instance_id`、`context_id`、親子関係、`fresh_context`、`received_artifacts`はOrchestratorがruntime metadataから付与する。`model`はruntimeが返すexact model ID、Humanまたは取得不能時はnullとし、取得不能時は`model_unavailable_reason`を必須にする。`received_artifacts`はcommon refを`artifact_id`順に並べる。

Artifactの共通refは`artifact_id`、run directory相対の`artifact_path`、保存済みbytesの`sha256`だけを持つ。`target_ref`、`input_refs`、`previous_manifest_ref`、payload内の`*_ref`と`*_refs`はこの型を使う。例外は`run_manifest.artifact_refs`で、各要素を`{"ref": <common_ref>, "lifecycle_status": "current|historical|invalidated", "invalidation_reason_ref": <common_ref|null>}`とする。`invalidated`だけ`invalidation_reason_ref`を必須にし、他statusではnullにする。

`repository_id`は保存済みrepository identity inputの`content`をRFC 8785 JCS bytesへ直列化し、そのSHA-256から`sha256-<小文字16進64文字>`として作る。`run_id`と`transaction_id`は`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`、`artifact_id`は`<run_id>/<state>/<sequence>`とし、`state`は本contractのstate名、`sequence`は先頭0なしの10進非負整数で`monotonic_sequence`と一致させる。通常artifactはartifact IDのstate segmentとenvelopeの`stage`を一致させ、Manifestは両方を`payload.state`とも一致させる。SequenceとManifest revisionは0以上`9007199254740991`以下のI-JSON exact integerに限定する。`monotonic_sequence`はManifestを含む全artifactでrun-globalに一意かつ0から隙間なく増加させ、既存committed artifactの最大値より1大きい値から採番する。同じtransactionではwrite setの非Manifest artifactをsequence昇順に並べ、Manifestへ最大sequenceを割り当てる。Manifest revisionは0から1ずつ増える独立counterであり、sequenceと同値である必要はない。Common refの`sha256`は小文字16進64文字に限定する。`artifact_path`とrun-storeを読むすべての`content_path`は`/`区切りの相対pathとし、各segmentを`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`へ限定する。Absolute path、空segment、`.`、`..`、backslash、NULを拒否する。

Writerとvalidatorはrun rootを一度realpathで固定し、run-store pathを文字列連結だけで開かない。各componentをsymlink followなしで辿り、正規化後も同じrun root配下であること、最終objectが通常fileであることを確認する。Artifactの`run_id`、`artifact_id`先頭、実際のrun directoryを一致させ、別runへの参照を拒否する。Repository相対の具体的なfile pathはabsolute、空segment、`.`、`..`、NULを拒否してrepository root配下へ限定するが、targetとして記録されたsymlink自体のtypeとlink targetはfollowせず観測できる。例外として、popr target fingerprintの`scope.included_paths`では配列全体がexactに`["."]`の場合だけ`.`をrepository全体を表すroot sentinelとして許可する。他entryとの併用、`excluded_paths`、artifact path、attachment path、run-store pathで`.`を許可しない。Local skill pathやexternal source identifierはrun-store pathとしてdereferenceせず、取得済みcontentをinput snapshotへ保存する。

Lifecycleは直前Manifestから次のManifestへ不可逆に遷移させる。`current -> current|historical|invalidated`、`historical -> historical|invalidated`、`invalidated -> invalidated`だけを許可し、`historical|invalidated`から`current`へ戻さない。新artifactは原則`current`で初出させる。Target generationを切り替える同じManifestに初出する旧target boundの`target_check`とtransition Evidenceだけは、`transition_cause_ref`から到達でき、expected/observed target refsを検証できる場合に、許可済みremediationなら`historical`、governing input、permission、contract、project rule、scopeの変更なら`invalidated`で初出できる。`current`はcurrent target generation、current input refs、permission set、contract/project rule hashが一致し、supersedeされていないartifactに限定する。`historical`と`invalidated`はいずれもREADY根拠へ使わず、`historical`は元targetに対するvalidな監査またはreconciliation履歴、`invalidated`は依存条件の破壊または検証不能を表す。

| Event | 対象artifact | 次status |
| --- | --- | --- |
| 同じtarget/inputでstageを意図的に再実行 | supersedeされたattemptと専用evidence | `historical` |
| 許可済みremediationなど、完全なtransition evidenceを伴うtarget generation更新 | 旧generationのtarget、review、change request、remediationとreconciliationに必要なevidence | `historical` |
| 上記generation更新 | 旧generationのverification、gate、blind/final review、READY decisionと、その成功だけを支えるevidence | `invalidated` |
| Governing input、contract、project rule、scope、permissionの変更 | 旧input snapshotと旧target | `historical` |
| 上記変更 | 旧generationへ属するすべてのtarget依存EvidenceとStage | `invalidated` |
| 想定外のtarget/input driftまたは依存sourceの再取得不能 | 影響を受ける構造的にvalidなartifactとその依存artifact | `invalidated` |

`historical`へ送らなかった旧generation artifactを暗黙に再利用しない。Manifestの`transition_cause_ref`は、変更を観測した先行`target_check`、Stage、またはEvidenceを常に参照する。`invalidation_reason_ref`はevent別unionとし、governing input、permission、contract、project rule、scopeの変更では変更後Root inputのcommon ref、それ以外のtarget更新、drift、再取得不能では原因を記録した先行StageまたはEvidenceのcommon refだけを許す。変更後Root inputを理由にする場合も、そのinputのexpected/observed差分を持つ`transition_cause_ref`がなければ遷移できない。`historical`では`invalidation_reason_ref: null`とし、遷移理由をManifestの`transition_cause_ref`だけで示す。Validatorは直前Manifestとの差分、artifact type、event、target/input dependencyを照合して表以外の遷移を拒否する。

Hash、schema、DAGに適合しないcandidate artifactはtransactionのinstall前に拒否し、lifecycleへ追加しない。Committed canonical chainに同じ不整合を発見した場合はledger corruptionであり、`invalidated`へ遷移させず、同ledgerへ追記しない。後述のledger外recovery reportを保存して停止する。

Artifact参照は次の非循環layerに限定する。

1. Rootの`input_snapshot`は`input_refs: []`とし、他artifactを参照しない。`target`の`input_refs`はcurrent `repository_identity` inputのcommon ref 1件だけを持ち、`payload.repository_identity_ref`とexactに一致させる。Stage、Evidence、Manifestは参照しない。両typeの`target_ref`は必ずnullにする。
2. Evidenceの`evidence`はRootだけを参照できる。
3. Stageの`target_check`、`review`、`change_request`、`remediation`、`verification`、`gate`、`blind_review`、`final_review`、`decision`は、Root、Evidence、自分より小さい`monotonic_sequence`のStageだけを参照できる。
4. Manifestの`run_manifest`は確定済みRoot、Evidence、Stageを`artifact_refs`へ列挙し、直前Manifestだけを専用の`previous_manifest_ref`で参照できる。他artifactからManifestは参照されず、Manifestを`artifact_refs`へ含めない。

同一artifact、前方参照、自分を含むManifest、別transactionの未確定artifactは参照しない。例外として、同じimmutable transaction descriptorのwrite set内で、参照先が参照元より小さい`write_index`と`monotonic_sequence`を持ち、canonical destination、exact bytes、hash、lengthがdescriptorに固定されたRoot、Evidence、Stageへのcommon refを許可する。これにより次generationのtarget/inputを先にstageし、それを参照する`target_check`と、そのcheckをcauseにするManifestを同一transactionでcommitできる。Writerはinstall前にwrite set全体のtype layer、順序、common ref、hash、cycleを検証し、1件でも不一致ならtransaction全体を拒否する。

最初のManifestだけ`previous_manifest_ref: null`、`previous_state: null`、`state: CONTEXT_RESOLVING`とし、以後は直前revisionへの共通refと直前Manifestのexact stateを`previous_state`へ要求する。Revision欠落、直前以外への飛越し、cycle、初回以外のnull previous stateを不正とする。保存前に参照先の存在または同一descriptor内の先行entry、hash、同じrun、許可されたtarget generationを確認する。違反時はartifactをREADY根拠へ使わず`EVALUATION_DEFERRED`にする。

Canonical ledgerへのpublishはatomicかつexclusiveにする。Run root配下の物理layoutを次へ固定する。`HEAD.json`、`manifests/`、`objects/sha256/`だけをcanonical namespaceとし、`writer.lock`と`transactions/`は復旧用namespaceであってledger artifactではない。

```text
<run-root>/
  HEAD.json
  writer.lock
  manifests/<revision>.json
  objects/sha256/<hash先頭2文字>/<残り62文字>
  transactions/<transaction_id>/descriptor.pending
  transactions/<transaction_id>/descriptor.json
  transactions/<transaction_id>/staged/<write_index>
  transactions/<transaction_id>/head.pending
  transactions/<transaction_id>/committed.pending
  transactions/<transaction_id>/committed.json
```

非Manifest artifactの`artifact_path`とattachment/evidenceの`content_path`は保存bytesのSHA-256から導出した上記object pathと完全一致させる。Manifestのpathは10進非負整数のrevisionから`manifests/<revision>.json`と一意に導出し、`HEAD.json`と`previous_manifest_ref`のcommon refもこのpathと保存済みJCS bytesのhashを使う。別path、hash prefix不一致、leading zero付きrevision、拡張子違いをaliasとして受理しない。Canonical namespaceを再帰列挙するときはこのlayout外を含めず、transaction staged bytesをobjectとして数えない。

Commit pointはManifest fileのinstallではなく、`writer.lock`のexclusive lock内で唯一の`HEAD.json`をexpected revision/hashからproposed Manifest revision/hashへcompare-and-swap相当で更新した時点とする。Headから到達するManifestと、その`artifact_refs`から到達するimmutable objectだけがcommitted artifactである。Object storeに存在してもcommitted Manifestから到達しないbytesはledger artifactでもlifecycle対象でもなく、診断用のuncommitted objectとしてREADYまたはresumeへ使わない。

`HEAD.json`はJCSの`{"revision":<integer>,"manifest_ref":<common_ref|null>}`とし、初期値は`revision: -1`かつnull、最初のManifest revisionは0とする。Bootstrapは必要directoryと初期headを同じrun lock下で作成し、各fileと親directoryをdurable syncできないruntimeではwriterを利用不能として停止する。

Writerはlockを取得してheadとcommitted最大sequenceを読んだ後、`transactions/<transaction_id>/staged/<write_index>`へ全write bytesを0からのwrite index順でexclusive createし、各fileをdurable syncする。次にJCS descriptorを`descriptor.pending`へexclusive create、file syncし、そのexact bytesを`descriptor.json`へatomic no-replace installしてtransaction directoryをsyncする。Validな`descriptor.json`をactive transactionの境界とし、descriptorより先にcrashしたdirectoryまたはpending fileはactiveとは扱わないが、transaction identityを安全に復元できない残骸としてread-only validationとrecoveryの両方で`transaction_unrecoverable`にする。自動commit、cleanup、healthy判定は行わない。Descriptorは`transaction_id`、expected/proposed head、next Manifest revision、割り当てたsequence範囲、write index順の完全なwrite setを持つ。各write set entryは`kind: object|manifest`、staged path、canonical destination path、SHA-256、byte length、artifact IDまたはnull、content typeを持ち、artifact JSONだけでなくtarget attachmentとEvidence bytesもすべて列挙する。Manifest entryは最後のwrite indexかつ1件だけとする。

Descriptorと全staged bytesを再検証した後、objectをwrite index順、Manifestを最後にcanonical destinationへsource-preservingなatomic no-replace installで複製し、各fileと親directoryをsyncする。`committed.json`がdurableになるまでstaged bytesを消費、移動、上書き、削除しない。Install primitiveがsource preservation、no-replace、durabilityを保証できないruntimeでは停止する。同じdestinationが既に存在する場合はexact bytes、hash、length一致時だけidempotent successとし、不一致なら停止する。最後にlock内で`HEAD.json`のexact JCS bytesをexpected headと再照合し、proposed headをtransaction directoryの`head.pending`へexclusive create、file sync、atomic replaceで`HEAD.json`へ移動、run root directory syncの順でCAS更新する。既存のpending headはdescriptorのproposed headとexact bytes/hashが一致する場合だけ再利用する。各revisionは1 Manifest、各Manifestは最大1 successorとする。

Head CAS成功後はdescriptorを変更せず、同じ`transaction_id`、descriptor hash、committed headを持つJCS markerを`committed.pending`へexclusive create、file syncし、そのexact bytesをimmutable `committed.json`へatomic no-replace installしてtransaction directoryをsyncする。既存の`committed.pending`はdescriptorから導出したexact JCS bytes、hash、lengthが一致する場合だけ再利用して`committed.json`へinstallし、不一致なら停止する。Validな`committed.json`だけをcommit markerとする。新transaction開始前とresumeでは、まずcommit markerのないactive descriptorをすべて検査する。Active descriptorが1件だけでcurrent headがexpected headなら、staged bytes、write set、既存object、proposed Manifestの全hashが一致する場合だけ不足installとhead CASを続行できる。Current headがproposed headならcommit済みとして同じhashを照合しcommit markerを追記する。それ以外、active descriptor複数、不足または不一致bytes、unknown headでは自動完了または削除をせず`EVALUATION_DEFERRED`にする。Marker済みdescriptorもhashを検証し、crashしたtransactionと無関係なuncommitted objectは診断に列挙するがledgerへ再接続しない。

Transactionを安全に完了またはcommit済みと確認した後、`HEAD.json`、`manifests/`、`objects/sha256/`を検査する。同一revisionの複数file、同じprevious manifestを指すfork、transactionで説明できないorphan Manifest、欠落、飛越し、sequence重複/欠落、partial/invalid canonical file、object path/hash不一致、head不一致が1件でもあれば、より古いvalid revisionへfallbackせず`EVALUATION_DEFERRED`にする。最大の観測済みcommitted revisionとheadが一致し、その唯一chain全体がvalidな場合だけ再開する。

Canonical chainがvalidな場合のblockerだけを新しいdecision/Manifestとしてappendする。Chain自体がinvalidでhead CASのexpected valueを確定できない場合は、そのledgerへartifactまたはManifestを追記しない。代わりにruntime state rootのledger外`recovery-reports/<repository_id>/<run_id>/<report_id>/report.json`へJCSのrecovery reportをexclusive createで保存する。`report_id`は`run_id`と同じ文字規則の新しい一意IDとし、既存reportを上書きしない。Reportはartifact、lifecycle、state transition、READY根拠ではなく、`report_version`、`report_id`、repository/run ID、RFC 3339の観測時刻、`observed_head_base64`と`observed_head_sha256`、違反kind/field/invariant、観測したManifest path/hashの配列、transaction ID/descriptor hash、診断、`required_human_action: start_new_run|restore_verified_store`を持つ。Headが欠落または安全に読めない場合はhead bytes/hashをともにnullにして診断へ理由を記録し、該当するManifestまたはtransactionがないfieldもnullまたは空配列にする。Filesystemから得た非UTF-8 nameはraw bytesを`<filesystem-bytes-hex:...>`へ変換し、保存reportと標準出力のどちらもI-JSON/JCS化できる診断値にする。保存不能なら同じJCS valueをHumanへ直接返す。Harnessは壊れたrunを修復、古いheadへrollback、または自動再開せず、Humanが検証済みstoreを外部手順で復元するか、新runを明示開始するまで停止する。

Target、Issue input、scope、permission、project rule、contract hashが変わった場合は新しいgenerationを作る。旧verification、gate、reviewを成功根拠へ流用しない。Historical artifactはreconciliationの参照だけに使える。

### 必須payloadとcheckpoint

`input_snapshot.payload`は`input_kind`、`trust_source`、空でないstableな`source_identifier`、`source_sha`、`source_object_id`、`source_revision`、`content_format: utf8_text|jcs_json`、`content_sha256`、秘密情報を除いたexact `content`を持つ。`content_sha256`は保存した`content`がstringなら改行を正規化しないUTF-8 bytes、JSON valueならRFC 8785 JCS bytesだけをhashする。元sourceの秘密情報を除いた場合はredaction位置と理由を別fieldへ記録し、stored content hashを元source hashと表現しない。非該当locatorは空文字やplaceholderでなく明示的nullにする。

`input_kind`は次のdiscriminatorとする。

| Input kind | Source locator |
| --- | --- |
| `repository_identity|prior_run_handoff` | `source_revision`に`sha256:<content_sha256>`を必須、`source_sha: null`、`source_object_id: null` |
| `project_rule|acceptance_policy` | `source_sha`とGit blobの`source_object_id`を必須、`source_revision: null` |
| `issue_bundle|external_record` | Stableな`source_revision`を必須、`source_sha: null`、`source_object_id: null` |
| `personal_contract` | `source_revision`に`version:<declared_version>`または`sha256:<content_sha256>`を必須、`source_sha: null`、`source_object_id: null` |
| `required_capability` | 上記exact contentの`declared_version`がstringなら`version:<declared_version>`、nullなら`sha256:<content_sha256>`を`source_revision`へ保存し、`source_identifier: skill:<capability_name>`、`source_sha: null`、`source_object_id: null` |
| `human_approved_run_local|explicit_scope` | `source_revision`に`approval:<stable_approval_id>`を必須、`source_sha: null`、`source_object_id: null` |
| `permission_set` | Human変更時は`approval:<stable_approval_id>`、defaultは`sha256:<content_sha256>`を`source_revision`へ保存し、`source_sha: null`、`source_object_id: null` |

`trust_source`は`runtime_observed|personal_contract|base|human_approved_run_local|external_authoritative|external_observed`のいずれかとする。`repository_identity`と`prior_run_handoff`だけ`runtime_observed`を使う。Repository identityは`source_identifier: runtime:git-common-dir`と上記JCS objectのexact `content`を保存する。Prior run handoffは`source_identifier: run:<repository_id>/<prior_run_id>`とし、旧runを検証してから、terminal Manifestのrevision/artifact ID/hash、terminal state、停止理由、未解決requestごとのstable request ID、source type、source artifact ID/hashを通常refではないscalar valueとして`content`へcopyする。`reuse_policy: informational_only_rederive`を必須にし、request payload、artifact path、common ref、旧Evidence contentはcopyしない。新runはこのsnapshotを成功、finding、期待値の根拠へ使わず、`CONTEXT_RESOLVING`からreviewまたはverificationを再実行してcurrent targetのrequestを再生成する。`external_authoritative`は`authority_status: governing`、`external_observed`は`authority_status: evidence_only|pending`だけに使い、external inputは`authority_basis`を必須にする。

`issue_bundle`はrun開始時に明示されたIssueのstable ID、number、title、exact body/acceptance criteriaだけを持つgoverning projectionであり、comment、PR、review、linked Issueを含めない。`source_revision`はsourceがtitle/body専用のimmutable revisionを返す場合はその値、返さない場合はstable Issue ID、title、bodyを持つJCS valueのSHA-256を`sha256:<小文字16進64文字>`で保存する。各comment、PR、review、linked Issueは1 recordにつき1つの`external_record`へstable ID、revision、record type、author、author role、exact body、`authority_status`、`authority_basis`を保存する。`governing|pending`のrecordだけgeneration inputへ含め、`evidence_only` recordの追加、更新、削除はIssue bundleのbytes、revision、generation inputを変更しない。Authority statusが変わった場合は新しいexternal record inputとgenerationを作る。Git SHA/object IDはrepository object formatに一致する小文字16進40または64文字とする。

`stable_approval_id`はruntimeが返すimmutable event/message IDを優先する。取得不能時は、Humanのexact approval text、actor ID、対象run ID、approval scope、承認対象のcontent hashをJCS化したSHA-256を`sha256-<小文字16進64文字>`として使い、そのJCS value自体をHuman inputの`approval_evidence`へ保存する。Timestamp、表示名、連番だけからIDを補作しない。

Permission setは`input_kind: permission_set`の`input_snapshot`として、permission名、boolean、対象identity、allowed path/ref/source/host、effects、approval scopeをexact `content`へ保存する。Run開始時のdefaultもHumanによる追加・縮小も新しいimmutable snapshotにし、inline値だけを正本にしない。Human承認は先に`human_approved_run_local` input snapshotへ固定し、それを参照するdecisionを保存する。Permission setが変わった場合は新generationを作り、必ず`CONTEXT_RESOLVING`からcontext、review、verification、gateを再評価する。

`target.payload`は`popr_target_fingerprint`、`repository_identity_ref`、`generation`、`transition_reason`、`mutable_content_snapshots`、`index_diff_snapshot`だけを持つ。`popr_target_fingerprint`のvalueにpoprのmachine-readable fingerprint objectをそのまま保存し、Harness独自のfieldへflattenまたは変換しない。`repository_identity_ref`はcurrent repository identity inputを参照し、popr結果に存在しないidentityをpopr fingerprintの一部と表現しない。Targetから旧targetへの`previous_target_ref`は持たせず、generation lineageと変更証拠は`target_check`と、それを指すManifestの`transition_cause_ref`だけに保存する。

`generation`は0以上9007199254740991以下のI-JSON exact integerとする。Runの最初にcurrentになるtargetは0、`target_check.status: unchanged`ではexpectedとobservedのgenerationを同値、`changed`でcurrentへ切り替えるtargetはexpected generation + 1とする。Generationの飛越し、同じrunで過去にcurrentだった番号の再利用、上限を超える更新をvalidatorは拒否する。`unresolved`ではobserved targetとgenerationを補作しない。

Target作成時、working tree manifestのうちimmutable Git objectからexact bytesを再取得できない各present entryは、targetを確定する前にtarget所有の`mutable_content_snapshots`へ保存する。対象なしは空配列とし、対象ありは`{"path":"<repository_relative_path>","mode":"<git_mode>","type":"regular|symlink","content_oid":"<git_blob_oid>","byte_length":<integer>,"content_sha256":"<lowercase_hex_64>","content_path":"<run_relative_path>"}`をpathのUTF-8 byte順で一意に並べる。Raw binary bytesは変換せず、symlinkはlink targetのraw bytesを保存する。`content_path`はtarget artifact自身が所有するappend-only attachmentであり、共通artifact refでもEvidence graph nodeでもない。Targetのcanonical JSONがattachment metadataをhashで固定する。Validatorはattachment pathがrun directory内の通常fileであること、bytesのlength/SHA-256、raw bytesを`git hash-object --stdin`相当で計算したrepository object formatのGit blob OIDがmetadataの`content_oid`および同じpath/mode/typeを持つ`popr_target_fingerprint.working_tree.entries[].content_oid`と一致することを検証する。Mutable snapshotと該当fingerprint entryは一対一とし、重複、欠落、余分なsnapshotを拒否する。

`popr_target_fingerprint.index_diff.included: false`では`index_diff_snapshot: null`とする。`included: true`では、popr contractが固定したexact environmentとargvから得たstdout bytesを、target所有の`index_diff_snapshot` `{"byte_length":<integer>,"content_sha256":"<lowercase_hex_64>","content_path":"<run_relative_path>","capture_environment":<exact_environment>,"capture_argv":<exact_argv>}`へ保存する。Validatorはpath、bytes、length/SHA-256、capture environment/argvを検証し、raw bytesを`git hash-object --stdin`相当で計算したOIDがfingerprintの`index_diff.content_oid`と一致することを要求する。Reviewerは保存済みbytesをreview diffとして使い、後からindexから再生成したbytesへ置き換えない。Working treeまたはindex diffのexact bytesを安全に保存・再読込できない場合はtargetを確定せず`EVALUATION_DEFERRED`にする。

各target generationの`generation_input_refs`は、そのgenerationの実行判定を決めるまたは停止させるcurrent `input_snapshot`のcommon ref全件とする。Repository identity、Issueまたはexplicit scope、personal contract/required capability、project rule/acceptance policy、permission set、governingまたはpendingのexternal record、Human run-local input、新runを開始した場合の`prior_run_handoff`を該当する場合に含め、`evidence_only`のexternal recordは含めない。そのgenerationをcurrentにした最初のManifestの`input_refs`を正本とし、`artifact_id`順の重複なし配列にする。`repository_identity_ref`、`permission_set_ref`、`contract_ref`、`issue_ref`または`scope_input_ref`、およびinput snapshotを指す`project_context_refs`はすべてこの集合の要素でなければならない。

通常のtarget依存Stageの envelope `input_refs`は、その`target_ref`のgenerationの`generation_input_refs`とexactに一致させる。Transition `target_check`だけはenvelopeと`payload.expected_input_refs`にexpected旧generationの集合、`payload.observed_input_refs`に観測した次generation候補の集合を持つ。Evidenceの`input_refs`はそのbytesの生成に実際に使ったRoot refだけを`artifact_id`順で持つ。ValidatorはStageの集合不足、余分、順序違反を拒否し、Manifestがinput変更で次generationへ切り替わるまで新集合を通常Stageの正本にしない。

Stage artifactの必須payloadは次の通りとする。

| Artifact | 必須payload |
| --- | --- |
| `target_check` | `expected_target_ref`、`observed_target_status: resolved|unresolved`、`observed_target_ref`、`observed_target_absence_reason`、`expected_input_refs`、`observed_input_refs`、`expected_permission_set_ref`、`observed_permission_set_ref`、`expected_contract_ref`、`observed_contract_ref`、`expected_project_rule_refs`、`observed_project_rule_refs`、`status: unchanged|changed|unresolved`、`transition_kinds`、`observed_components`、`changed_components`、`unresolved_components`、`observation_evidence_refs`、条件付き`transition_diff_ref`、`checked_at` |
| `evidence` | `evidence_kind`、`media_type`、`content_sha256`、`content_path`またはinline `content`、`completeness: full|redacted|truncated`、`redactions`、`truncation` |
| `review` | `popr_result`、`generic_risk_result`、`generic_coverage_status`、`project_results`、`project_coverage_status`、`blocking_finding_ids`、`required_gates`、`coverage_status` |
| `change_request` | `requests`。各要素は`review_finding|verification_failure|gate_failure`を識別する |
| `remediation` | `request_id`、`decision`、`minimal_change`、`planned_paths`、`changed_paths`、条件付き`patch_ref`、`test_plan`、`scope_effect` |
| `verification` | `commands`、各commandの`command_id`、exact `argv`、exit code、開始・終了時刻、`stdout_ref`、`stderr_ref`、`environment_snapshot_ref`、`status`、`unverified_reason`、`mutated_target`、条件付き`mutation_patch_ref` |
| `gate` | `gate_name`、`declared_version`、`capability_revision`、`content_sha256`、`execution_status`、`decision_status`、`decision_policy`、`acceptance_policy_ref`、`evidence_ref`、`pre_target_check_ref`、`post_target_check_ref`、`mutated_target` |
| `blind_review` | `blind_result`、`generic_risk_result`、`generic_coverage_status`、`blind_received_artifacts`、`project_results`、`project_coverage_status`、`required_gates`、`independence_check` |
| `final_review` | `blind_review_ref`、`reconciliation`、`blocking_finding_ids`、`popr_result`、`previous_review_ref`、`remediation_status`、`remediation_refs`、`independence_check` |
| `decision` | `decision_kind`と、その判断を再現する観測値、根拠ref、blocker、Human action。Context解決では下記の専用field |

`change_request.requests`は空でない配列とし、各要素を次のdiscriminated unionで検証する。

- `source_type: review_finding`: `id`はsource review artifact内のexact finding ID、`source_ref`はそのreview、`source_item_id`は同じfinding IDを必須にする。
- `source_type: verification_failure`: `id`は`verification/<resolved_command_id>/<stable_failure_signature>`、`source_ref`はsource verification、`command_id`、要件またはtest contractの`input_snapshot`を指す`expected_behavior_ref`、`observed_failure`、raw output Evidenceを指す`output_ref`を必須にする。Stable signatureはresolved command ID、正規化したassertion、exit分類、主要error signatureから決定し、連番やtimestampを使わない。
- `source_type: gate_failure`: `id`は`gate/<gate_name>/<stable_failure_signature>`、`source_ref`はsource gate、governing acceptance policy inputを指す`expected_behavior_ref`、raw result Evidenceを指す`evidence_ref`を必須にする。Stable signatureはgate名、stable policy rule ID、主要failure signatureから決定し、連番やtimestampを使わない。

各`*_ref`は共通ref型とDAG規則を満たす。Testerとgateは観測結果と既存の期待値参照だけを記録し、severityや仕様を新設しない。Expected behaviorをimmutableな正本へ結び付けられない失敗はchange requestにせず`HUMAN_DECISION_REQUIRED`へ送る。Gateの実行失敗または利用不能は`gate_failure`へ変換せず`EVALUATION_DEFERRED`にする。

`review.required_gates`と`blind_review.required_gates`の各要素はexact `{"gate_name":"<nonempty>","trigger_reason":"<nonempty>","accepted_decision_statuses":["<status>"],"target_ref":<common_ref>}`とする。`accepted_decision_statuses`は`PASS|UPDATED`の空でない部分集合をUTF-8 byte順に重複なく並べ、`target_ref`はreview envelopeと同じtargetを指す。Gate artifactは同名gate、同じtarget、accepted status、same-target pre/post target checkを満たす場合だけrequired gateを充足する。Required gate itemのunknown field、空status集合、別target、同名gateの曖昧な複数成功を拒否する。

`remediation`は`request_id`でsource `change_request.requests[].id`のexact 1件を参照し、同じtarget generation lineageでrequest IDごとに最大1件だけcurrentにできる。再試行したremediationは各attemptを別artifactとして保持し、旧attemptを`historical`、最後のattemptだけを`current`にする。Final reviewの`remediation_refs`は同じFIXING lineageの全attemptを参照し、READYにはrequestごとにexact 1件の最新current attemptと、その`fix|not_applicable` decisionを要求する。`decision: fix|defer_minor|not_applicable|human_decision`、`minimal_change`、`planned_paths`、`changed_paths`、`test_plan`、`scope_effect`を必須にする。`fix`で実際に変更した場合は`patch_ref`を必須にし、その他はnullと不在理由を記録する。`defer_minor`はMinorまたはNitの`review_finding`だけに使え、Critical、Major、required verification failure、required gate failureへ使わない。Finding severityを変更する必要がある場合はreviewerへ差し戻す。

`blind_review.independence_check`と`final_review.independence_check`はexact `{"status":"passed|failed|unverifiable","compared_instance_ids":[],"compared_context_ids":[],"conflicting_instance_ids":[],"conflicting_context_ids":[]}`とする。各ID配列は空でないstringをUTF-8 byte順に重複なく並べる。`passed`ではcurrent lineage上のInitial reviewer、Project reviewer、Implementerの全producer instance/context IDを対応するcompared配列へ含め、conflicting配列を空にする。Final reviewer envelopeは`producer.role: final_reviewer`、`fresh_context: true`とし、producer instance/context IDがcompared IDのいずれとも一致しない場合だけpassedにできる。取得不能または比較不足は`unverifiable`、一致は`failed`とし、どちらもREADY根拠へ使わない。

`final_review.reconciliation`はexact `{"previous_findings":[],"current_findings":[]}`とする。`previous_findings`の各要素はexact `finding_id`、`status: Fixed|Remaining|Regressed|Not applicable`、`evidence_refs`を、`current_findings`の各要素はexact `finding_id`、`status: New|Residual`、Harness-owned `blocking: bool`、`evidence_refs`を持つ。HarnessはPopr内部severity schemaを複製せず、Final reviewerが判定したblocking状態だけを保持する。各配列はfinding ID順で重複を許さず、Evidence refはartifact ID順の重複なし配列にする。`blocking_finding_ids`は`current_findings`で`blocking: true`のfinding ID exact集合をUTF-8 byte順で持ち、READYでは空配列を要求する。各reviewのblocking findingは、そのreviewとfinding IDを指すexact 1件の`review_finding` change request、そのrequestをcauseとするFIXING遷移、同じrequest IDのcurrent final remediation、decisionに対応する空でないreconciliation Evidenceへ接続する。Blind scanを確定する前にprevious findingまたはremediationを受領したproducer metadata、同じfinding IDの分類重複、別target Evidenceを拒否する。

`verification.status`は`passed|failed|unverified`とする。`passed`は全commandのexit codeが0、required output Evidenceが`full|redacted`、`unverified_reason: null`の場合だけ許可する。READYではContextの`resolved_commands.commands`に固定した`command_id`とexact `argv`の集合を、currentなpassed verification command集合とexact 1回ずつ照合する。必須commandの欠落、別ID、argv drift、重複実行を成功へ丸めない。Schema 2.0 v1の`failed`は空でないcommand記録、少なくとも1 commandの非0 exit code、`unverified_reason: null`をすべて要求し、`verification_failure`は選択したcommand自身のexit codeが非0の場合だけ作れる。期待値不一致だけを表す別schemaは本versionに含めない。`unverified`は空でない`unverified_reason`を必須にし、READY根拠へ使わない。`passed`でも`mutated_target: true`ならsame-target成功として扱わず、mutation patchを保存して新targetを固定する。

`gate.execution_status`は`succeeded|failed|unavailable`、`decision_status`は`PASS|UPDATED|BLOCKED|HUMAN_DECISION_REQUIRED`とする。`failed|unavailable`では`PASS|UPDATED`を禁止する。`gate_name`、`declared_version`、`capability_revision`、`content_sha256`はgateのcurrent `required_capability` input exact 1件のidentity、revision、hashと一致させる。宣言versionがあるcapabilityは`version:<declared_version>`、ないcapabilityは`sha256:<content_sha256>`をrevisionとする。Gate Evidenceはsame-targetのpre target checkより後、post target checkより前に作成し、gate自体はpost checkより後に作成する。`succeeded`でもrequired gateの`accepted_decision_statuses`に含まれないstatus、same-targetでないpre/post target check、`mutated_target: true`はrequired gateを充足しない。Gate実行失敗または利用不能をpolicy判断でPASSへ変換しない。

`review`と`blind_review`の`generic_coverage_status`、およびreview結果全体の`coverage_status`は`Complete|Incomplete`とする。`project_coverage_status`は`Complete|Incomplete|not_required`とする。Contextの`project_review_status: required`ではreviewとblind reviewの両方に`project_coverage_status: Complete`を要求し、`project_results[].lens_id`のsorted unique集合を`required_lens_ids`とexact一致させる。`project_review_status: not_required`では両方を`project_coverage_status: not_required`かつ空の`project_results`にする。READYはこのcontext policy、generic `Complete`、review全体の`Complete`をすべて要求する。

Context解決の`decision.payload`は`decision_kind: context_resolution`、`resolution_mode`、`contract_status`、`contract_ref`、`considered_sources`、`selected_sources`、`authority_decisions`、`resolved_source_of_truth`、`resolved_scope`、`resolved_lenses`、`resolved_commands`、`resolved_gates`、`resolved_risk_triggers`、`resolved_permissions`、`resolved_limits`、`unresolved_inputs`を持つ。`resolved_lenses`はexact `{"project_review_status":"required|not_required","required_lens_ids":[],"source_ref":<common_ref>,"content_sha256":"<sha256>"}`とする。`required`はUTF-8 byte順の空でないlens ID集合、`not_required`は空集合を要求する。`resolved_commands`はexact `commands`、`source_ref`、`content_sha256`を持ち、各commandをsorted unique `command_id`、空でないexact `argv`、contract順の`effects`、正整数`timeout_seconds`、sorted unique `required_services`で固定する。各selected sourceとresolved fieldは対応するinput/evidence refとcontent hashを含める。値が空になり得る他fieldは、空配列だけでなく`not_required_reason`とその判断根拠refを持つ。候補を無視して空の`unresolved_inputs`を返さず、いずれかのresolved fieldが欠落するdecisionを`context_status: resolved`の根拠にしない。

`run_manifest.payload`は`revision`、`previous_manifest_ref`、`state`、`previous_state`、`transition_id`、`transition_cause_ref`、`repository_identity_ref`、`target_status`、`target_absence_reason`、`current_target_generation`、`current_target_ref`、`input_refs`、`permission_set_ref`、lifecycle wrapperを使う`artifact_refs`、`limits`、`counters`、`input_source`、`issue_ref`、`scope_input_ref`、`contract_status`、`contract_ref`、`context_status`、`resolution_mode`、`pending_reason_refs`、`conflict_refs`、`project_context_refs`、`context_resolution_ref`、`last_completed_stage`、`resume_state`、`blocker`を持つ。`repository_identity_ref`はrun rootの`repository_id`を導出したcurrent inputを指し、`input_refs`にも同じrefを含める。`artifact_refs`へManifestを含めない。最初のrevisionだけ`previous_manifest_ref: null`を許し、以後は直前Manifestのpathとhashを参照する。

`review|change_request|remediation|verification|gate|blind_review|final_review|target_check`はartifact typeごとの許可stageだけで作成し、そのartifactより小さいsequenceの直前Manifestが同じstateであることを要求する。将来stageのartifactを先に生成して後からManifestだけを並べることはできない。Root、Evidence、context/blocker decisionはcauseや同一transactionを構成するためこのcheckpoint規則の対象外だが、各type固有のstage/ref/DAG規則には従う。

Manifest envelopeとpayloadの重複bindingはvalidatorがexact一致を要求する。Envelope `input_refs`とpayload `input_refs`は同じ順序の同一配列である。`target_status: resolved`では`target_absence_reason: null`、envelope `target_ref`とpayload `current_target_ref`を同じ非null common refにし、`current_target_generation`を参照先targetの`payload.generation`と一致させる。両input配列はそのtarget generationの`generation_input_refs`と一致し、targetと各input refが`artifact_refs`で`current`になっていなければならない。`target_status: unresolved`では`target_absence_reason`を空でないstring、envelope `target_ref`とpayload `current_target_ref`と`current_target_generation`をすべてnullにする。Unresolvedでも両input配列の一致を要求し、存在するcurrent inputだけを`artifact_refs`で`current`にする。Resolved/unresolved以外、target ref、input集合、generationの交差、payloadだけの更新を拒否する。

`input_source: issue`では`issue_ref`を必須にして`scope_input_ref: null`、`explicit_scope`では`scope_input_ref`を必須にして`issue_ref: null`とする。`contract_status`は`resolved|unavailable|drifted`とし、`resolved`だけhash付き`contract_ref`を持てる。`context_status`は`resolved|pending|conflicted`とし、`resolved`だけ`resolution_mode: repository_baseline|human_approved_run_local|mixed`を持ち、`pending_reason_refs`と`conflict_refs`は空配列にする。`pending`は`resolution_mode: null`、空でない`pending_reason_refs`、空の`conflict_refs`を、`conflicted`は`resolution_mode: null`、空の`pending_reason_refs`、空でない`conflict_refs`を要求する。各要素は未解決または矛盾を記録したartifactのcommon refとする。`context_status: resolved`には`contract_status: resolved`、validな`permission_set_ref`、external authority確定、全`resolved_*` fieldの存在と根拠ref、空の`unresolved_inputs`、空でない`project_context_refs`、`context_resolution_ref`を要求する。各state遷移、target generation変更、stage完了、blocker、外部副作用の前後で新revisionをappend-only保存する。

`state`、`resume_state`、`blocker`は次のdiscriminated unionとして検証する。

| `state` | `resume_state` | `blocker` |
| --- | --- | --- |
| `CONTEXT_RESOLVING|REVIEW_PENDING|CHANGES_REQUESTED|FIXING|VERIFYING|PRECOMMIT_DOCS_PENDING|CANDIDATE_COMMIT_PENDING|TARGET_VERIFYING|GATES_PENDING|REREVIEW_PENDING` | null | null |
| `READY` | null | null |
| `EVALUATION_DEFERRED` | `CONTEXT_RESOLVING` | 下記blocker object |
| `VERIFICATION_BLOCKED` | `VERIFYING`または`TARGET_VERIFYING` | 下記blocker object。停止したverification stateと一致させる |
| `SCOPE_CHANGE_REQUIRED` | `CONTEXT_RESOLVING` | 下記blocker object |
| `HUMAN_DECISION_REQUIRED` | `CONTEXT_RESOLVING` | 下記blocker object |
| `INDEPENDENCE_BLOCKED` | `REREVIEW_PENDING` | 下記blocker object |
| `BUDGET_EXHAUSTED` | null | 下記blocker object |

Blocker objectは`failure_classification`、`cause_ref`、空でない`observed_evidence_refs`、`required_human_action`、`resume_requirement`を持つ。`cause_ref`はManifestの`transition_cause_ref`と同じcurrent Stage ref、`observed_evidence_refs`はそのStageから到達するcurrent Evidence refに限定する。Stateごとの許容値は次に固定し、それ以外の組合せ、null、空配列を拒否する。

| `state` | `failure_classification` | `required_human_action` | `resume_requirement` |
| --- | --- | --- | --- |
| `EVALUATION_DEFERRED` | `target_unresolved|context_unresolved|capability_unavailable|coverage_incomplete|gate_unavailable|artifact_invalid|input_revalidation_failed|external_write_unsupported` | `provide_or_restore_required_input_or_capability` | `revalidate_context_and_target` |
| `VERIFICATION_BLOCKED` | `environment_unavailable|permission_unavailable|required_service_unavailable` | `restore_verification_environment_or_permission` | `revalidate_same_permission_and_environment` |
| `SCOPE_CHANGE_REQUIRED` | `scope_expansion` | `approve_scope_change_or_split_issue` | `record_scope_decision_and_revalidate_context` |
| `HUMAN_DECISION_REQUIRED` | `specification_ambiguous|risk_acceptance_required|authority_pending|permission_decision_required|side_effect_decision_required` | `record_spec_risk_or_permission_decision` | `record_human_decision_and_revalidate_context` |
| `INDEPENDENCE_BLOCKED` | `fresh_reviewer_unavailable|independence_unverifiable` | `provide_fresh_reviewer` | `record_fresh_reviewer_identity` |
| `BUDGET_EXHAUSTED` | `deadline_exhausted|token_budget_exhausted|paid_call_budget_exhausted|remediation_cycle_exhausted|same_request_attempt_exhausted|transient_retry_exhausted|diff_limit_exhausted` | `start_new_run` | `new_run_with_prior_run_handoff` |

Blockerを起こした既存Stageが上記観測値を完全に持たない場合は、先に`decision_kind: blocker_observation`のdecision artifactを保存する。そのpayloadは`blocked_state`、`target_ref`、`failure_classification`、`attempt`、`command_or_tool`、`exit_code`、空でない`observed_evidence_refs`、`required_human_action`、`resume_requirement`、`resume_state`を持つ。`target_ref`はManifestの`current_target_ref`と同値にし、target unresolvedだけnullを許す。`attempt`は実行試行がある場合の0以上のI-JSON exact integer、それ以外はnull、`command_or_tool`は実行したstable IDまたはnull、`exit_code`はprocessが終了codeを返した場合のI-JSON exact integer、それ以外はnullとする。`observed_evidence_refs`は`artifact_id`順の重複なし配列にする。Manifestはこのdecisionを`transition_cause_ref`と`blocker.cause_ref`で参照し、`decision.payload.blocked_state == manifest.state`、`decision.payload.resume_state == manifest.resume_state`を要求する。`failure_classification`、`observed_evidence_refs`、`required_human_action`、`resume_requirement`はdecision payloadとManifest blockerでfieldごとにexact一致させる。`blocker.cause_ref`自体をdecision payloadへ複製せず、自己参照を作らない。これにより自由文のlogだけからblockerまたはresume先を復元しない。

`final_review.remediation_status`は`required|not_required`のいずれかとする。Current targetのgeneration lineageでoriginを問わず`change_request`が`FIXING`を1回でも発生させた場合は`required`とし、`remediation_refs`へ対応する全remediation artifactを含める。Lineage全体に該当change requestがない場合だけ`not_required`と空の`remediation_refs`を許可する。

`gate.decision_policy`は`native_status|project_or_human`とする。`acceptance_policy_ref`は`native_status`の場合だけnullにでき、`project_or_human`ではgoverningなacceptance policyまたはHuman承認input snapshotへのcommon refを必須にする。その他のnullable refは、各payload contractが状態と不在理由を明示した場合だけnullを許す。

現行`security-audit`は監査reportとscoreを所有するがnativeなPASS/BLOCKEDを持たないため、Harnessは次のexact adapterだけを所有する。Audit前後にsame-target `target_check`を保存し、full reportを`evidence_kind: security_audit_result`のEvidenceへ保存する。そのJCS `content`は`audit_contract_revision`、`audit_status: complete|incomplete`、0以上10以下のinteger `rounds_completed`、6カテゴリを固定順で持つ`category_results`、全`findings`、0以上100以下のinteger `overall_score`、exact string `raw_report`、そのUTF-8 bytesの`raw_report_sha256`を持つ。

`category_results`の各要素はexact `{"category_id":"<id>","weight_percent":<integer>,"score":<0..100 integer>}`とし、`authentication_session: 25`、`authorization_access_control: 20`、`csrf_transport: 15`、`input_validation_injection: 20`、`infrastructure_server_configuration: 10`、`logging_monitoring_information_disclosure: 10`の順に6件を要求する。`findings`の各要素はexact `id`、`severity: Critical|High|Medium|Low`、上記`category_id`、`location`、`attack_scenario`、`evidence`、`remediation`を持つ。`audit_status: complete`は`rounds_completed: 10`、全6カテゴリ、raw report/hash一致の場合だけ許可する。10 round未完、category coverage不足、report/hash不一致は`audit_status: incomplete`かつ`execution_status: failed`にし、READYへ使わない。

Security gateは常に`decision_policy: project_or_human`とし、上記Evidence、前後target check、`mutated_target`をgate artifactへ接続する。Base側のgoverning acceptance policyがstable rule IDと、security resultのseverity/count/score/category fieldから`PASS|BLOCKED`を決める完全な規則を持つ場合だけ機械適用できる。Policyがない、不完全、複数解釈、またはHumanのrisk判断が必要なら、監査完了やfinding 0件をPASSへ変換せず`decision_status: HUMAN_DECISION_REQUIRED`にする。Humanが判断する場合も、exact result、対象run/target、受容scopeを固定したHuman inputを`acceptance_policy_ref`へ保存する。`mutated_target: true`または前後check不一致はdecision statusにかかわらずsame-target成功として扱わない。

`target_check.status`は、全componentを観測でき差分がなければ`unchanged`、全componentを観測でき差分が1件以上あれば`changed`、1件でも再取得または比較できなければ`unresolved`とする。`unresolved`では`unresolved_components`へcomponent、理由、観測証拠refを記録し、既存artifactを再利用せず`EVALUATION_DEFERRED`にする。`changed`と`unresolved`を相互に丸めない。

`target_check` envelopeの`target_ref`は常に`expected_target_ref`と同じ旧/current targetを指す。`unchanged`では`observed_target_status: resolved`かつ`observed_target_ref`をexpectedと同じcommon ref、`changed`では事前にexact bytesを固定した次generationのtarget common refとする。`unresolved`では`observed_target_status: unresolved`、`observed_target_ref: null`、空でない`observed_target_absence_reason`を要求し、新targetを補作しない。

`transition_kinds`は`target_changed`、`governing_input_changed`、`permission_changed`、`contract_changed`、`project_rule_changed`、`scope_changed`、`external_revision_changed`、`unresolved`をこの順で重複なく並べる。差分も未解決もない場合だけ`["none"]`とする。`status: changed`は`none|unresolved`以外を1つ以上、`status: unresolved`は`unresolved`を必須とし、観測済みの変更kindも併記する。Expected/observed refsの各集合は`artifact_id`順で並べ、permission、contract、project rule、governing inputをtarget contentと独立に比較できるようにする。

各verification commandの`stdout_ref`と`stderr_ref`は、出力が空でも空bytesをhashした個別`evidence`を参照する。秘密情報はredaction位置と理由を記録できるが、単なる切詰めを`full`または`redacted`と表現しない。`completeness: truncated`のevidenceはHuman向けpreviewに限定し、READYまたはresumeの根拠へ常に使わない。完全なbytesを保存できる場合は別の`completeness: full|redacted` artifactとして保存し、Stageからそのartifactを参照する。各`content_sha256`は同じartifactの`content_path`またはinline `content`のbytesだけをhashする。`remediation.decision: fix`で変更した場合は`patch_ref`、`mutated_target: true`のstageは`mutation_patch_ref`を必須にする。

Working tree manifestのtracked/untracked file追加、変更、削除、file mode/type変更、または`index_diff.included|content_oid`変更で`target_check.status: changed`になった場合は`transition_diff_ref`を必須にする。参照先は`evidence_kind: target_transition_diff`のcanonical JSONとし、`expected_target_ref`、`observed_target_ref`、`path_changes`、`index_diff_change`を持つ。各path changeはchange kindと`before`、`after`を持ち、`before|after`は`{"status":"absent"}`または`{"status":"present","mode":"<mode>","type":"regular|symlink","content_oid":"<git_blob_oid>","byte_length":<integer>,"content_sha256":"<hash>","content_source":<source>}`のdiscriminated unionとする。追加はbeforeだけ`absent`、削除はafterだけ`absent`、空fileは`present`かつ`byte_length: 0`とし、欠落や取得失敗を`absent`へ丸めない。`content_source`は`{"kind":"git_object","object_id":"<oid>"}`または`{"kind":"target_attachment","target_id":"<target_artifact_id>","content_path":"<run_relative_path>"}`とする。Before contentはexpected targetのsnapshotまたはimmutable Git object、after contentはobserved targetのsnapshotまたはimmutable Git objectへ結び付ける。

`index_diff_change`はindex diffが同値ならnull、差分があれば`{"before":<index_side>,"after":<index_side>}`とする。`index_side`は`{"status":"excluded"}`または`{"status":"included","content_oid":"<git_blob_oid>","byte_length":<integer>,"content_sha256":"<hash>","content_source":{"kind":"target_attachment","target_id":"<target_artifact_id>","content_path":"<run_relative_path>"}}`のunionとし、expected/observed targetの`index_diff_snapshot`へそれぞれ結び付ける。Validatorは両target ref、fingerprint entryまたはindex diff OID、attachment metadata、raw bytesから再計算したGit blob OIDとSHA-256/length、entryのtarget IDを照合する。`path_changes`が空かつ`index_diff_change: null`のtransition diffを拒否する。Text、binary、symlink、cached diff bytesを変換せず、EvidenceからEvidenceへの参照は追加しない。新generationへ進むManifestは、その`target_check`またはtargetを変更したStage artifactを`transition_cause_ref`で参照する。

Offline artifact validatorは`content_source.kind: git_object`で`object_id == content_oid`、target refs、change kind、path/index change coverageを検証するが、clean targetのfingerprintへHEAD tree全entryを複製しない。`<head_sha>:<path>`が実際にそのblobを指すことは#50のtarget checkerがread-only Git inspectionで再取得して検証する。`target_attachment`はrun store内のraw bytesを持つため#49で完全に検証する。この境界を理由にgit objectを未検証のままREADYへ使わず、#50のsame-target成功を必須にする。

Orchestratorはtarget依存stageの開始前と完了後、resume、Final review開始前、READY判定前、呼び出し元へ`READY`を返す直前に`target_check`を保存する。Checkは保存済みtargetだけでなく、generation input refs、permission set、contract/project rule hash、governing/pending external source revisionも現在値と比較する。Evidence-only recordはauthority判定を再実行するために取得できるが、そのcontent driftだけをgeneration driftへ含めない。差分または必要な再取得不能があれば旧artifactをREADY根拠へ使わず、該当blockerを記録する。

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
- `write_run_store`: 初期true。Candidate外のappend-only ledger、transaction、ledger外recovery reportだけ。
- `read_external_source`: 明示source/hostだけtrue。Authorityは別判定。
- `fetch_remote_refs`: 初期false。Candidate commit準備で明示されたrepository identity、remote、refspec、prune範囲だけtrueにできる。
- `write_worktree`: 変更依頼かつallowed path/limitがある場合だけtrue。
- `run_local_commands`: 解決済みexact commandだけtrue。
- `commit`: 明示されたcommitまたはPR依頼の範囲だけtrue。
- `push`、`create_or_update_pr`、`write_external_system`: 常にfalse。`READY`後の提出は呼び出し元が既存の`create-pr` contractで実行する。
- `merge`、`deploy_or_production_write`、`accept_risk_or_spec`: 初期false。Harnessはtrueにしない。

この集合全体をpermission set input snapshotとしてManifestの`permission_set_ref`へ固定する。Permissionの追加・縮小、対象identity、allowed path/ref/source/host、effects、approval scopeの変更はすべてgoverning input変更であり、途中stageへ直接resumeせず`CONTEXT_RESOLVING`へ戻る。単なるservice復旧などpermission setのbytesが不変な場合だけ、記録済みresume stateへ戻れる。

解決済みcommandはstable ID、exact command、declared `effects`、1以上でrun deadline以下のtimeout、required servicesを持つ。`effects`は`repository_read|local_write|repository_write|external_read|external_write`の重複なし配列をこの順に並べる。複合commandは該当effectをすべて持ち、各rowのpermissionとretry制約を累積する。

| Effect | 必要permissionと固定input | Retry条件 |
| --- | --- | --- |
| `repository_read` | `read_repository`、`run_local_commands` | 未実行または未完了を証明できるtransient failureだけ1回 |
| `local_write` | `run_local_commands`、許可されたlocal destination | 同じ入力から安全に再実行できるdeclared commandだけ1回 |
| `repository_write` | `run_local_commands`、`write_worktree`、allowed paths、file/diff limit | 同じ入力から安全に再実行できるdeclared commandだけ1回 |
| `external_read` | `run_local_commands`、`read_external_source`、source/host、credential scope、network、paid-call budget | 同じsourceへの未完了transient failureだけ1回 |
| `external_write` | 本contractのverification/gate commandではunsupported。Permissionを追加せず実行前に`EVALUATION_DEFERRED` | 自動retryなし |

Declared effectsはpermissionの下限であり、command自身が権限を弱めるauthorityではない。Orchestratorは実行tool metadata、network access、filesystem/endpointのread/write先を独立に分類し、観測または可能なeffectをdeclared setへ加えた累積effective setで判定する。Network endpoint、credential、paid cost、local/repository write先、effect集合のいずれかを実行前に一意に分類できないcommandは権限を昇格して推測実行せず停止する。Coverage upload、外部DB変更、Issue/comment/SaaS更新は`external_write`として検出するが、本contractのverification/gate commandでは許可せず、専用artifactを補作せず停止する。認証付きAPIやpackage auditのnetwork readは`external_read`を含める。Deployまたはproduction writeを含むcommandもHarness内で実行しない。Context resolutionにないcommandも実行しない。Context前の固定bootstrap inspectionはproject commandではなく`read_repository`だけで実行する。

Limitsには`max_remediation_cycles`、`max_same_request_attempts`、`max_transient_stage_retries`、required RFC 3339 deadline、integerまたは`unsupported`のtoken budget、paid external call budget、UTF-8 byte順のallowed write paths、max changed files、max diff linesをexact fieldとして含める。Countersは`remediation_cycles_started`、request ID別attempt、execution key別transient retry、integerまたは`unsupported`のtokens used、paid external callsをexact fieldとして含める。Limitはrun中不変、scalarとmap counterは非減少、map keyは削除不可、各値は対応上限以下とし、token budgetとusageの`unsupported`は両方一致させる。初期counterは0または空で開始する。

各Manifestの`created_at`がrun deadline以上なら、`deadline_exhausted`のexact `limit_observation`をcauseとする`BUDGET_EXHAUSTED`だけを許可する。通常stateまたはREADYをdeadline到達後に保存して成功へ進めず、時刻guardをcallerの会話状態だけへ委ねない。

Remediation cycleは`FIXING`直前、request別attemptは対象requestの最初のworktree変更前、transient retryは再実行前にcounterを予約する。`FIXING`へ入るManifestはcause `change_request.requests`の全IDを同じrevisionでexactに1ずつ増やし、対象なし、一部だけ、別ID、2以上の増加を拒否する。予約した試行はcrash時に戻さず、同じexecution keyを重複実行しない。Counterが上限と等しくなっただけでは進行中の試行を停止せず、その試行後も未解消で次の試行が必要になった時点で`BUDGET_EXHAUSTED`にする。

`BUDGET_EXHAUSTED`のcauseは`decision_kind: limit_observation`だけに限定する。Payloadはblocker共通fieldに加えてexact `limit_name`、`limit_value`、`limit_event`、`observed_value`、nullable `counter_key`、exact Manifest schemaの`counter_snapshot`、`previous_manifest_revision`、`previous_manifest_sha256`を持つ。Classificationごとにlimitとeventを固定し、deadline、token、diffの`hard_exceeded`は観測値がlimit以上または超過したことを、paid callの`next_reservation_rejected`とattempt系の`next_attempt_rejected`は直前counterがlimitへ到達したことを要求する。Request attemptとtransient retryは`counter_key`を必須にして該当map値と照合し、その他ではnullにする。Observationは直前Manifestのrevision、canonical hash、counter snapshotへexactに結び、停止Manifestでcounterを変更しない。

`fetch_remote_refs`はcandidate準備に必要なnetwork readとlocal Git metadata更新専用である。実行前にnormalized repository identity、remote名とURL、source/destination refspec、`prune`の有無、credential scope、timeoutをallowlistへ固定する。Fetchは`--no-tags`かつ自動maintenance無効で実行し、許可するlocal writeはGit object database、fetch中のlock/temporary metadata、`FETCH_HEAD`、宣言したremote-tracking ref namespaceだけとする。Working tree、index、local branch、tag、Git configを変更しない。`run_local_commands`や`read_repository`へ暗黙に含めない。Permissionがfalse、remote identityまたはrefspecが不一致、credentialまたはnetworkが利用不能ならfetchせず、前2者は`HUMAN_DECISION_REQUIRED`、後者は`EVALUATION_DEFERRED`にする。

Fetchのtimeoutまたはtransient failureでは、許可したrefをread-backして要求されたobjectとref更新が完了済みなら成功として再実行しない。未完了を確認でき、同じallowlistとexecution keyを使う場合だけ`max_transient_stage_retries`の範囲で1回retryできる。Fetch後にbaseまたはinput refが変わった場合は成功を流用せず`CONTEXT_RESOLVING`へ戻る。

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
11. `READY`またはblockerを呼び出し元へ返す。Harnessはpush、PR作成、提出結果の再開を実行しない。

Targetを変更したstageは`TARGET_MUTATED`相当の結果を返し、影響するartifactをinvalidateする。Harnessが`READY`を記録して呼び出し元へ返す前にbase/head/input driftを検出した場合はREADYを作らず、同じrunの`CONTEXT_RESOLVING`から新targetを作る。`READY`返却後の提出時照合と`READY_INVALIDATED`は`issue-to-pr` / `create-pr`だけが所有し、旧runへ追記せずintakeから新しいHarness runを開始する。

各stageの失敗と差戻しは次のように一意に扱う。

- `REVIEW_PENDING`: CriticalまたはMajorがあれば`change_request`を作って`CHANGES_REQUESTED`、なければ`VERIFYING`へ進む。Targetまたはcoverage不足によるpoprの`Evaluation deferred`は`EVALUATION_DEFERRED`、materialな仕様矛盾による同resultは矛盾Evidenceを保存して`HUMAN_DECISION_REQUIRED`へ進む。
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

Blockerからは記録されたresume stateへだけ戻る。`EVALUATION_DEFERRED`は`CONTEXT_RESOLVING`、verification blockerは停止したverification state、independence blockerは`REREVIEW_PENDING`を再開候補にするが、次の再検証に成功するまで遷移しない。`BUDGET_EXHAUSTED`は現在runのterminal stateであり、Manifestは`resume_state: null`と`blocker.required_human_action: start_new_run`を持ち、同じrunのlimitを増やしてresumeしない。Humanが継続を承認した場合は、新しいlimit/permission inputとself-containedな`prior_run_handoff` input snapshotを持つ別`run_id`を開始する。旧runのcommon refを新runへ保存せず、旧runへdecisionまたはManifestを追記しない。

Resumeでは次を順に行う。

1. Single-writer lockを取得し、transaction descriptorとstaged/write-set hashを照合する。上記条件で一意に完了可能なtransactionだけをidempotentに完了し、それ以外は停止する。
2. Canonical namespaceの全Manifestとheadを検査し、最大の観測済みcommitted revisionがheadと一致する唯一の連続chainであることを確認する。Invalid、partial、fork、説明不能なorphan、重複revision、head不一致があれば古いrevisionへfallbackしない。各Manifestのcontent hash、transition、counter、全artifact refに加えて`permission_set_ref`、`project_context_refs`、`context_resolution_ref`のhashを検証し、`artifact_refs`にManifestが含まれないことも確認する。
3. Repository identity、base ref/SHA、branch、head SHA、working tree status/mode/manifestをread-onlyで再取得する。
4. Issue governing projectionと`governing|pending` external inputをsourceから再取得し、revisionとcontent hashを照合する。新規recordもauthority判定し、新たに`governing|pending`となる場合はinput driftとする。Evidence-only recordのcontent driftだけではgenerationを変えない。必要なinputの権限または安定したrevisionがなく再検証できなければ成功扱いしない。
5. 新しい`target_check`をexpected/observed target、generation input、permission set、contract/project rule、governing/pending external revisionへ接続して保存する。
6. Manifestのcurrent target generationと再取得値を比較し、driftがあれば新target/input snapshotを作る。許可済み変更か想定外driftかをtransition evidenceで分類し、上記lifecycle表に従って旧artifactを`historical|invalidated`へ遷移させて`CONTEXT_RESOLVING`へ戻す。
7. Driftがない場合だけ、同じtarget generation、input refs、permission set、contract hashを持つ完了artifactを再利用する。
8. `last_completed_stage`を単独cursorにせず、manifest stateと確定済みtransitionから状態機械を再評価する。検証不能、manifest chain破損、曖昧な実状態は`EVALUATION_DEFERRED`または`HUMAN_DECISION_REQUIRED`にする。

## Fallback

- Project-local Harness skill/entrypointなし: 正常系。Personal/global Harnessを使い、project側に複製しない。
- Repository context不足: Base instruction、CI/manifest、governing Issueから必須fieldを決定的に解決する。未解決fieldはHuman承認run-local inputで補完し、用意できなければ停止する。
- Project reviewerなし: Personal `pr-risk-reviewer`または同じsemantic contractでgeneric comprehensive reviewを行う。信頼済みruleが専用lensを要求せず、generic coverageがCompleteならproject coverageは`not_required`にできる。
- Codex subagentなし: 過去会話を渡さない新しいtask/sessionまたはHuman reviewerへhandoff bundleを渡す。
- Claude Code subagentなし: 別session、別CLI、Human reviewerのいずれかを使う。
- Fresh sessionなし: `INDEPENDENCE_BLOCKED`。
- Required gate実装なし: 同じsemantic contractの別実装をHumanが用意する。用意できなければ停止する。
- Git remote fetch不可: 許可済みremote/refへのnetwork、credential、Git metadata writeを回復して再開する。Base/ref一致を再検証できなければcandidate準備またはPR提出を続けない。
- Worktreeなし: Cleanな単独checkoutだけを使う。Dirty共有checkoutや並行runでは停止する。
- Token meterなし: `unsupported`を記録し、cycle、retry、deadline、cost limitを適用する。

Fallbackで独立性、coverage、gate成功を偽装しない。

## 出力

- `READY`: Exact base/head、target ref、artifact hash、gate status、Final review、permission使用状況を返す。Mergeは実行しない。
- Blocker: State、原因artifact、観測値、完了済みartifact、invalidated artifact、必要なHuman action、resume stateを返す。

## 検証

- Harness wrapper/reference、generic comprehensive reviewer、required capabilityのpath、capability revision、content hashを固定した。
- 全artifactが同じrunと正しいtarget generationへ接続され、参照graphが非循環である。
- Canonical JSON bytes、mutable content attachment、Manifest lifecycle遷移がSchema 2.0の規則へ一致する。
- Input kindごとのsource locator/null規則とstored content hashが一致する。
- Ledger破損時はcanonical chainへ追記せず、ledger外recovery reportを返す。
- Required verificationとgateがcandidate SHAへ結び付く。
- ImplementerとFinal reviewerのinstanceが分離され、blind scanの受領artifactが制限されている。
- Critical/Major 0、poprとgeneric comprehensive coverage Complete、unresolved blockerなしを確認した。
- Retry、scope、permission、cost上限を超えた副作用がない。
- `READY`後のpush、PR作成、project hookはHarness外の`issue-to-pr`と`create-pr`へ委譲され、Harness permissionを流用していない。

## 関連skill

- `issue-to-pr`: Issue intakeと全体進行。
- `principle-of-programming-reviewer`: Neutral reviewの共通schemaとrubric。
- `sync-docs-code`: Documentation gate。
- `security-audit`: Risk trigger時のsecurity gate。
- `create-pr`: Candidate prepareとexact publish。
