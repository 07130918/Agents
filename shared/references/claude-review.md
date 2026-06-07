# /claude-review (/clr)

Codex から Claude Code CLI を介して、現在の作業ブランチの差分を Claude にレビューさせる。エイリアス: `/clr`。

## 使う場面

- ユーザーが `/claude-review`、`/clr`、または「Claude にレビューして」と明示したとき。
- Codex の実装後に、別モデルの観点でバグ、設計漏れ、セキュリティ、テスト不足を確認したいとき。
- Claude Code の通常セッション内ではなく、Codex から Claude Code CLI を呼ぶ必要があるとき。

## 対象外

- 変更の修正実装。レビュー結果を受けて修正する場合は、ユーザーに確認してから別タスクとして扱う。
- Claude Code 自身での通常レビュー。Claude Code 上では自己呼び出しせず、通常のレビュー手順を使う。
- `claude ultrareview` の実行。クラウドホスト型の multi-agent review が必要な場合だけ、ユーザーが明示したうえで別途実行する。

## 入力

- 任意の base branch 名。未指定なら `origin/develop`、`develop`、`origin/main`、`main` の順で存在確認し、最初に見つかったものを使う。
- 現在の git worktree。未コミット差分も `git diff <base>...HEAD` には含まれないため、必要なら実行前にユーザーへ確認する。

## 出力

- Claude Code CLI のレビュー結果を日本語で表示する。
- 指摘は重要度 `[高]` / `[中]` / `[低]`、ファイル名、行番号、影響、修正方針を含める。
- 指摘がない場合も、その旨と残存リスクを明記する。

## 手順

1. `command -v claude` で Claude Code CLI が利用可能か確認する。見つからない場合は停止し、Claude Code CLI の導入または認証が必要だと伝える。
2. `git branch --show-current` で現在のブランチを確認する。空または `HEAD` の場合は detached HEAD として明記する。
3. base branch を決める。
   - 引数があればそれを使う。
   - 未指定なら `origin/develop`、`develop`、`origin/main`、`main` の順に `git rev-parse --verify <candidate>` で確認する。
   - どれも存在しなければ停止する。
4. `git diff --name-only <base>...HEAD` を確認する。空なら「レビュー対象の差分がありません」と伝えて停止する。
5. `git diff <base>...HEAD --no-color` でレビュー対象 diff を取得する。
6. diff が 50,000 文字を超える場合は、出力が長くなる可能性を警告する。必要なら主要ファイルに絞るか、差分全体をそのまま送るかをユーザーに確認する。
7. 次のレビュープロンプトと diff を Claude Code CLI に渡す。

```bash
review_prompt_file="$(mktemp)"
{
    cat <<'PROMPT'
あなたは経験豊富なシニアソフトウェアエンジニアです。
以下の git diff を詳細にレビューし、日本語で包括的なコードレビューを提供してください。

制約:
- 指摘は差分に基づけ。推測が必要な場合は推測であることを明記する。
- 些末なスタイル論よりも、バグ、仕様破綻、セキュリティ、運用リスク、テスト不足を優先する。
- コード変更、ファイル編集、コミット、push は行わない。

レビュー観点:
1. バグの可能性: 潜在的なバグ、論理エラー、例外処理の不備
2. パフォーマンス: 性能上の問題、最適化の機会
3. 保守性: 可読性、構造、命名規則、重複コード
4. ベストプラクティス: 言語・フレームワーク固有の規約
5. セキュリティ: 脆弱性、権限検証漏れ、秘密情報露出の可能性
6. テスト: 不足しているテスト、回帰リスク、追加すべき検証

出力形式:
- 指摘を先に出す。重要度を [高] / [中] / [低] で分類する。
- 各指摘にファイル名と行番号、問題、影響、修正方針を含める。
- 指摘がない場合は「重大な指摘はありません」と明記し、残存リスクや未検証事項を書く。
- 最後に短い総評を付ける。

以下がレビュー対象の diff です:
PROMPT
    git diff "${base}"...HEAD --no-color
} > "${review_prompt_file}"

claude -p "$(cat "${review_prompt_file}")" \
    --allowed-tools "Read,Grep,Glob,Bash(git *)" \
    --permission-mode dontAsk \
    --no-session-persistence

rm -f "${review_prompt_file}"
```

8. Claude Code CLI が認証エラー、権限エラー、モデルエラーで失敗した場合は、stderr の要点を示し、Claude Code 側の認証や設定を確認するよう伝える。
9. 結果を Codex の最終回答としてそのまま貼るのではなく、重要な指摘を先頭に保ったうえで読みやすく整えて日本語で表示する。

## 失敗時

- `claude` が見つからない: CLI 未導入または PATH 未設定として停止する。
- 認証エラー: `claude auth` や利用中の認証方式を確認するよう案内する。
- diff が空: レビュー対象なしとして停止する。
- diff が大きすぎる: ファイルを絞る、または base branch を見直す。

## 検証

- `command -v claude` が成功すること。
- `claude --help` に `-p, --print`、`--allowed-tools`、`--permission-mode`、`--no-session-persistence` が表示されること。
- wrapper の参照先 `~/.agents/references/claude-review.md` が存在すること。
- skill 名と directory 名が `claude-review` で一致すること。

## 関連

- `codex-review`: Claude Code から Codex MCP にレビューを依頼する逆方向の skill。
- `principle-of-programming-reviewer`: 普遍的プログラミング原則に基づく追加レビュー。
