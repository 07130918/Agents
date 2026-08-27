# Profileなしgeneric Harness pilot evidence

Issue [#42](https://github.com/07130918/Agents/issues/42)の監査用evidence bundle。Pilot結果の要約と判断は[`../../2026-08-27-profileless-generic-harness.md`](../../2026-08-27-profileless-generic-harness.md)を正本とする。

このdirectoryはHarnessのcanonical run store、常設fixture、schema適合例ではない。Author-localな`.git/review-harness/`と`/tmp`が消えた後も、Issue #40で主要な観測結果と非準拠箇所を再確認できるように、必要なcheckpointだけを保存した監査用extractである。

## 保存scope

FareHuntは次を保存した。

- Context resolution
- Fresh Initial review
- Target generation 1 / 2のfingerprint
- Verification attempt 1 / 2
- Attempt 2のremediation plan
- Budget停止decision
- Terminal manifest
- Generation 2のworking tree patch

word-pop-quizは、訂正済みcontext decisionとterminal manifestを保存した。Local user pathは`~`へ置換したが、判断に使ったrepository SHA、Git blob hash、target hashは変更していない。

元の32 JSONすべては保存しない。選択したcheckpointでIssue #42の受入判断を監査でき、残りは非canonicalな中間manifestと重複情報である。Bundle追加時は13 files、約48 KiBである。

## Provenance

Source rootは次のauthor-local run storeである。

- FareHunt: `.git/review-harness/07130918-FareHunt/agents-42-farehunt-20260827T065752Z/`
- word-pop-quiz: `.git/review-harness/07130918-word-pop-quiz/agents-42-word-pop-holdout-20260827T071340Z/`

| Extract | Source SHA-256 | Extract SHA-256 | Transform |
| --- | --- | --- | --- |
| `farehunt/006-context-resolution.json` | `23c79fbef014bdd873476b8ebb93db71f7c086b328e4c184bee404259298d91b` | `23c79fbef014bdd873476b8ebb93db71f7c086b328e4c184bee404259298d91b` | exact copy |
| `farehunt/009-initial-review.json` | `9bf968162bfa0f49bf8ab0cd311174dec19ad1b0d0b4f221939502450771e964` | `9bf968162bfa0f49bf8ab0cd311174dec19ad1b0d0b4f221939502450771e964` | exact copy |
| `farehunt/016-target-generation-1.json` | `3cb06d378533345206a432a3c995913eed9caa4164f5f63e6ea41e9f70d0ea64` | `3cb06d378533345206a432a3c995913eed9caa4164f5f63e6ea41e9f70d0ea64` | exact copy |
| `farehunt/018-verification-attempt-1.json` | `6fd695e0fd616412296329b33d9841af84d4e54cfafad7dc32e30dd94e5ff8c1` | `6fd695e0fd616412296329b33d9841af84d4e54cfafad7dc32e30dd94e5ff8c1` | exact copy |
| `farehunt/020-remediation-plan-attempt-2.json` | `52ea863a2fb0d76ca940684828263a2c7259f626dccf731e8cf9db1f40444a77` | `52ea863a2fb0d76ca940684828263a2c7259f626dccf731e8cf9db1f40444a77` | exact copy |
| `farehunt/021-target-generation-2.json` | `06099f70164683dbc65ee066448c66be559824fbcfab50d0ea63a0361ea775df` | `06099f70164683dbc65ee066448c66be559824fbcfab50d0ea63a0361ea775df` | exact copy |
| `farehunt/025-verification-attempt-2.json` | `06ddc95008f801cf35a44b9db34532c9f7124c4678a03f6a1b90824f6b655da5` | `06ddc95008f801cf35a44b9db34532c9f7124c4678a03f6a1b90824f6b655da5` | exact copy |
| `farehunt/026-budget-exhausted.json` | `58fd5a11fffc07e04cc045fa8f9934558ac788b594fce9dd25b80882064655c3` | `58fd5a11fffc07e04cc045fa8f9934558ac788b594fce9dd25b80882064655c3` | exact copy |
| `farehunt/027-manifest-r8.json` | `c9d2527bc940b2f27e5357d5186150018392e51698e63b8b7d7561c1652f09d3` | `c9d2527bc940b2f27e5357d5186150018392e51698e63b8b7d7561c1652f09d3` | exact copy |
| `word-pop-quiz/004-context-deferred-corrected.json` | `8863fcf04b2dae6e1b3825f12d54d43d2f10a9f4b5f8935ade3137b90a80018e` | `abae1b6bf62effc634b29fbd9fa432b9238cbbf302c4d1590455dc451b3b0844` | local user pathを`~`へ置換 |
| `word-pop-quiz/005-manifest-r1.json` | `a325626dc019fced5e81fee9b8bbc0f4b11c2dcb38ffbb9271b499cf091eb1b8` | `155cd04ac736ebe05ac694fc4fedb355340a378a5705dc8aed7857a37bd7ca80` | local user pathを`~`へ置換 |

Pilot reportのFinal manifest SHA-256はsource artifactのhashである。FareHunt terminal manifestはexact copyのためextractから同じ値を検証できる。Hold-out terminal manifestはpath-redacted extractなので、reportの`a325626...`はSource SHA-256、committed fileのhashは`155cd04...`となる。

## 重要な制限

- 保存JSONはpilot時の手動artifactから取得したが、共通refとexact contentのschema非準拠を含む。Canonical artifactまたはresume可能なrun storeとして使わない。
- Generation 1はfingerprint、file content hash、diff SHA-256、verification結果を保存したが、working tree patchそのものはpilot中に保持していなかった。後から推測復元していない。
- `generation-2.patch`は失敗したverification対象の証拠であり、採用候補や修正例ではない。
- Commandのfull stdout/stderrは保持していない。保存したexit code、時刻、要約をpilot結果の限界として扱う。

これらの制限により代表runは`READY`ではなく`EVALUATION_DEFERRED`である。

## Reproduce

FareHuntのcommitted inputは次のexact rangeで再取得できる。

```bash
git -c maintenance.auto=false fetch --no-tags origin refs/heads/refactor/code-1
git diff --stat 311d05e7a422c77f48baffcbfaebcd2f07f17c2b e6368a840ec983055b7fb218c33760f74abc75be
git switch --detach e6368a840ec983055b7fb218c33760f74abc75be
git apply --check --unidiff-zero /path/to/Agents/docs/pilots/evidence/2026-08-27-profileless-generic-harness/farehunt/generation-2.patch
```

Patch SHA-256:

```text
7d50952cfafbad5f727967c501a0bd30c4bf6641f90abd24187f71660ba702ea
```

元run storeが残っている場合、report記載のledger aggregate SHA-256は次の方法で再計算できる。Path自体もhash入力に含むため、元と同じrepository-relative pathから実行する。

```bash
pilot_run_store=.git/review-harness/07130918-FareHunt/agents-42-farehunt-20260827T065752Z
find "$pilot_run_store" -maxdepth 1 -type f -name '*.json' -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256
```

期待値:

```text
0f6b4813f044740820d6e69ba86f6af401f314fd590ee33202280ccb7e12245d
```

Hold-outはstore pathを`07130918-word-pop-quiz/agents-42-word-pop-holdout-20260827T071340Z`へ置き換え、期待値`e56b37662305d9ccda819cd897f7d0b35c7a6ce00005d5e2259041d29292182d`と照合する。
