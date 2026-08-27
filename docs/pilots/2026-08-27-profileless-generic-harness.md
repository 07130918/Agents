# Profileなしgeneric Harness pilot

## 概要

Issue [#42](https://github.com/07130918/Agents/issues/42)に基づき、personal `review-remediation-harness`をproject profileと専用project reviewerがない実repositoryで手動pilotした。

代表runはFareHuntのhistorical UI変更を隔離worktreeで再現した。Initial reviewで3件のMajorを検出して2 remediation cycleを実行し、実行上はrequired testが残った時点で`BUDGET_EXHAUSTED`へ停止した。その後のartifact監査で手動JSONにschema非準拠を検出したため、このrunの契約上の最終判定は`EVALUATION_DEFERRED`とした。Hold-out runはword-pop-quizでexact verification commandを解決できず、command名から推測せず`EVALUATION_DEFERRED`で停止した。

どちらも`READY`ではない。Profile不在自体ではなく、artifact非準拠、観測したverification failure、固定budget、未解決inputを停止理由にした。

## Personal Harnessの固定

Run開始前にAgents `main`の`a566c20bdbe89ea67887aaf0a9ca14185b7b67a0`をpersonal/global設定へ同期し、project側ではなく次のpersonal pathから起動した。

| Input | Path | SHA-256 |
| --- | --- | --- |
| Wrapper | `~/.agents/skills/review-remediation-harness/SKILL.md` | `2300e38efde40c962d613e5e0a0d1b736e56ea9fb3193cc3433741179610b382` |
| Contract | `~/.agents/references/review-remediation-harness.md` | `0822bc102afc4800bb88e872a27a0ef4e207d92e3666cf6cc3db5b0732b1b2ff` |
| Popr | `~/.agents/references/principle-of-programming-reviewer.md` | `1c0ea74319856f2150b226bb166ee18ef0bbce1e7f6544a50ef83290544d6f81` |
| Generic reviewer | `~/.codex/agents/pr-risk-reviewer.toml` | `dfa0f48d4ba48e9e2addadfa8b2a1d8e61a3b5fa3138e4f3dac8c1650e65ba44` |

`scripts/validate.sh`と`scripts/diff-local.sh`を実行してから同期し、同期後のwrapper/reference hash一致を確認した。

## 代表run: FareHunt

### 選定

| Field | Value |
| --- | --- |
| Repository | `github.com/07130918/FareHunt` |
| Base SHA | `311d05e7a422c77f48baffcbfaebcd2f07f17c2b` |
| Initial head SHA | `e6368a840ec983055b7fb218c33760f74abc75be` |
| Initial diff | emojiからReact Iconsへの変更とdate picker更新、10 files |
| Profile | `.review-harness/profile.yaml`なし |
| Project reviewer | 専用`code-reviewer` / `pr-risk-reviewer`なし |
| Project-local Harness | skill、entrypoint、contract snapshotのいずれもなし |
| 実行場所 | `/tmp/farehunt-issue42.En2AEi/worktree`の隔離worktree |

個人projectであり、本番service、秘密情報、会社dataを必要としない。Remote branchに存在するhistorical commitを使うことで入力を再現可能にし、FareHuntへのpush、PR作成、恒久file追加を禁止した。

### Context解決

Profile不在を`profile_status: absent`として記録し、次の順序でbase側情報を解決した。

| 順位 | Source | 採用結果 |
| --- | --- | --- |
| 1 | `.review-harness/profile.yaml` | 不在。blockerにはしない |
| 2 | `CLAUDE.md` blob `76c5dba1c971de2a66e98ed7030208c786a289e6` | Project概要と規約として採用 |
| 3 | `.github/workflows/pr-validation.yaml` blob `8a89a4abe9a5c46a7ad33f96a9090337afd445e5` | PR verificationの正本として採用 |
| 4 | `Makefile` / `package.json` | CI stepのexact scriptとeffect確認に採用 |
| 5 | Issue #42 | Pilot scopeと非目標のgoverning inputとして採用 |

Exact verificationはCIの順序から`npm ci`、`npm run chakra:typegen`、`npm run check`、`npm run type-check`、`npm run test:ci`、`npm run build`へ固定した。`Makefile`の`make ci`はbuildを含まずCIより狭いため、単独の正本にはしなかった。

Initial/Final reviewにはpoprとgeneric comprehensive reviewをrequiredとし、base ruleが専用lensを要求しないため`project_coverage_status: not_required`とした。Docs gateはrequired、security gateは当初triggerなしと解決した。

### Permissionとlimit

- Target側は隔離worktree内の変更とlocal commitだけを許可し、push、PR、external write、merge、deployを禁止した。
- Remote readは`origin`の`refs/heads/refactor/code-1`を`--no-tags`かつpruneなしで取得する範囲だけを許可した。
- `max_remediation_cycles: 2`、`max_same_request_attempts: 2`、`max_transient_stage_retries: 1`、paid call budgetは0とした。
- Changed file上限12、diff上限700 linesとした。
- Initial review前のwrite pathを既知のtest fileだけに狭めすぎたため、review後に元の変更scope内2 filesと隣接testへ訂正した。この訂正は外部scopeを増やしていないが、手動allowlist設計の摩擦として記録した。

### Initial review

実装と会話履歴を持たないfresh instanceを2つ使用した。

| Capability | Instance | Coverage | Result |
| --- | --- | --- | --- |
| Popr | `/root/issue42_initial_popr` | Complete | `Request changes` / C / Major 3 / Minor 1 |
| Generic risk | `/root/issue42_initial_risk` | Complete | 実害risk 3件。Poprの3 root causeへ統合 |

Blocking findingは次の3件だった。

1. Date-only値を`new Date(YYYY-MM-DD)`と`toISOString()`で往復し、timezoneによって検索日が前日になる。
2. Custom DatePicker inputがlabel、validation error、keyboard eventの契約を失う。
3. Emoji削除後も既存testがemoji込み見出しを要求し、required CIが失敗する。

不要な`@types/react-datepicker`はMinorだったため、自動loopの対象にしなかった。

### Remediationとverification

3件のMajorだけを対象に、`FlightSearchForm.tsx`、新規component test、`ResultsContent.test.tsx`を変更した。Targetをgeneration 0から1へ更新し、以前のgradeと単純比較しなかった。

| Attempt | 結果 | 遷移 |
| --- | --- | --- |
| 1 | `npm ci`、typegen、Biome check成功。`npm run type-check`が新規test型とChakra label型の3 errorsで失敗 | `VERIFYING -> CHANGES_REQUESTED -> FIXING` |
| 2 | typegen、Biome check、type-check成功。`npm run test:ci`は145 pass、6 fail、3 skip、1 todo | `VERIFYING -> BUDGET_EXHAUSTED` |

Attempt 2では、新規DatePicker mockが`aria-labelledby`をcustom inputへ模倣しておらず2 testが失敗した。またhistorical testの固定日付`2026-06-01`がpilot実行日`2026-08-27`では過去日となり、既存API testが期待した500より前にvalidationの400となった。Required testが失敗したためbuild、docs/security gate、candidate commit、Final reviewへ進まなかった。

`npm ci`は14 vulnerabilitiesを報告した。対象差分がdependencyを変更しているため、本来はsecurity triggerの再評価が必要だが、verification budgetで先に停止した。成功扱いにもrisk受容にもしていない。

### 観測した実行状態とartifact

```text
CONTEXT_RESOLVING
  -> REVIEW_PENDING
  -> CHANGES_REQUESTED
  -> FIXING
  -> VERIFYING
  -> CHANGES_REQUESTED
  -> FIXING
  -> VERIFYING
  -> BUDGET_EXHAUSTED
```

- Run ID: `agents-42-farehunt-20260827T065752Z`
- Local store: `.git/review-harness/07130918-FareHunt/agents-42-farehunt-20260827T065752Z/`
- Persistent evidence: [`evidence/2026-08-27-profileless-generic-harness/`](evidence/2026-08-27-profileless-generic-harness/)
- Manual run log: 27 JSON、124 KiB
- Artifact ledger aggregate SHA-256: `0f6b4813f044740820d6e69ba86f6af401f314fd590ee33202280ccb7e12245d`
- Final manifest: `027-manifest-r8.json`
- Final manifest SHA-256: `c9d2527bc940b2f27e5357d5186150018392e51698e63b8b7d7561c1652f09d3`
- Manifest記録state: `BUDGET_EXHAUSTED`
- 契約上の最終判定: `EVALUATION_DEFERRED`
- Final reviewer: 未実行。Required verificationが成功していないため

### Post-run artifact監査

全27 JSONがparse可能で、ledger aggregate hashは保存済みbyte列を識別できることを確認した。一方、次のschema非準拠があり、これらをcanonical artifactまたはresume可能なmanifest chainとは扱わない。

- `input_refs`と`artifact_refs`の一部が、共通refの`artifact_id`、`artifact_path`、`sha256`を持たずpath文字列だけで保存されている。
- Personal contractとrequired capabilityの`input_snapshot.payload.content`がexact contentではなくpathとhashの要約になっている。
- 常設validatorがないため、作成時にDAG、required payload、参照先hashを機械的に検証していない。

契約ではartifact graph違反をREADY根拠へ使わず`EVALUATION_DEFERRED`にする。このため、最後のmanifestが記録した`BUDGET_EXHAUSTED`は実行時のbudget guard観測として保持するが、run全体の契約適合を示す最終stateには使わない。JSONを上書きして履歴を整形することもしていない。

Merge後も監査できるように、context、Initial review、target generation、verification、budget decisionとgeneration 2 patchをpersistent evidenceへ抽出した。全artifactを複製せず、約42 KiBの最小bundleに限定した。Generation 1 patchとcommandのfull stdout/stderrはpilot中に保持していなかったため、後から補作せずbundleの制限として明記した。

## Hold-out run: word-pop-quiz

`github.com/07130918/word-pop-quiz`のremote `main`、exact SHA `56bc473617bb9bc5108bf9aa22ab1fc0a5b99f1f`をread-onlyで解決した。

Profile、project reviewer、project-local Harness、AGENTS/CLAUDE、CI workflowはいずれも存在しない。`package.json`には`build`、targetを書き換える`lint --fix`と`format --write`はあるがtest scriptがなく、READMEにもrequired gateがない。そこでcommand名からbuildやlintを必須検証へ昇格させず、次をunresolved inputとして停止した。

- Exact verification command
- Required gates

結果は`EVALUATION_DEFERRED`、resume stateは`CONTEXT_RESOLVING`である。Profile不在ではなく必須input不足を理由にした。Human承認run-local inputまたは任意profileが提供されるまでproject commandを実行しない。

Manual artifact作成時にtarget hashのplaceholderを含むdecisionを一度生成した。上書きせずinvalidatedとし、correct hashの新artifactをappendした。ただし、代表runと同じくschema validatorを通していないため、このledgerもcanonical artifactとは扱わない。上書きを避けた挙動とplaceholder混入の両方が、手動artifact運用のerror-pronenessを示した。

- Run ID: `agents-42-word-pop-holdout-20260827T071340Z`
- Local store: `.git/review-harness/07130918-word-pop-quiz/agents-42-word-pop-holdout-20260827T071340Z/`
- Persistent evidence: [`evidence/2026-08-27-profileless-generic-harness/word-pop-quiz/`](evidence/2026-08-27-profileless-generic-harness/word-pop-quiz/)
- Artifact数: 5 JSON、20 KiB
- Artifact ledger aggregate SHA-256: `e56b37662305d9ccda819cd897f7d0b35c7a6ce00005d5e2259041d29292182d`
- Final manifest SHA-256: `a325626dc019fced5e81fee9b8bbc0f4b11c2dcb38ffbb9271b499cf091eb1b8`

## Scenario結果

| Scenario | 観測結果 |
| --- | --- |
| Profileなしで標準規約とcommandを解決 | FareHuntでは`repository_baseline`で解決成功 |
| Project-local Harness fileなしで同じ状態遷移を辿る | State machineは実行でき、Target repositoryへHarness fileを追加していない。Artifact schema適合は失敗したため完全成功とは扱わない |
| Test command候補が一意でない、または不足 | word-pop-quizで`EVALUATION_DEFERRED` |
| Source of truthが矛盾 | 今回は未発生。矛盾なしを成功と記録し、synthetic conflictは作っていない |
| 必須gateまたはfresh reviewerが利用不能 | Fresh Initial reviewerは利用可能。Final reviewerはverification未達のため起動対象外 |
| 修正が元scopeを超える | 未発生。Write allowlist訂正は元のUI変更と隣接test内に限定 |
| Target SHAまたはsnapshotが変わる | Remediationごとにgeneration 0 -> 1 -> 2とし、旧review/verificationを成功根拠へ流用していない |
| Retry/cost上限へ到達 | 2 remediation cycle後もrequired testが失敗し、実行上は`BUDGET_EXHAUSTED`で停止 |
| Artifact graphまたはrequired payloadが不正 | Post-run監査でschema非準拠を検出し、最終判定を`EVALUATION_DEFERRED`にした |

## Uka-Route最適化pilotとの比較用観測値

| Metric | Generic pilot |
| --- | --- |
| Profile status | `absent` |
| Context resolution | FareHunt: resolved、word-pop-quiz: pending |
| Contextの主な根拠 | Repository instruction、CI workflow、manifest |
| Initial reviewer | Fresh 2 instances |
| Manual permission decision | 1件 |
| Remediation cycle | 2 / 2 |
| Target generation | 3世代 |
| Required verification | 6 commands。5番目で停止 |
| Final state | `EVALUATION_DEFERRED`。実行時checkpointは`BUDGET_EXHAUSTED` |
| Final reviewer | 0。Verification未達のため |
| External write | 0 |
| Target projectへの恒久file | 0 |
| Manual run log | 27 JSON、124 KiB。Schema適合は否認 |
| Hold-out state | `EVALUATION_DEFERRED` |

## Issue #40へのhandoff

このpilotだけで自動化を採用決定しない。Uka-Route #1197のprofileありpilotと比較するため、Issue #40では[reportとpersistent evidence](evidence/2026-08-27-profileless-generic-harness/)を使って少なくとも次を評価する。

1. Artifact/manifest helper: 手動hash参照とmanifest chainは誤りやすく、実際に共通refとexact contentの非準拠、placeholder hashのinvalidatedを観測した。WriterまたはvalidatorがDAG、required payload、hash、直前manifest参照を保護できるか比較する。少なくともschema適合を証明できないrunをREADYへ進めない検査が必要である。
2. Target checker: Formatter、typegen、remediationごとのsnapshot/hash再取得は単純だが反復が多い。Deterministic checkerでtarget driftだけを小さく自動化できるか比較する。
3. Context resolver: FareHuntではCIから解決できた一方、word-pop-quizでは安全に停止した。Profile authoring支援がunresolved inputを減らすか、単なる追加保守になるか比較する。
4. Permission allowlist: Initial findingを事前予測したpathだけに狭めると訂正が必要になった。Changed pathとadjacent testを初期allowlistへ含める規則が安全か検討する。
5. Historical replay: Fixed dateや外部時刻に依存するtestは後から再現不能になる。Current-date-safe fixture、clock固定、またはcurrent targetをpilotへ使う条件を比較する。
6. Security trigger: Dependency変更とinstall時のaudit signalをcontext/gateへ反映する規則が必要か、optimized profileでどこまで明示できるか比較する。
7. Loop budget: 2 cycleで安全に停止できた一方、agentが追加したtest mockの不備でもbudgetを消費した。上限を緩めず、verification failureを同一request attemptとして扱う粒度を比較する。

常設runner、fixture、schema validator、project profileはこのIssueでは追加していない。

## 結論

Personal Harnessはproject profileと専用reviewerなしで起動し、repository baselineからcontextを解決して独立Initial review、修正、verificationまで進められた。また情報不足、budget超過、artifact非準拠を成功へ読み替えず停止できた。

一方、今回の代表runはcanonical artifact chainを確立できず`READY`へ到達していないため、「profileなしで契約どおり安定して完走できる」とは結論しない。特にartifact作成と検証、permission allowlist、time-dependent test、security trigger、verification failureのattempt粒度はUka-Route最適化pilotとIssue #40で比較する必要がある。
