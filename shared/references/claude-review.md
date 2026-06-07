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
5. `git diff --name-status <base>...HEAD`、`git diff --stat <base>...HEAD`、`git diff <base>...HEAD --no-color` でレビュー対象を取得する。
6. 原則として default は **fast diff review** にする。Claude に tool access を渡さず、提示した diff だけでレビューさせる。
7. diff が 25,000 文字以下なら、次のレビュープロンプトと diff を 1 回で Claude Code CLI に渡す。

```bash
review_prompt_file="$(mktemp)"
{
    cat <<'PROMPT'
あなたは経験豊富なシニアソフトウェアエンジニアとして、PR のマージ可否を判断するコードレビューを行います。
目的は称賛や一般論ではなく、提示された diff から根拠を持って説明できる重大な問題を見つけることです。

制約:
- コード変更、ファイル編集、コミット、push は行わない。
- tool は使わない。提示された変更概要と diff だけで判断する。
- 指摘は diff に根拠があるものだけにする。根拠が弱い推測は「注意点」または「質問」に分ける。
- 些末なスタイル、好み、一般的ベストプラクティスだけの指摘は出さない。
- 周辺コードが必要で断定できない場合は、推測で指摘せず「質問」または「要追加確認」に分ける。
- 最終出力前に各指摘を自己検証し、実際の障害やレビューアクションにつながらない弱い指摘は削除する。

レビュー観点:
1. 正確性: 仕様破綻、境界条件、状態遷移、例外処理、型や null の扱い
2. セキュリティ: 認可漏れ、入力検証、秘密情報露出、インジェクション、危険な外部連携
3. データ整合性: migration、schema、transaction、idempotency、並行実行、互換性
4. API/UX 互換性: 既存呼び出し元、レスポンス形式、feature flag、ロール別挙動
5. パフォーマンス/運用: N+1、不要な I/O、ログ、監視、失敗時の復旧性
6. テスト: 変更で壊れ得るケースに対する不足テスト

重要度の基準:
- [高]: データ破壊、認可漏れ、セキュリティ事故、本番停止、主要フローの明確な破綻、後方互換性の重大な破壊。
- [中]: 特定条件でのバグ、回帰、性能劣化、運用上の問題、重要なテスト不足。
- [低]: 軽微な不具合、将来の保守リスク、局所的な改善。ただし好みだけの指摘は含めない。

出力形式:
1. `変更意図`: 変更ファイルと diff から推定した意図を 2 から 4 行で書く。
2. `指摘`: 重大度順に並べる。各項目は `[高|中|低] file:line - タイトル`、`問題`, `影響`, `根拠`, `修正方針` を含める。
3. `テスト不足`: 指摘に含めなかったが追加すべきテストがあれば書く。
4. `質問`: 判断に必要な仕様確認があれば書く。
5. `総評`: 1 から 3 行でマージ判断に必要な要約を書く。

指摘がない場合:
- 「重大な指摘はありません」と明記する。
- それでも残るリスク、未確認事項、追加するとよいテストを簡潔に書く。

以下が変更概要です:
PROMPT
    git diff --name-status "${base}"...HEAD
    printf '\n'
    git diff --stat "${base}"...HEAD
    printf '\n以下がレビュー対象の diff です:\n\n'
    git diff "${base}"...HEAD --no-color
} > "${review_prompt_file}"

claude -p \
    --tools "" \
    --permission-mode dontAsk \
    --no-session-persistence \
    --output-format text \
    < "${review_prompt_file}"

rm -f "${review_prompt_file}"
```

8. diff が 25,000 文字を超える場合は、全体を一括で渡さない。`git diff --name-only <base>...HEAD` の順に、次の優先度でファイル単位または小さな batch に分割する。
   - 高優先: 認証、認可、API route、DB/migration/query、外部連携、ファイルアップロード、課金、メール、ジョブ、テスト。
   - 中優先: shared helper、状態管理、UI のロジック部分、設定。
   - 低優先: 定数だけの変更、文言、docs、生成物、lock file。
9. 分割レビューでは 1 回の Claude 入力を概ね 20,000 文字以下にする。大きい 1 ファイルは、そのファイルだけを 1 回で渡し、さらに止まる場合は変更概要と主要 hunk に絞る。
10. 長い diff で Claude が返らない場合、同じ入力で再試行しない。tool-free のまま batch を小さくする。2 回連続で返らないファイルは skip し、最終結果に「未完了」として明記する。
11. deep review が必要な場合だけ、対象を 1 ファイルまたは 1 論点に絞って `--allowed-tools "Read,Grep,Glob,Bash(git *)"` を使う。全体 diff に tool access を渡してはいけない。
12. Claude Code CLI が認証エラー、権限エラー、モデルエラーで失敗した場合は、stderr の要点を示し、Claude Code 側の認証や設定を確認するよう伝える。
13. 結果を Codex の最終回答としてそのまま貼るのではなく、重要な指摘を先頭に保ったうえで、未レビュー範囲と分割方法も含めて日本語で表示する。

## 分割レビュー用プロンプト差分

分割時は上記 prompt の最後に次を追加する。

```text
今回は大きな diff の分割レビューです。
対象 batch だけをレビューしてください。batch 外のファイルについて推測で指摘しないでください。
この batch でレビューできなかったリスクがあれば「未確認リスク」に短く書いてください。
```

deep review 時は次を追加する。

```text
今回は deep review です。
必要最小限の Read/Grep/Glob/Bash(git *) だけを使い、対象ファイルの呼び出し元、関連テスト、設定を確認してください。
調査範囲を広げすぎないでください。レビュー目的に直接関係しない探索は止めてください。
```

## 失敗時

- `claude` が見つからない: CLI 未導入または PATH 未設定として停止する。
- 認証エラー: `claude auth` や利用中の認証方式を確認するよう案内する。
- diff が空: レビュー対象なしとして停止する。
- diff が大きすぎる: 一括実行せず、優先度順に batch review へ切り替える。
- Claude が返らない: 同じ入力を再実行せず、tool-free、小 batch、主要 hunk の順で縮小する。完全レビューできない場合は未完了範囲を明記する。

## 検証

- `command -v claude` が成功すること。
- `claude --help` に `-p, --print`、`--tools`、`--allowed-tools`、`--permission-mode`、`--no-session-persistence` が表示されること。
- 短い prompt が `printf '...' | claude -p --tools "" --permission-mode dontAsk --no-session-persistence --output-format text` で返ること。
- wrapper の参照先 `~/.agents/references/claude-review.md` が存在すること。
- skill 名と directory 名が `claude-review` で一致すること。

## 関連

- `codex-review`: Claude Code から Codex MCP にレビューを依頼する逆方向の skill。
- `principle-of-programming-reviewer`: 普遍的プログラミング原則に基づく追加レビュー。
