# skill-trigger-regression

Codex と Claude Code の両方で使う、skill の発火品質を回帰テストするワークフロー。新規作成、description 更新、skill 分割、skill 統合の直後に、発火漏れ・過剰発火・既存 skill との競合を検査する。

## 使う場面

- `create-skill` で新規 skill を作った直後。
- 既存 skill の `description`、発火条件、関連 skill を更新した直後。
- 似た目的の skill が増えて、どれが発火すべきか曖昧になったとき。
- ユーザーが「この skill が勝手に発火する」「必要な時に発火しない」「skill の発火テストをして」と言ったとき。

対象外:

- 実装コードのユニットテスト作成。
- skill 本体の品質改善全般。description 以外の大幅な再設計は `create-skill` または `audit-codex-config` に委譲する。
- セッション履歴から新規 skill を探す作業。これは `discover-skills` に委譲する。

## 入力

- target: skill 名、変更ファイル、または `all`。
- scope: global または現在のリポジトリ。未指定なら変更ファイルから推定する。
- optional context: ユーザーが期待する発火例、発火してほしくない例、競合している skill 名。

## 出力

- 対象 skill と比較対象 skill の一覧。
- 発火回帰マトリクス。
- `PASS` / `WARN` / `FAIL` の判定。
- 必要な description 修正案。
- ユーザーが修正まで依頼している場合だけ、wrapper または reference の最小編集。

## 判定モデル

発火品質は次の 4 種で見る。

- Positive case: 対象 skill が発火すべき依頼。
- Negative case: どの skill も不要、または対象 skill は発火すべきでない依頼。
- Conflict case: 近い skill と競合しそうな依頼。
- Handoff case: 対象 skill が別 skill に委譲すべき依頼。

判定基準:

- `PASS`: 期待 skill が自然に選ばれ、競合 skill より明確に強い。
- `WARN`: 発火はしそうだが、description の語彙や境界が曖昧。
- `FAIL`: 発火漏れ、過剰発火、または競合 skill の方が選ばれそう。

## 手順

### 1. 対象を決める

引数または会話から対象を決める。

- skill 名がある場合は、その skill を target にする。
- `changed-files` の場合は、変更された `SKILL.md` と対応する reference を target にする。
- `all` の場合は、全 skill の description を対象にする。ただし大規模な場合は、最近更新された skill と近い名前の skill から始める。
- `create-skill` から続けて実行する場合は、新規作成または更新した skill を target にし、関連 skill を comparison にする。

### 2. 対象ファイルを読む

共通構成では次を確認する。

```bash
find ~/.agents/skills ~/.claude/skills -maxdepth 2 -name SKILL.md
find ~/.agents/references -maxdepth 1 -name '*.md'
```

読むファイル:

- target の Codex wrapper。
- target の Claude Code wrapper。
- target の reference。
- target の `関連 skill` に出てくる skill。
- 名前、description、使う場面が近い skill。

### 3. description から発火契約を抽出する

次を短く書き出す。

```text
target:
job:
trigger_words:
positive_scope:
negative_scope:
handoff_to:
known_conflicts:
```

この時点で description が「何をする skill か」ではなく「なぜ使うか」だけになっている場合は `WARN` にする。description は自動発火の主要材料なので、用途、トリガー語、非対象、委譲先が前半に入っているほどよい。

### 4. 回帰マトリクスを作る

最低限、次の件数を作る。

- Positive case: 5 件以上。
- Negative case: 5 件以上。
- Conflict case: 3 件以上。
- Handoff case: 2 件以上。

形式:

```markdown
| Case | User request | Expected | Should not trigger | Result | Reason |
|------|--------------|----------|--------------------|--------|--------|
| P1 | ... | target skill | ... | PASS | ... |
```

ユーザーの自然な言い方を優先し、slash command、skill 名明示、曖昧な自然文を混ぜる。

### 5. 競合 skill を評価する

各 case について、対象 skill と比較対象 skill の description だけを読んだ時に、どれが最も選ばれそうかを判断する。

競合しやすいパターン:

- `create-skill` と `skill-trigger-regression`: 作成するのか、作成後の発火品質を検査するのか。
- `discover-skills` と `session-retrospective`: 過去 30 日を分析するのか、今の 1 セッションを振り返るのか。
- `audit-codex-config` と `skill-trigger-regression`: 構造監査か、発火テストか。
- `prompt-engineering` と `skill-trigger-regression`: 指示文一般の改善か、skill 発火の回帰テストか。

### 6. 修正する

ユーザーが修正まで依頼している場合だけ、最小限編集する。

優先順位:

1. wrapper の `description` 先頭に主要 trigger words を追加する。
2. 非対象または委譲先を description 後半に短く入れる。
3. reference の `使う場面` と `対象外` を更新する。
4. 関連 skill に相互リンクを足す。

避けること:

- description を長い仕様書にする。
- 複数 skill に同じ trigger words を広く入れる。
- 競合回避のために対象 skill の役割を不自然に狭める。

### 7. `create-skill` との組み合わせ

`create-skill` で新規 skill を作成または更新したら、次の順で使う。

1. `create-skill` で wrapper、reference、発火すべき例、発火すべきでない例を作る。
2. `skill-trigger-regression <skill-name>` を実行する。
3. `FAIL` があれば description または reference の `使う場面` を修正する。
4. `WARN` が残る場合は、最終報告に残存リスクとして書く。
5. `PASS` した回帰マトリクスを最終報告に要約する。

`create-skill` 側の最終報告には、少なくとも次を含める。

```text
skill-trigger-regression:
- target:
- result:
- fixed:
- residual risk:
```

## 検証

変更後に確認する。

```bash
test -f <codex-skill>/SKILL.md
test -f <claude-skill>/SKILL.md
test -f <reference>
wc -l <codex-skill>/SKILL.md <claude-skill>/SKILL.md <reference>
rg -n 'name:|description:|発火すべき|発火すべきでない|対象外|関連 skill' <changed-files>
rg -n -P '\x{ff08}|\x{ff09}' <changed-files>
```

合格条件:

- wrapper は短い。
- target の positive / negative / conflict / handoff case がある。
- `FAIL` がない。
- `WARN` がある場合は理由と残存リスクが明記されている。
- 全角カッコを使っていない。

## レポート形式

```markdown
## skill-trigger-regression

Target: `<skill-name>`
Result: `PASS` / `WARN` / `FAIL`

| Type | Pass | Warn | Fail |
|------|------|------|------|
| Positive | 5 | 0 | 0 |
| Negative | 5 | 0 | 0 |
| Conflict | 3 | 0 | 0 |
| Handoff | 2 | 0 | 0 |

修正:
- ...

残存リスク:
- ...
```

## 関連 skill

- `create-skill`: 新規 skill 作成と wrapper/reference 設計。
- `audit-codex-config`: 既存設定の構造監査とリファクタ。
- `discover-skills`: セッション履歴から不足 skill を発見する。
- `prompt-engineering`: description と指示文の質を上げる。
- `empirical-prompt-tuning`: 独立評価で発火例と命令文を改善する。
