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
- Generation 2のworking tree patch

word-pop-quizは、訂正済みcontext decisionとterminal manifestを保存した。Local user pathは`~`へ置換したが、判断に使ったrepository SHA、Git blob hash、target hashは変更していない。

元の32 JSONすべては保存しない。選択したcheckpointでIssue #42の受入判断を監査でき、残りは非canonicalな中間manifestと重複情報である。Bundle追加時の総量は約42 KiBである。

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
