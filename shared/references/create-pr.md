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

- PR作成依頼は、現在scopeの変更をcommit、pushしてPRを作る権限を含む。merge権限は含まない。
- PRは宣言済みscopeだけを含め、無関係な整形、依存更新、別課題を混ぜない。
- 1 commitを単独revertしたとき、その変更目的だけが戻る単位に分ける。
- 各commitは単独checkout時にもbuild、型check、関連testが通る状態を保つ。後続commitがなければ動かない変更は同じcommitにまとめる。
- 同じ目的の実装と関連testは原則として同じcommitに含め、独立して説明できるdata取得・永続化、UI、refactor・設定は別commitにする。
- 各commitで対象pathを`git add <path>`または`git add -p`により明示し、`git diff --cached`で内容を確認する。
- Commit件名はglobal指示の`Gitと成果物の共通契約`に従う。
- PR titleと本文は日本語で書き、全commitと最終diffの実態を反映する。
- PR作成時は`07130918`をassigneeに設定し、変更内容に合うlabelを付ける。
- Bot reviewは指摘の根拠を検証し、妥当な指摘だけを反映する。Copilotへのreview依頼はuserが手動で行う。

## 完了条件

- Project指定のlint、format、型check、testが成功している。
- 実行できない必須checkは理由と代替確認がPR本文に記録されている。
- `sync-docs-code`が`PASS`または`UPDATED`で、`BLOCKED`ではない。
- Commit済みの`<base>...HEAD`と未commit差分の両方を確認し、PR対象に未commit変更が残っていない。
- PR URL、assignee、label、base、headを確認できる。

## 手順

### 1. Contextを固定する

1. `git branch --show-current`と`git status --short --branch`を確認する。
2. 現在branchが空、`HEAD`、`main`、`develop`なら停止する。
3. `git fetch --prune origin`でremote refsを最新化する。
4. `git symbolic-ref refs/remotes/origin/HEAD`を優先してbaseを決める。失敗時は`develop`、次に`main`を使う。
5. 比較元を`origin/<base>`に固定し、`git diff --name-status origin/<base>...HEAD`、`git diff --name-status`、`git diff --cached --name-status`、untracked fileを確認する。
6. `.env`、認証情報、秘密情報らしいfileが含まれる場合はcommitせず、対象を報告する。

### 2. 品質gateを通す

1. ProjectのAGENTS.md、CLAUDE.md、package script、Makefile、CIから必須commandを特定する。
2. 変更に該当するlint、format、型check、unit testを実行する。
3. Bug修正またはUI変更は、再現手順を実環境で再実行する。
4. 必須checkが失敗した状態ではcommitとPR作成へ進まない。

### 3. Documentationを同期する

1. `sync-docs-code`を同じbase、HEAD、working treeへ実行する。
2. `PASS`または`UPDATED`と関連検証の成功を確認する。
3. `BLOCKED`ならPRを作成しない。

### 4. Commitを作成する

1. 最終diffを変更目的ごとに分け、commit一覧を決める。
2. 各commitで対象pathだけをstageし、`git diff --cached --check`と`git diff --cached`を確認する。
3. 共通契約に従う日本語件名でcommitする。
4. Commit後、そのcommitが単独checkout時の動作可能性を満たすか確認する。後続commitへ依存する分割なら同じcommitへまとめ直す。
5. `git status --short`を確認し、PR対象の変更が残っていれば次のcommitへ進む。
6. 全commit作成後、必要な品質gateを再実行する。

### 5. PR差分を確定する

1. `git diff --name-only origin/<base>...HEAD`、`git diff --stat origin/<base>...HEAD`、`git log --oneline origin/<base>..HEAD`を確認する。
2. 必要に応じて`git diff origin/<base>...HEAD --no-color`を読み、scope外変更がないことを確認する。
3. `.github/pull_request_template.md`があれば構造を維持する。なければ標準templateを使う。
4. 最新commitだけでなく、全commitの差分からPR titleと本文を作る。

### 6. PushしてPRを作成する

1. `git push -u origin <branch>`で現在branchをpushする。
2. `gh pr create`でbase、head、title、本文、assignee、labelを指定する。
3. `gh pr view`でURL、state、draft、assignee、label、base、headを確認する。

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
- Push後にPR作成だけ失敗した場合は、branch URLと再実行commandを示す。
- `--no-verify`は使わない。

## 関連skill

- `issue-to-pr`: Issue起点の調査と実装。
- `sync-docs-code`: PR前のdocumentation同期gate。
- `git-diff`: 差分確認だけを行う。
- `git-worktree-ops`: 独立worktreeの作成とmerge後整理。
