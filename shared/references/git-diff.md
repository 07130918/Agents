# git-diff

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# /git-diff スキル

現在のブランチとベースブランチの差分を表示し、日本語サマリーを生成する。

## 手順

1. ベースブランチ決定: `git show-ref --verify --quiet refs/heads/develop` → 成功なら `develop`、失敗なら `main`
2. 以下を順に表示:
   - `git diff --name-status <base>...HEAD` (変更ファイル一覧)
   - `git diff --stat <base>...HEAD` (変更統計)
   - `git log --oneline <base>..HEAD` (コミット履歴)
   - `git diff <base>...HEAD --no-color` (差分詳細)
3. 差分全体を読み、日本語サマリーを生成

## サマリー項目

1. **主な変更点の概要** — どのような機能や修正か (1〜2行)
2. **追加された機能** — 新しいファイル/機能
3. **修正された内容** — バグ修正・既存機能の改善
4. **削除された内容** — あれば記載 (なければ「なし」)

## 出力ひな型

```
## 差分対象: '<branch>' vs '<base>'

### 変更ファイル
{git diff --name-status}

### 統計
{git diff --stat}

### コミット履歴
{git log --oneline}

### 変更内容のサマリー
1. 主な変更点の概要: ...
2. 追加された機能: ...
3. 修正された内容: ...
4. 削除された内容: なし / ...
```

## Claude Code 版

# /git-diff

現在のブランチとベースブランチ (`develop` 優先、無ければ `main`) の差分を表示し、日本語サマリーを生成する。

## 手順

1. `current_branch=$(git branch --show-current)`
2. `base_branch=$(git show-ref --verify --quiet refs/heads/develop && echo develop || echo main)`
3. 以下を順に表示
   - `git diff --name-status $base_branch...$current_branch` (変更ファイル)
   - `git diff --stat $base_branch...$current_branch` (統計)
   - `git log --oneline $base_branch..$current_branch` (コミット)
   - `git diff $base_branch...$current_branch --no-color` (本体)
4. 日本語サマリーを以下のセクションで作成
   - 主な変更点の概要
   - 追加された機能
   - 修正された内容
   - 削除された内容 (該当時のみ)

## 関連

- レビュー: `codex-review` / `principle-of-programming-reviewer` skill
- PR 作成: `create-pr` skill
