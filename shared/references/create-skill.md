# create-skill

Codex と Claude Code の両方から呼び出せる skill を作成・更新するためのワークフロー。原則として、この PC の共通構成では本体を `~/.agents/references/<skill-name>.md` に置き、`~/.agents/skills/<skill-name>/SKILL.md` と `~/.claude/skills/<skill-name>/SKILL.md` は短い wrapper にする。

## 使う場面

- ユーザーが「skill を作って」「この手順を skill 化して」「Claude Code と Codex 両方で呼べるようにして」と依頼したとき。
- 既存 skill の description、発火条件、参照構造、supporting files を改善するとき。
- 長くなった `AGENTS.md`、`CLAUDE.md`、手順メモ、チェックリストを on-demand の skill に分離するとき。

## 公式ベストプラクティスの要点

- skill は 1 つの仕事に集中させる。
- `description` は自動発火の判定に使われるため、先頭に用途・トリガー語・非対象を明確に書く。
- `SKILL.md` は required metadata と実行手順の入口にし、長い知識は `references/`、確定的な処理は `scripts/`、成果物テンプレートは `assets/` に分ける。
- instruction-only をデフォルトにする。外部ツールや決定的処理が必要な場合だけ script を追加する。
- 手順は命令形で、入力・出力・検証条件を明示する。
- 作成後は「発火すべき依頼」と「発火すべきでない依頼」を両方テストする。
- 大規模コードベースでは常時ロードされる文書を薄くし、専門知識は skill に逃がす。root の `AGENTS.md` / `CLAUDE.md` は重要な pointer と gotcha に絞る。

Sources:
- https://developers.openai.com/codex/skills
- https://code.claude.com/docs/en/skills
- https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start

## 事前確認

1. 既存構成を確認する。

```bash
find . -path '*/.agents/skills/*/SKILL.md' -o -path '*/.claude/skills/*/SKILL.md'
find ~/.agents/skills ~/.claude/skills -maxdepth 2 -name SKILL.md
find ~/.agents/references -maxdepth 1 -name '*.md'
```

2. 同名または近い目的の skill がある場合は新規作成ではなく更新を優先する。
3. 仕様が不足していても、次のデフォルトで進められるなら質問せず実装する。

デフォルト:

- scope: ユーザーが「この PC 全体」「グローバル」と言ったら global、それ以外は現在のリポジトリ。
- target: Codex と Claude Code の両方。
- structure: 共通 reference + 両 CLI wrapper。
- content type: instruction-only。
- scripts: 同じ処理を毎回書く、または deterministic reliability が必要な場合だけ追加。
- validation: frontmatter、参照パス、行数、発火例を確認。

## 名前と配置

名前ルール:

- lowercase letters、numbers、hyphens のみ。
- 64 文字以下。
- 動詞 + 対象にする。例: `create-skill`, `review-security`, `sync-docs-code`。
- 既存 system skill と同名にしない。Codex には `skill-creator` があるため、この PC では skill 作成用の共通 skill 名を `create-skill` にする。

この PC の global 配置:

```text
~/.agents/references/<skill-name>.md
~/.agents/skills/<skill-name>/SKILL.md
~/.claude/skills/<skill-name>/SKILL.md
```

プロジェクト固有で同じ共通構成を使う場合:

```text
<repo>/.agents/references/<skill-name>.md
<repo>/.agents/skills/<skill-name>/SKILL.md
<repo>/.claude/skills/<skill-name>/SKILL.md
```

単一 CLI だけが対象の場合は、その CLI の標準配置だけを作る。

## 作成フロー

### 1. 要件を 1 枚にまとめる

作成前に次を内部で確定する。

```text
name:
scope:
target_cli:
job:
trigger_examples:
non_trigger_examples:
inputs:
outputs:
side_effects:
tools_needed:
supporting_files:
validation:
```

質問は最大 3 つまで。実装場所、破壊的副作用、認証情報の扱いが不明な場合だけ質問する。

### 2. description を先に書く

description は skill の発火品質を決める。次を 1 から 3 文で書く。

- 何を作るか、または何を実行するか。
- いつ使うか。ユーザーが言いそうな語を含める。
- 使わない条件が重要なら明記する。

良い例:

```yaml
description: Codex と Claude Code の両方で使える skill を作成・更新する。共通 reference + CLI 別 SKILL.md wrapper 構成、frontmatter 設計、発火条件、supporting files、検証まで行う。「skillを作って」「手順をskill化」「Claude/Codex両対応」と言われたときに使う。
```

