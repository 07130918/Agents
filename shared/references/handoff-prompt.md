# handoff-prompt

次の Codex / Claude Code セッションが迷わず再開できる handoff prompt を生成する。会話要約だけに頼らず、現在の作業ディレクトリを検査して、git、PR、コンテナ、検証状態、未完了タスク、注意点を Markdown prompt として標準出力へ出す。

## 使う場面

- ユーザーが「引き継ぎ用のプロンプトを出して」「handoff を作って」「次セッションに渡す」「引き継ぎ用に作業をまとめて」と依頼したとき。
- 長い実装、PR 作成、CI 復旧、環境復旧、デプロイ作業の途中または終了時。
- 次のセッションで、branch、PR、未コミット変更、起動中サービス、次アクションを取り違えたくないとき。

対象外:

- セッションから恒久的な学びを抽出して `AGENTS.md`、`CLAUDE.md`、skill、reference に反映する作業。これは `session-retrospective` を使う。
- 新規 skill の作成や更新。これは `create-skill` を使う。
- 過去複数セッションを横断して不足 skill を発見する作業。これは `discover-skills` を使う。

## 入力

- current working directory。
- 現在の会話から分かる直近の目的、ユーザーの意図、注意点。
- git repo、GitHub PR、Docker Compose など、ローカル検査で取得できる事実。
- ユーザーが保存先を明示した場合だけ、保存先 path。

## 出力

- 標準出力に、次セッションへそのまま貼れる Markdown prompt を出す。
- 通常はファイル保存しない。
- ユーザーが「ファイルに保存して」と明示した場合だけ保存する。保存先指定がなければ、作業ディレクトリへ勝手に置かず、確認するか user-global 側の保存先を提案する。

## 優先順位

事実の信頼度は次の順に扱う。

1. コマンドで確認した事実。
2. 直近会話から分かる意図、背景、注意点。
3. 推測。

ルール:

- git / PR / コンテナ状態と会話要約が矛盾する場合は、検査済みの事実を優先する。
- 推測は `推測` と明記する。
- 未確認の項目は `未確認: <理由>` と明記する。
- 失敗した検査は握り潰さず、handoff に失敗理由を残す。

## Redaction

handoff は次セッションへ貼る前提なので、秘密情報の再掲を禁止する。

- Cookie、session token、Authorization header は `[REDACTED]` にする。
- `.env`、Secret Manager、API key、DB password、VAPID private key、OAuth token の値は出さない。
- ユーザーが会話に貼った値でも、秘密情報らしければ出さない。
- URL、branch、PR 番号、file path、コマンド名、秘密値を含まない env var 名は残してよい。
- 「秘密値を設定した」事実は書いてよいが、値は書かない。

## 言語

- `AGENTS.md`、`CLAUDE.md`、明示的ユーザー指示の出力言語を優先する。
- 言語指定がなければ日本語で出力する。
- コマンド名、path、branch、PR URL は原文のまま書く。

## 手順

### 1. 作業ディレクトリを確認する

まず現在地と repo 状態を把握する。

```bash
pwd
git rev-parse --show-toplevel
git status --short --branch
git log --oneline --decorate -8
```

git repo 外なら、`git: 未確認: git repo 外` と書き、会話と filesystem で分かる範囲に限定する。

### 2. 差分と作業対象を確認する

git repo の場合は、作業中の変更を確認する。

```bash
git diff --stat
git diff --name-only
git diff --cached --stat
git diff --cached --name-only
```

branch が base branch と差分を持つ場合は、base を `develop` 優先、なければ `main` として確認する。

```bash
git branch --all --format='%(refname:short)'
git diff <base>...HEAD --stat
git diff <base>...HEAD --name-only
```

未追跡ファイルは、ユーザーや他作業のものか不明なら「触っていない未追跡」として分ける。

### 3. PR 状態を確認する

GitHub CLI が使える場合は、現在 branch の PR を確認する。

```bash
gh pr view <current-branch> --json url,state,isDraft,headRefName,baseRefName,mergeStateStatus,statusCheckRollup,title,number
```

必要に応じて明示 PR 番号も確認する。

```bash
gh pr view <pr-number> --json url,state,isDraft,headRefName,baseRefName,mergeStateStatus,statusCheckRollup,title,number
```

`gh` が未認証、network 不通、PR なしの場合は、未確認理由または PR なしを明記する。

### 4. 実行中サービスを確認する

Docker Compose がある場合だけ確認する。

```bash
test -f docker-compose.yml || test -f compose.yml
docker compose ps
```

dev server やローカル URL がログや compose ports から分かる場合は書く。分からなければ推測で URL を書かない。

### 5. 検証結果を整理する

会話と shell 履歴から分かる範囲で、実行済み検証をまとめる。

書くもの:

- 成功したテスト、lint、type-check、build。
- 失敗したが解決済みのコマンドと原因。
- 未実行の重要検証。

コマンド出力を長く貼らない。要点だけを残す。

### 6. 次セッション用 prompt を作る

次の構成で出力する。

````markdown
# Handoff Prompt

## Context
- repo:
- cwd:
- branch:
- base:
- PR:
- current goal:

## Verified Facts
- ...

## Completed
- ...

## Current State
- git:
- PR checks:
- local services:
- database:

## Changed Files
- ...

## Validation
- passed:
- failed then fixed:
- not run:

## Next Steps
1. ...
2. ...
3. ...

## Do Not Redo
- ...

## Cautions
- ...

## Useful Commands
```bash
...
```
````

必要に応じて、`Current State` に `未確認` を残す。

## 品質チェック

出力前に確認する。

- 秘密値を含んでいない。
- git / PR / Docker の事実と矛盾していない。
- 次に打つべきコマンドが具体的。
- 未確認事項が未確認として書かれている。
- 「何をしないべきか」が書かれている。
- ファイル保存はユーザーが明示した場合だけ。

## 発火すべき例

```text
引き継ぎ用のプロンプトを出して
次セッションに渡せる handoff prompt を作って
この作業を次の Codex に引き継げる形でまとめて
$handoff-prompt
handoff を作って。git と PR の状態も確認して
```

## 発火すべきでない例

```text
このセッションの学びを AGENTS.md に反映して
新しい skill を作って
過去30日のセッションから不足 skill を発見して
README を要約して
PR を作成して
```

## 関連 skill

- `session-retrospective`: セッションの学びを設定や docs に残すか分類するとき。
- `create-skill`: 新規 skill 作成や既存 skill 更新をするとき。
- `git-diff`: 現在 branch の差分サマリーだけを出すとき。
- `create-pr`: PR を作成するとき。
- `skill-trigger-regression`: この skill の description や発火条件を更新した後。
