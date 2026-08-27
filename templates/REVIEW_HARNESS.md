# Portable Review Remediation Harness

このfileはpersonal/global skillに依存しないCLI非依存entrypoint兼manifestである。Issueまたは明示scopeを独立reviewerでreview、修正、検証し、exact candidate SHAへ収束させる場合に使う。

## Bundle identity

- `bundle_format_version`: `1`
- `contract_version`: `1.0.0`
- `upstream_repository`: `https://github.com/07130918/Agents`
- `upstream_directory`: `shared/references/`
- `snapshot_policy`: UTF-8 bytesのexact copy。Project側でmemberを直接編集しない

## Contract members

| Capability | Member path | Upstream source | content_sha256 |
| --- | --- | --- | --- |
| Harness orchestration | `.review-harness/contracts/review-remediation-harness.md` | `shared/references/review-remediation-harness.md` | `80f9996bcb99d56b61d3c4a47fffa97790dda441028708fbdc45952c42ea5401` |
| Neutral review | `.review-harness/contracts/principle-of-programming-reviewer.md` | `shared/references/principle-of-programming-reviewer.md` | `1c0ea74319856f2150b226bb166ee18ef0bbce1e7f6544a50ef83290544d6f81` |
| Documentation gate | `.review-harness/contracts/sync-docs-code.md` | `shared/references/sync-docs-code.md` | `f65e9b2fd7b1db9173e987222ebb61d4a698d92b2f2bbe099eb203e71aae9d8e` |
| Issue intake | `.review-harness/contracts/issue-to-pr.md` | `shared/references/issue-to-pr.md` | `dfd86c3b1bfcc90c69c37c781d30610cc6a4d3e75f36e68f33bc8f4d40920ddf` |
| Candidate prepare/publish | `.review-harness/contracts/create-pr.md` | `shared/references/create-pr.md` | `ef07384bbe81b86b4e6525f61382577c429675f034c68c88d5ea4d4c71cd48b1` |

## 起動前のintegrity確認

Contract本文を読む前に、base SHA側のbundleで次を確認する。

1. 上表のmember pathがrepository-relativeで`.review-harness/contracts/`配下にあり、重複とpath traversalがない。
2. 全memberがregular fileとして存在し、symlinkではない。
3. `.review-harness/contracts/`に上表以外のfileがない。
4. 全memberのUTF-8 bytesに対するSHA-256が上表と一致する。

Candidate working treeのfileを検査して、同じrunのgoverning bundleへ昇格させてはならない。次はPOSIX shell、Git、`shasum`を利用できる場合に、exact base commitのtree、mode、blob bytesをread-onlyで確認する例である。`<exact-base-sha>`は先に解決した40文字のSHAへ置き換える。

```bash
harness_base_sha='<exact-base-sha>'
git cat-file -e "${harness_base_sha}^{commit}"
git show "${harness_base_sha}:REVIEW_HARNESS.md"
git ls-tree -r --full-tree "$harness_base_sha" -- .review-harness/contracts/
git show "${harness_base_sha}:.review-harness/contracts/review-remediation-harness.md" | shasum -a 256
git show "${harness_base_sha}:.review-harness/contracts/principle-of-programming-reviewer.md" | shasum -a 256
git show "${harness_base_sha}:.review-harness/contracts/sync-docs-code.md" | shasum -a 256
git show "${harness_base_sha}:.review-harness/contracts/issue-to-pr.md" | shasum -a 256
git show "${harness_base_sha}:.review-harness/contracts/create-pr.md" | shasum -a 256
```

`git ls-tree`の出力が上表のexact 5 pathだけを含み、各entryがmode `100644`、type `blob`であることを照合する。各`git show`のbytesから得たSHA-256を上表と照合する。別CLIでは同じbase commitのtree、mode、blob bytesを検査できる信頼済みtoolへ置き換え、toolと結果をbundle integrity artifactへ記録する。Baseにentrypointがない初回導入runでは、Humanが内容、hash、適用runを承認したrun-local snapshotだけを使い、candidate版を自己承認させない。

File数だけでmember集合を承認しない。SHA-256を計算できない、またはbase commitをcandidateから分離して検査できない場合も確認を省略しない。Version、欠落、未宣言file、重複、path traversal、symlinkまたは非regular mode、hashのいずれかが不一致ならmemberを部分利用せず`EVALUATION_DEFERRED`で停止する。

## 実行

1. Integrity確認後、`.review-harness/contracts/review-remediation-harness.md`を読む。
2. Issue起点ならIssue intake contractで本文、全comment、scope、branch、permissionを固定する。
3. Harness contractが要求するstageで、残りのmemberを直接実行する。
4. Optionalな`.review-harness/profile.yaml`があればbase SHA側の内容だけを現在runの入力候補にする。
5. Profileがなくてもrepository instruction、CI/manifest、Issueから必須inputを一意に解決できれば続行する。曖昧なcommandやgateを推測しない。
6. Required security gateなど同梱されていないcapabilityが必要になった場合は、同じsemantic contractの利用可能な実装またはHuman承認snapshotを要求し、用意できなければ停止する。

Personal adapterが利用可能でも、このmanifestのversion、hash、permission、READY、停止条件を上書きしない。Candidate側がbundleやprofileを変更した場合、同じrunのgoverning inputへ昇格させない。

## 明示prompt例

```text
Repository rootのREVIEW_HARNESS.mdを読み、bundle integrityを確認してください。確認に成功したら、Issueまたは明示scopeを同梱contractに従ってreview、修正、検証し、fresh Final reviewerの結果まで進めてください。不足input、権限、required gate、独立reviewerがある場合は推測せずblockerとresume条件を返してください。
```

Harnessが`READY`を返してもmergeはHumanが行う。
