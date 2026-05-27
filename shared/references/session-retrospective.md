# session-retrospective

Codex と Claude Code の両方で使う、セッション終了時の振り返りワークフロー。今終わった作業から、AI CLI 設定に残すべき学び、残さない一時情報、次回作業へ渡す要点を仕分ける。

## 使う場面

- 長い実装、バグ調査、PR 作成、CI 復旧、設計相談が終わったとき。
- ユーザーが「このセッションを振り返って」「学びを skill に反映して」「次回に引き継げる形にして」と言ったとき。
- 同じ失敗や調査手順を次回も繰り返しそうなとき。
- セッションの最後に、何を `AGENTS.md`、`CLAUDE.md`、skill、reference、docs、issue に残すべきか判断したいとき。

対象外:

- 過去 30 日のセッション横断分析。これは `discover-skills` に委譲する。
- 既存設定の大規模監査。これは `audit-codex-config` または `audit-claude-config` に委譲する。
- 新規 skill の設計と作成そのもの。これは `create-skill` に委譲する。

## 入力

- current goal: このセッションの目的。
- changed files: 変更ファイル、差分、作成した PR、issue、Asana task。
- commands: 実行した主要コマンド、失敗したコマンド、確認できたテスト。
- decisions: 実装中に決めたこと、捨てた案、制約。
- incidents: ハマった原因、再発しそうな失敗、環境依存。

入力が不足していても、現在の会話、git 状態、変更ファイルから推定できる範囲で進める。

## 出力

標準出力は次の 5 分類にする。

- Keep: 今後も有効な知識。AI CLI 設定や docs に残す候補。
- Do not keep: 今回限りの情報。設定に残さない。
- Update: 既存 `AGENTS.md`、`CLAUDE.md`、skill、reference、docs への追記候補。
- Create: 新規 skill、subagent、script、checklist の候補。
- Handoff: 次回セッションや別 AI CLI に渡す要約。

ユーザーが「反映して」「更新して」「作成して」と明示した場合だけファイル編集まで行う。明示がない場合は提案で止める。

## 手順

### 1. セッションの境界を決める

次を短く確定する。

```text
goal:
repo:
branch:
related_pr_or_issue:
start_assumption:
final_state:
```

git が使える場合は、差分と最近のコミットから補助情報を得る。

```bash
git status --short
git diff --stat
git log --oneline -5
```

### 2. 事実を集める

読む対象:

- 変更ファイル。
- このセッションで触った `AGENTS.md`、`CLAUDE.md`、`SKILL.md`、reference。
- 実行したテストや CI の結果。
- ユーザーが明示した判断、制約、好み。

推測と事実を混ぜない。推測は「推測」として扱う。

### 3. 学びを分類する

各項目を以下のどれかに分類する。

```text
repo-rule:
  AGENTS.md または CLAUDE.md に置く。Codex が毎回知る必要がある短い非自明ルール。

workflow:
  skill または reference に置く。特定状況でだけ必要な手順。

script:
  deterministic に実行したい検査、変換、生成。手順より script が適切。

docs:
  人間向け仕様、設計判断、ADR、運用メモ。

handoff:
  次回作業者向けの一時的な状態共有。

discard:
  今回限り。設定に残さない。
```

判断基準:

- 毎回ロードすべき短い gotcha なら `AGENTS.md` または `CLAUDE.md`。
- 条件付きで必要な手順なら skill。
- 同じ shell 手順を繰り返すなら script。
- プロダクト仕様や意思決定なら docs。
- branch や PR 固有の状態なら handoff。
- 1 回限りのログ、古くなりやすい一時 URL、偶然のエラーは discard。

### 4. 設定へ反映するか決める

編集は次の順で保守的に行う。

1. 既存 skill の reference 追記。
2. 既存 skill の description 微調整。
3. `AGENTS.md` または `CLAUDE.md` の短い gotcha 追記。
4. 新規 skill 候補の提案。
5. 新規 skill 作成は `create-skill` に委譲。

`AGENTS.md` と `CLAUDE.md` に入れる条件:

- コードから推測できない。
- 頻繁に変わらない。
- 1 から 3 行で書ける。
- 消すと AI CLI が次回ミスしそう。

skill に入れる条件:

- 発火条件が明確。
- 特定作業だけで使う。
- 手順、チェックリスト、検証条件がある。
- 既存 skill と重複しない。

### 5. 反映する

ユーザーが反映まで依頼している場合だけ実行する。

- 既存ファイルは編集前に読む。
- 大きな削除や移動は確認する。
- 新規 skill が必要なら `create-skill` を使う。
- 新規または更新した skill は `skill-trigger-regression` で発火品質を確認する。
- 全角カッコを使わない。

### 6. handoff を作る

次回に渡す場合は、次の形式にする。

```markdown
## Handoff

Goal:
State:
Changed files:
Verified:
Known risks:
Next steps:
Do not redo:
```

`Do not redo` には、既に検証済みの仮説、失敗したアプローチ、不要だった調査を入れる。

## レポート形式

```markdown
## Session Retrospective

Keep:
- ...

Do not keep:
- ...

Update candidates:
- ...

Create candidates:
- ...

Handoff:
- Goal:
- State:
- Verified:
- Next:
```

編集した場合は最後に変更ファイルと検証結果を書く。

## 関連 skill

- `create-skill`: 新規 skill 作成と既存 skill 更新。
- `skill-trigger-regression`: 更新した skill の発火品質検査。
- `discover-skills`: 複数セッションを横断して不足 skill を探す。
- `audit-codex-config`: 設定ファイルの構造監査と整理。
- `docs-code-consistency-audit`: docs とコードの事実整合性を監査する。
