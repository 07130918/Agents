# Claude Code グローバル設定

全プロジェクトに適用される Claude Code の共通指示。

## 言語

IMPORTANT: 英語で思考し、日本語で出力する。コード内コメント/ドキュメントも日本語。

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
全角カッコ(U+FF08/U+FF09)は使わない。半角カッコ `()` で統一する。

## コードレビュー順序

中規模以上の変更・重要変更・PR 前は `/codex-review` → `/popr` の順で実行する。

## コミットメッセージ

IMPORTANT: コミットメッセージは「プレフィックス + 日本語」形式で書く。

形式: `<prefix>: <日本語の要約>`

- `feat:` 新機能の追加
- `fix:` バグ修正
- `chore:` ビルド・依存関係・設定など雑務
- `refactor:` 挙動を変えないリファクタリング
- `perf:` パフォーマンス改善
- `docs:` ドキュメントのみの変更
- `test:` テストの追加・修正
- `style:` フォーマット・空白など (挙動に影響しない)
- `build:` ビルドシステム・依存関係の変更
- `ci:` CI 設定の変更
- `revert:` 以前のコミットの取り消し

例:
- `feat: ユーザープロフィール編集画面を追加`
- `fix: ログイン後のリダイレクトが効かない問題を修正`
- `chore: react-hook-form を 7.75.0 に更新`
- `refactor: 検索フィルタのロジックを hooks に切り出し`

ルール:
- 件名は 50 文字程度を目安に簡潔に書く (本文で詳細補足は OK)
- 「何を」「なぜ」が分かる動詞 + 目的語を心がける (例: 「修正」「追加」「更新」「削除」)
- 末尾の句点は付けない
- 英語のみ・プレフィックス無しのメッセージは作らない

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
