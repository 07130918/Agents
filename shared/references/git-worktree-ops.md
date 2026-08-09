# git-worktree-ops

Git worktreeを使って作業場所とbranchを安全に分離し、状態確認、作成、PR merge後の整理まで行うworkflow。既存worktreeや未コミット変更を壊さず、別PRへの変更混入と誤ったbranch削除を防ぐ。

## 使う場面

- 「新しいworktreeで作業」「別PRへ変更を混ぜない」「worktreeを切って」と依頼されたとき。
- 複数PRや複数branchを並行して扱うため、独立した作業directoryが必要なとき。
- 「merge後のworktreeを整理」「不要なworktreeとbranchを削除」と依頼されたとき。
- worktreeとbranchの対応、stale metadata、削除できない理由を調査するとき。

対象外:

- 現在のworktree内で通常のbranchを作るだけの作業。
- commit、push、PR作成そのもの。必要に応じて `create-pr` へ委譲する。
- 未コミット変更の内容判断や別branchへの移植。変更の帰属が不明ならユーザーへ確認する。

## 入力

- action: `create`、`status`、`cleanup` のいずれか。自然文から明確なら省略可。
- repository: 対象repository。未指定なら現在のGit repository。
- branch: 作成または整理するbranch名。
- base: 新規branchの比較元。未指定ならoriginの既定branch。
- path: worktreeの絶対path。未指定なら既存規約を探し、安全な候補を提示または採用する。
- optional PR: merge確認に使うPR番号またはURL。

## 出力

- 実行したactionと対象repository、branch、worktree path。
- 作成後または整理後の `git worktree list` と `git status` の要約。
- 保護した未コミット変更、残したbranch、削除できなかった対象と理由。
- 次に作業すべきworktreeの絶対path。

## 安全原則

- 最初に `git rev-parse --show-toplevel`、`git status --short --branch`、`git worktree list --porcelain` を確認する。
- worktree path、branch、baseを具体値へ解決してから変更する。未解決の環境変数、glob、`~` を削除対象に使わない。
- dirtyなworktreeをremoveしない。tracked変更だけでなくuntracked fileも確認する。
- `git worktree remove --force`、`git branch -D`、直接のrecursive削除を使わない。
- branchが別worktreeでcheckout中なら、その対応を保ったまま停止して報告する。
- ユーザーの変更を自動でstash、discard、移植しない。
- merge確認なしにlocal branchやremote branchを削除しない。

## 手順

### 1. repositoryと既存worktreeを固定する

1. `git rev-parse --show-toplevel` でrepository rootを取得する。
2. rootで `git status --short --branch` を実行し、現在のbranchとdirty状態を記録する。
3. `git worktree list --porcelain` でworktree path、HEAD、branch、locked、prunableを確認する。
4. `git symbolic-ref refs/remotes/origin/HEAD` を優先して既定baseを決める。失敗時は `develop`、次に `main` を使う。
5. remote情報が必要なら `git fetch --prune origin` を実行し、判断前に最新化する。

### 2. actionを決める

- 新しい作業場所が必要なら `create`。
- 対応関係や異常の確認だけなら `status`。
- merge済み作業の削除なら `cleanup`。
- actionによって必要なbranch、path、PRが判断を変える場合だけユーザーへ確認する。

### 3. worktreeを作成する

1. repository内のAGENTS.md、README、scriptからworktree配置規約を探す。
2. 規約がなければrepositoryの外側に専用親directoryを使う。例: `<repo-parent>/<repo-name>-worktrees/<branch-slug>`。
3. branch名をpath componentへ使う場合は `/` を `-` に置換し、空文字、`.`、`..` にならないことを確認する。
4. `test -e <path>` でpath衝突がないことを確認し、親directoryだけを `mkdir -p` で作る。
5. `git show-ref --verify refs/heads/<branch>` と `git show-ref --verify refs/remotes/origin/<branch>` でlocal、remote branchの有無を確認する。
6. local branchが存在する場合は `git worktree add <path> <branch>` を使う。
7. remote branchだけが存在する場合は `git worktree add --track -b <branch> <path> origin/<branch>` を使う。
8. local、remoteのどちらにも存在しない場合は `git worktree add -b <branch> <path> <base>` を使う。
9. 作成先で `git status --short --branch` と `git rev-parse --show-toplevel` を実行し、branch、upstream、pathを検証する。
10. 元worktreeのdirty状態が変化していないことを再確認する。

