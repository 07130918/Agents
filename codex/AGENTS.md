# Codex グローバル設定

全プロジェクトに適用される Codex の共通指示。

## 言語

IMPORTANT: 英語で思考し、日本語で出力する。コード内コメント/ドキュメントはプロジェクト規約と周辺ファイルの言語を優先し、規約がない場合は日本語で書く。

## Python 実行環境

IMPORTANT: Python 実行は常に `uv` を使う。

- ✅ `uv run python <script>` / `uv run pytest` / `uv run python -m flask run`
- ✅ `uv pip install <pkg>`
- ❌ `python3` / `python` / 素の `pip install`

## コーディング規約

### 絵文字
ドキュメント・コード内で使う絵文字は次の3種のみ:

- ✅ 成功・推奨・メリット
- ⚠️ 警告・注意
- ❌ エラー・非推奨

### 文字種
全角カッコ `()` は禁止。半角カッコ `()` で統一する。

## コミットメッセージ

IMPORTANT: コミットメッセージは `プレフィックス: 日本語の要約` の形式で書く。

- `feat: xxx機能を追加`
- `fix: xxxのバグを修正`
- `chore: xxxの依存関係を更新`

## コードレビュー順序

中規模以上の変更・重要変更・PR 前は `/codex-review` → `/popr` の順で実行する。

## GitHub PR 作成

- PR 作成時は必ず `07130918` を assignee に設定する。
- PR 作成時は変更内容に応じて必要なラベルを付与する。例: リファクタは `refactor`、バグ修正は `bug`、機能追加は `enhancement`。
- PR 作成前に、ローカル開発環境で対象機能の動作確認を行い、PR 本文の動作確認欄に実施内容を書く。ローカルで確認できない事情がある場合は、その理由と代替確認内容を明記する。
- Copilot へのレビュー依頼はリポジトリごとに統合アプリケーションが異なるため、Codex からは行わない。必要な場合はユーザーが手動で行う。

## バグ調査

- 修正前に根本原因を特定する(計画フェーズを省略しない)。症状ではなく原因を直す
- 最初に疑うパターン:
  1. 環境変数の未設定/誤設定
  2. Chakra UI v3 prop 変更の適用漏れ
  3. SQL のカンマ漏れ・NULL 扱いのミス
  4. キャッシュ不整合 (Next.js `.next`)
- 深掘りが必要なら `bug-investigator` エージェントを使う

## DB 変更

- ✅ マイグレーションファイルを必ず作成する
- ❌ 直接 `ALTER TABLE` を本番 DB に実行しない
- ✅ 相関サブクエリより JOIN を優先する (Cartesian 積・N+1 回避)
- ✅ `NOT NULL` カラムには必ず `defaultTo()` を設定する

## Skills 共有

- Skill の本体は `~/.agents/references/*.md` に集約する。
- `~/.agents/skills/*/SKILL.md` と `~/.claude/skills/*/SKILL.md` は frontmatter と参照指示だけを置く。