悪い例:

```yaml
description: skill を作る。
```

### 3. wrapper を作る

共通構成では wrapper に長い手順を書かない。CLI ごとの frontmatter 差分だけ許容する。

Codex 側 template:

```markdown
---
name: <skill-name>
description: <description>
argument-hint: <必要な場合だけ>
allowed-tools: Read Write Edit Glob Grep Bash(find *) Bash(wc *) Bash(mkdir *)
---

# <skill-name>

この skill の詳細手順は `<reference-path>` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
```

Claude Code 側 template:

```markdown
---
name: <skill-name>
description: <description>
argument-hint: <必要な場合だけ>
allowed-tools: Read Write Edit Glob Grep Bash(find *) Bash(wc *) Bash(mkdir *)
---

# <skill-name>

この skill の詳細手順は `<reference-path>` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
```

副作用が大きく、ユーザーの明示呼び出しだけにしたい workflow では Claude Code 側に `disable-model-invocation: true` を追加する。Codex app 用に implicit invocation を止めたい場合は `agents/openai.yaml` の `policy.allow_implicit_invocation: false` を検討する。

### 4. reference を作る

reference には実際の workflow を置く。標準構成:

```markdown
# <skill-name>

## 使う場面

## 入力

## 出力

## 手順

## 検証

## 失敗時

## 関連 skill
```

内容は短く、命令形にする。長い API 仕様、ファイル一覧、大量の例は reference 内でも分割する。

### 5. supporting files を選ぶ

次の基準で追加する。

- `references/`: 詳細仕様、長いチェックリスト、ドメイン知識、API 仕様。
- `scripts/`: 毎回同じ機械処理、危険な順序依存、構文検証、テンプレート生成。
- `assets/`: 成果物テンプレート、画像、フォント、サンプルファイル。

追加しないもの:

- 作成経緯だけの README。
- 重複した quick reference。
- 実行されない長い bash 手順。
- モデルが既に知っている一般論。

### 6. 検証する

作成後に必ず確認する。

```bash
test -f <codex-skill>/SKILL.md
test -f <claude-skill>/SKILL.md
test -f <reference>
wc -l <codex-skill>/SKILL.md <claude-skill>/SKILL.md <reference>
rg -n 'name:|description:|~/.agents/references|.agents/references' <codex-skill>/SKILL.md <claude-skill>/SKILL.md
rg -n -P '\x{ff08}|\x{ff09}' <changed-files>
```

判定基準:

- wrapper は短い。目安 20 行以下。
- reference は必要十分。目安 500 行以下。超えるなら分割する。
- `name` と directory name が一致する。
- description の先頭に trigger words がある。
- 参照パスが存在する。
- この PC では全角カッコを使わない。
- 絵文字を使う場合は `✅`、`⚠️`、`❌` のみ。

### 7. 発火テストを設計する

最終報告に、最低限この 2 種を含める。

発火すべき例:

```text
この手順を Codex と Claude Code の両方で使える skill にしてください。
/create-skill security-review
$create-skill docs-audit
```

発火すべきでない例:

```text
この関数のバグを直してください。
README を少し整えてください。
```

新規作成または description を更新した skill は、可能なら `skill-trigger-regression <skill-name>` を続けて実行する。`FAIL` があれば final へ進む前に description、`使う場面`、`対象外`、`関連 skill` を最小修正する。`WARN` が残る場合は最終報告に残存リスクとして書く。

## 更新フロー

既存 skill を更新する場合:

1. wrapper と reference を読む。
2. description だけで直る問題か、本体 workflow の問題かを分ける。
3. 発火しすぎる場合は description の scope と non-trigger を狭める。
4. 発火しない場合は key trigger words を description 先頭に移す。
5. 長すぎる場合は body から reference / scripts に逃がす。
6. 変更後に発火テスト例を更新する。

## 関連 skill

- `prompt-engineering`: description、命令文、発火条件を設計するとき。
- `empirical-prompt-tuning`: 作成した skill を独立評価で改善するとき。
- `skill-trigger-regression`: 新規作成または更新した skill の発火漏れ・過剰発火・競合を検査するとき。
- `audit-codex-config` / `audit-claude-config`: 既存設定や肥大化した skill を整理するとき。
- `discover-skills`: セッション履歴から新規 skill 候補を発見するとき。
