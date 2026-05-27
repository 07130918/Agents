# GitHub Actions 運用

`gh` CLI を使った Actions 調査・復旧の標準フロー。Bash で `gh` を直接叩くため、Bash ツール経由で実行する。

## 失敗調査の標準フロー

```bash
# 1. 直近の失敗 run を見つける
gh run list --status failure --limit 5
gh run list --workflow auto-trading.yml --status failure --limit 5

# 2. 失敗ステップのログだけ見る
gh run view <run-id> --log-failed

# 3. 全ログを見る (大きい)
gh run view <run-id> --log

# 4. artifact をダウンロード (logs/, data/csv など)
gh run download <run-id>
gh run download <run-id> -n trading-logs-<run-number>

# 5. 修正 PR をマージしたら手動再実行
gh workflow run auto-trading.yml
gh run watch  # 直近 run を follow
```

## 対話的に run を選ぶ

```bash
gh run list --limit 20              # 一覧
gh run watch                         # in-progress / queued の最新を follow
gh run rerun <run-id> --failed       # 失敗ジョブのみ再実行
gh run rerun <run-id>                # 全部再実行
```

## actions/cache@v4 のキー戦略

```yaml
- uses: actions/cache@v4
  with:
    path: |
      data/bot_state.json
      data/bot_state.json.backup
    # 毎回ユニークなキー → 毎 run 必ず保存する
    key: bot-state-${{ github.repository }}-${{ github.run_id }}
    restore-keys: |
      bot-state-${{ github.repository }}-
```

**ポイント**:
- `key` を `github.run_id` で毎回ユニークにすると、保存は必ず行われる (cache hit しても save する v4 の挙動)
- `restore-keys` は prefix 一致で最新を引く。run 間で状態を引き継ぐとき必須
- cache hit 確認: `gh run view <run-id> --log | grep -i "cache hit\|cache restored"`

## workflow_dispatch のみ運用

cron を停止して手動実行のみにする運用 (検証期間など):

```yaml
on:
  # schedule:
  #   - cron: '0 0,4,8,12,16,20 * * *'   # 検証クリアまで停止
  workflow_dispatch:
```

理由をコメントで残す (停止条件がいつ解除されるか後から分かるように)。

## 失敗時 Issue 自動作成

`actions/github-script@v7` で失敗時に Issue を作るテンプレート:

```yaml
permissions:
  contents: read
  issues: write   # Issue 作成のため
  actions: read   # ログ取得のため

# (jobs.steps の最後に)
- name: Notify on failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      const runUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
      await github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: `[${context.workflow}] 定期実行が失敗しました (run #${context.runNumber})`,
        body: `Run: ${runUrl}\n\n対処後にクローズしてください。`,
        labels: ['bug', 'ci-failure'],
      });
```

リポジトリの「Issues」を Watch しているユーザーに通知が飛ぶ。

## permissions ブロック (least privilege)

ワークフローで使う最小権限のみ宣言:

```yaml
permissions:
  contents: read       # checkout のため
  issues: write        # Issue を作成する場合のみ
  actions: read        # cache や log を読む場合のみ
  pull-requests: write # PR コメント / レビューする場合のみ
```

省略すると default (read-only or all、リポジトリ設定依存) になる。明示するのが安全。

## Secrets 管理

```bash
gh secret list                                    # 一覧
gh secret set BITFLYER_API_KEY                    # 対話入力
gh secret set BITFLYER_API_KEY --body "$VALUE"    # 値直接 (履歴注意)
gh secret set BITFLYER_API_KEY < /path/to/file    # ファイルから
gh secret delete BITFLYER_API_KEY
```

ワークフローでの使用:

```yaml
env:
  BITFLYER_API_KEY: ${{ secrets.BITFLYER_API_KEY }}
```

❌ secrets を `echo` で出力したり log に残したりしない (Actions が自動マスクするが冗長な変換は通り抜ける)。

## artifact のアップロード

```yaml
- name: Upload logs
  if: always()                                    # 失敗時でも上げる
  uses: actions/upload-artifact@v6
  with:
    name: logs-${{ github.run_number }}
    path: |
      logs/*.log
      data/*.csv
    retention-days: 30
```

`if: always()` を忘れると失敗時に artifact が残らず調査できない (頻出ミス)。

## 良くある詰まりどころ

| 症状 | 原因 | 対処 |
|---|---|---|
| `Resource not accessible by integration` | `permissions:` 不足 | 必要な権限を `write` に |
| `gh run watch` が反応しない | run が queued でまだ start していない | `gh run list` で id 確認後 `gh run view <id> --log` |
| cache が保存されない | `key` が hit したまま v3 以前を使っている | v4 に上げる、または `key` をユニークに |
| secrets が空文字 | secret 名のタイポ / repo/env mismatch | `gh secret list` で正確な名前を確認 |
| Issue が作られない | `permissions: issues: write` 漏れ | 追加 |
