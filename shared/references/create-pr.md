# create-pr

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# /create-pr スキル

現在のブランチと既定ベースブランチの差分を分析し、日本語のタイトル・本文でプルリクエストを作成する。

## 前提条件

- 現在のブランチがベースブランチではない
- 変更がコミット済み
- PR 作成前に、ローカル開発環境で対象機能の動作確認を実施済みである。実施できない場合は、理由と代替確認内容をPR本文に明記する
- `gh` CLI がインストール・認証済み

## 手順

1. `git branch --show-current` で現在のブランチを取得する。空、`HEAD`、ベースブランチなら停止する
2. ベースブランチを決める:
   - `git symbolic-ref refs/remotes/origin/HEAD` で取得できる既定ブランチを優先
   - 失敗時は `develop` があれば `develop`、なければ `main`
3. 変更把握:
   - `git diff --name-only <base>...HEAD`
   - `git diff --stat <base>...HEAD`
   - `git log --oneline <base>..HEAD`
   - 必要に応じて `git diff <base>...HEAD --no-color`
4. `.github/pull_request_template.md` があれば読み、テンプレート構造を維持して本文を埋める。なければ下の標準テンプレートを使う
5. PR本文の動作確認欄に、ローカル開発環境で確認した画面/API、実行結果、確認できなかった場合の理由を具体的に書く
6. 最新コミットメッセージをタイトル候補にしつつ、**全コミットの差分**を見てタイトルを生成する
7. リモート未プッシュなら `git push -u origin <branch>`
8. `gh pr create --base <base> --title "..." --body-file <tmp-file>` で作成する
9. PR URL を出力する

## 標準本文テンプレート

`.github/pull_request_template.md` がない場合は以下を使う:

```
## 概要
{変更の要約}

## 変更内容
- {主要な変更}

## 動作確認
- {実行したコマンドや確認内容}

## レビュー観点
- {重点的に見てほしい点}
```

## 注意

- タイトルは簡潔にする
- 最新コミット 1 件だけでなく **全コミットの差分** で判断する
- 秘密情報 (`.env`, 認証情報) が含まれていれば警告する
- `--no-verify` は使わない

## Claude Code 版

# /create-pr

現在の作業ブランチとベースブランチの差分から、プロジェクトの PR テンプレートに沿った PR を日本語で作成する。

## 手順

1. `current_branch=$(git branch --show-current)`
2. ベースブランチ取得: `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` (失敗時は `main`)
3. `git diff <base>...HEAD` で差分把握
4. `.github/pull_request_template.md` があれば Read で読み込み、フォーマットに従う
5. ブランチ名から数字 prefix を抽出 (`223/foo` → `[223]`)
6. `gh pr create --base <base> --title "[prefix] 作業内容" --body "<テンプレ準拠本文>"`

## ルール

- タイトル・本文は日本語
- PR 本文に「Created by Claude Code」等の自動署名を入れない
- ブランチ名に数字 prefix がない場合は省略
- `.github/pull_request_template.md` が無いプロジェクトは標準フォーマット (概要 / 変更内容 / 動作確認) で作成
- 変更内容を git diff で正確に把握してから記述する

## 関連

- 差分確認: `git-diff` skill
- 多段 PR 設計: `docs-driven-development` skill