### 4. 変更混入を防ぐ

- 新しい依頼は、既存作業branchではなく最新baseから作ったworktreeで開始する。
- 現在のworktreeがdirtyでも、既存変更を触らずに別worktreeを作れる場合はそのまま分離する。
- 変更が誤ったworktreeに既に入っている場合は、対象fileと差分を列挙して停止する。commit、patch、stashのどれで移すかは変更の帰属を確認してから決める。
- 同じbranchを複数worktreeへcheckoutしようとしない。

### 5. 状態を確認する

1. `git worktree list --porcelain` の各pathとbranchを一覧化する。
2. 対象worktreeごとに `git status --short --branch` を確認する。
3. `prunable` がある場合はpathが実在するか確認し、metadataだけがstaleかを判定する。
4. `git worktree prune --dry-run` で削除候補を確認する。実行は候補がstale metadataだけだと確認できた場合に限る。

### 6. merge後に整理する

1. PRが指定されていれば `gh pr view <PR> --json state,mergedAt,headRefName,baseRefName` でmergeを確認する。
2. PRがない場合は `git merge-base --is-ancestor <branch> origin/<base>` でmerge済みか確認する。
3. primary worktreeで `git pull --ff-only origin <base>` を使い、base branchをfast-forward更新する。
4. 対象worktreeの `git status --short --branch` がcleanであることを確認する。dirtyなら削除しない。
5. `git worktree remove <exact-path>` でworktreeを削除する。
6. `git branch -d <branch>` でlocal branchを削除する。
7. ユーザーがmerge後の完全整理を依頼している場合は `git push origin --delete <branch>` でremote branchも削除する。remote側で既に削除済みならその事実を報告する。
8. `git worktree list --porcelain` と `git branch -vv` で最終状態を確認する。

## 検証

- 作成時は指定pathがworktree一覧に存在し、期待branchをcheckoutしている。
- 元worktreeと新worktreeの両方で、作業開始前の未コミット変更が保護されている。
- 整理時は対象pathだけがworktree一覧から消え、他のworktreeが残っている。
- 削除したbranchがmerge済みで、同名branchが別worktreeに紐づいていない。
- `git status`、`git worktree list`、`git branch -vv` の結果を完了報告へ含める。

## 発火テスト例

発火すべき:

- 「新しいworktreeを作って別PRとして作業してください」
- 「今の変更を混ぜずにworktreeを切ってください」
- 「PR #123をmergeしたのでworktreeとbranchを整理してください」
- 「どのbranchがどのworktreeで開かれているか確認して」
- 「staleなworktree metadataを安全に片付けて」

発火すべきでない:

- 「現在のbranchでテストを実行して」
- 「このPRの本文を作って」
- 「未コミット差分を別branchへ移して」
- 「mainから通常のbranchを作って」
- 「repositoryをcloneして」

## 失敗時

- pathが既に存在する場合は内容を上書きせず、別path候補を選ぶ。
- branchが別worktreeで使用中なら、該当pathを報告して処理を止める。
- dirtyなworktreeは削除せず、残っているfileを報告する。
- mergeを確認できなければbranchを残し、確認に必要なPRまたはbaseを示す。
- stale metadataか実在するworktreeか判断できなければpruneしない。

## 関連 skill

- `issue-to-pr`: issue起点で実装からPR提出まで進める。
- `create-pr`: 分離したbranchからPRを作成する。
- `git-diff`: worktree内のbranch差分を確認する。
- `local-dev-ops`: worktreeごとのlocal開発環境を起動・停止する。
