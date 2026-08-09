# address-claude-pr-comments

GitHub PRに付いたClaudeのレビューコメントを、修正または説明で処理し、返信してresolveするworkflow。

## 使う場面

- ユーザーがPR番号またはPR URLを渡し、「Claudeレビュー対応」「claudeのコメントを見てresolve」「PRコメント対応」と依頼したとき。
- PR作成後やforce-push後に、Claudeの未解決review threadが残っていないか確認したいとき。

## 対象外

- Claude以外のレビューコメント対応。必要なら別途明示がある場合だけ扱う。
- PRを新規作成する作業。PR作成は `create-pr` を使う。
- CI失敗の調査。CI修正が必要なら `github-actions-ops` または該当プロジェクトの運用手順を使う。

## 入力

- 必須: PR番号またはGitHub PR URL。
- PR番号だけ渡された場合は、現在のgit repositoryを対象repoとして扱う。
- 入力がない場合は、現在ブランチのPRを `gh pr view` で推定する。推定できなければユーザーにPR番号またはURLを1行で依頼する。

## 出力

- 対応したClaude thread数。
- 修正したファイルとコミット/push有無。
- 修正不要として返信した理由。
- 残っている未解決Claude threadの有無。
- 実行した検証コマンド。

## 手順

### 1. PRを特定する

PR URLなら `owner/repo/number` を抽出する。PR番号なら現在repoを使う。

```bash
gh repo view --json nameWithOwner
gh pr view <number-or-url> --json number,url,headRefName,baseRefName,state,isDraft
```

作業前に `git status --short --branch` を確認する。未コミット差分がある場合は、今回のレビュー対応に関係するか判断し、無関係な差分を巻き込まない。

### 2. Claudeの未解決threadを取得する

GitHub GraphQLでreview threadを取得する。`author.login == "claude"` のコメントを含む、未解決threadを対象にする。outdatedでも未解決なら対象に含める。

```bash
gh api graphql \
  -F owner="$OWNER" \
  -F repo="$REPO" \
  -F number="$PR_NUMBER" \
  -f query='
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first: 30) {
            nodes {
              id
              body
              createdAt
              url
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}'
```

通常のreview本文も読む。threadに紐づかない総評に実装上の注意が書かれている場合がある。

```bash
gh pr view <number-or-url> --json reviews,comments
```

### 3. 各コメントを判定する

各threadについて、必ず次のどちらかに分類する。

- 修正必要: バグ、アクセシビリティ、テスト不足、保守性の実害、仕様との不一致がある。
- 修正不要: 誤読、既に修正済み、スコープ外、別issueで扱うべき、現行仕様を変えるリスクが高い。

修正不要でも放置しない。理由を短く明示して返信し、resolveする。

### 4. 修正する場合

修正は最小差分にする。無関係な整形、依存追加、別issueの先取りを混ぜない。

修正後はリポジトリ規約に沿って検証する。最低限:

```bash
npm run check -- <changed-files>
npm run type-check
npm run test:run -- <related-tests>
git diff --check
```

プロジェクトで `make ci`、`make db-check`、`npm audit --audit-level=moderate` が必須なら実行する。依存追加がある場合は必ずauditする。

コミット済みPRなら、レビュー対応コミットを作成してpushする。小さなPRで直前コミットをamendする方が自然な場合だけ、`--force-with-lease` を使う。無関係差分をstageしない。

### 5. 返信してresolveする

修正した場合の返信は、何を直し、どの検証を通したかを1から3文で書く。

修正不要の場合の返信は、なぜ不要か、必要なら代替issueまたは現行仕様を1から3文で書く。

返信:

```bash
gh api graphql \
  -F threadId="$THREAD_ID" \
  -f body="$BODY" \
  -f query='
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId,
    body: $body
  }) {
    comment {
      id
    }
  }
}'
```

resolve:

```bash
gh api graphql \
  -F threadId="$THREAD_ID" \
  -f query='
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}'
```

### 6. 再取得して完了確認する

返信・resolve後に、もう一度threadを取得する。

- 未解決Claude threadが0件なら完了。
- force-push後に新しいClaudeコメントが増えていたら、同じ手順を繰り返す。
- GitHub API認証が切れた場合は `gh auth status` を確認し、ユーザー操作が必要なら `gh auth refresh -h github.com` を依頼する。

## 判断基準

- コメントが正しいなら、低優先でも原則直す。小さく直せる指摘を放置しない。
- 指摘が正しくない場合は、コード上の根拠または仕様上の根拠を示してresolveする。
- outdated threadでも、未解決なら対応対象にする。既に修正済みの場合は「現headで対応済み」と返信してresolveする。
- レビュー返信前に、修正がpush済みか確認する。未pushの修正に対して「修正済み」と返信しない。

## 完了報告

最終報告には次を含める。

1. 対象PR URL
2. Claude未解決threadの対応件数
3. 修正した内容または修正不要の理由
4. 検証結果
5. 残っている未解決Claude threadの有無

## 発火例

```text
$address-claude-pr-comments https://github.com/org/repo/pull/123
PR #123 のClaudeレビューコメントを対応してresolveしてください
claudeからプルリクエストにレビューコメントがついていたら対応して。対象は https://github.com/org/repo/pull/123
```

## 発火しない例

```text
PRを作成してください
CIが落ちているので直してください
この差分をコードレビューしてください
```

## 関連skill

- `create-pr`: PR作成。
- `github-actions-ops`: GitHub Actions失敗の調査。
- `pr-risk-reviewer` agent: ローカル差分のコードレビュー。
