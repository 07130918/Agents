# discover-skills

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Skill ギャップ発見 & 追加実装

最近のセッションを分析し、不足している skills/agents を発見して実装する。既存ファイルの整理ではなく、**使用パターンからの新規スキル発掘** が目的。

---

## Phase 1: 現状棚卸し

既存スキル・エージェント・グローバル設定を読み込み、**何をトリガーに起動するか** を把握する。

- `Glob` で `~/.Codex/skills/*/SKILL.md` と `~/.Codex/agents/*.md` を列挙
- `Read` で `~/.Codex/AGENTS.md` を取得
- 各ファイルの frontmatter `description` を並列で `Read` し、カバー範囲を一覧化

`ls` / `cat` を Bash で叩かないこと (dedicated tool を優先)。

---

## Phase 2: セッション分析

### 対象ファイルの特定

mtime 絞り込みが必要なので Bash の `find` を使う (Glob は mtime フィルタ不可):

```bash
find ~/.Codex/projects/ -name "*.jsonl" -mtime -30 | sort | tail -20
find ~/.Codex/projects/ -name "*.plan"  -mtime -30 | sort | tail -30
```

### パターン抽出

内容走査は **Grep ツール** で実行する (`grep -r` は使わない)。以下はクエリ例。

**技術キーワードの頻度** - 全プロジェクト横断:

- `Grep(pattern: "Chakra|Next\\.js|Flask|FastAPI|Knex|MySQL|TypeScript|Supabase|Slack|Bitcoin|Figma|Asana", path: "~/.Codex/projects/", glob: "*.plan", output_mode: "count", head_limit: 30)`

**繰り返しのタスク種別** - 計画・修正・バグ・実装の頻出ワード:

- `Grep(pattern: "Chakra UI|マイグレーション|権限|RBAC|ダッシュボード|ログ|API|コードレビュー|PR作成|バグ|テスト", path: "~/.Codex/projects/", glob: "*.plan", output_mode: "count", head_limit: 20)`

**エラーパターン** - 直近2週間のセッションからサンプル:

1. Bash で対象 `.jsonl` を選定: `find ~/.Codex/projects/ -name "*.jsonl" -mtime -14 | sort | tail -5`
2. 各ファイルを `Grep(pattern: "エラー|Error|failed|Cannot|undefined", path: <file>, output_mode: "content", head_limit: 20)` で走査

キーワードは例示。ユーザーの実際の技術スタックに合わせて調整する。

---

## Phase 3: ギャップ分析

Phase 1 と Phase 2 の結果を比較して以下を評価する:

1. **頻出技術に対応するスキルが存在するか**
   - 月3件以上登場する技術・ワークフローでスキルが未作成のものを特定
2. **繰り返しのワークフローが自動化されているか**
   - 毎セッションで手動実行しているタスクを特定
3. **既存スキル・エージェントが最新の実態と乖離していないか**
   - 説明文のトリガー条件が実態と合っているか確認
4. **AGENTS.md や既存 skill の肥大・重複**
   - 一次的な違和感レベルで留め、詳細な監査・リファクタは `audit-codex-config` に委譲する (二重実装を避ける)

---

## Phase 4: 作成提案と承認待ち

### 必須ルール (例外なし)

- Phase 3 のギャップ分析が終わった時点では、まだ skill / agent を作成・更新しない
- 新規 skill / agent 作成、または既存 skill / agent 更新が必要だと判断したら、必ず先にユーザーへ提案する
- 提案後はユーザーの返答を待つ。明示承認がない限り、Phase 5 の実装へ進まない
- ユーザーが却下した候補は作成しない。保留理由として最終報告に残す
- ユーザーが一部だけ承認した場合は、承認された候補だけ実装する

提案には最低限これを含める:

1. 作成/更新候補の名前
2. 目的とトリガー条件
3. 既存 skill / agent では不足する理由
4. 作成/更新する予定ファイル
5. 作成しない場合のリスク、または既存 skill で代替する方針

提案例:

```markdown
以下の skill 作成を提案します。実装してよいか返答をください。

- `local-dev-ops`: ローカル開発環境の起動、停止、ポート確認、Docker Compose の運用手順。既存 skill は Cloud/GitHub/UI に寄っており、localhost 運用の反復手順が薄い。
  - 作成予定: `~/.agents/references/local-dev-ops.md`, `~/.agents/skills/local-dev-ops/SKILL.md`, `~/.claude/skills/local-dev-ops/SKILL.md`
```

---

## Phase 5: 実装

### 必須ルール (例外なし)

- ユーザー承認後、実装前に「**これから作成/更新するもの**: [リスト]」と必ず宣言する
- 既存ファイルは更新前に必ず Read で内容確認する
- AGENTS.md は200行以内に収める

### ファイル構造テンプレート

**新規スキル** `~/.Codex/skills/{name}/SKILL.md`:

```
---
name: {skill-name}
description: {いつ使うかの説明 - コンテキストトリガーを含める。例: "〇〇に関する実装や修正を行うときに参照する"}
---

# {スキル名}

## {セクション}
(内容)
```

**新規エージェント** `~/.Codex/agents/{name}.md`:

```
---
name: {name}
description: Use this agent when [トリガー条件]. Examples:\n\n<example>\nContext: [状況]\nuser: "[発言例]"\nassistant: "[応答例]"\n<commentary>[なぜこのエージェントを起動するか]</commentary>\n</example>
model: sonnet
color: {blue|green|red|yellow|purple}
---

(エージェントの指示...)
```

**スラッシュコマンドをスキルとして作成** (commands/ は廃止されスキルに統合):

```
---
name: {skill-name}
description: {コマンドの説明 - "`/{skill-name}` で呼び出される" を含めるとよい}
---

# {コマンド名}

(実行手順...)
```

---

## Phase 6: 実行後の確認

実装完了後に以下を報告する:

1. **作成/更新したファイルの一覧**
2. **保留とした項目** (ユーザーが却下した候補、工数が大きい・要調査など)
3. **次回分析の推奨タイミング** (目安: 1〜2ヶ月後、または新プロジェクト開始時)

## Claude Code 版

# Skill ギャップ発見 & 追加実装

最近のセッションを分析し、不足している skills/agents を発見して実装する。既存ファイルの整理ではなく、**使用パターンからの新規スキル発掘** が目的。

---

## Phase 1: 現状棚卸し

既存スキル・エージェント・グローバル設定を読み込み、**何をトリガーに起動するか** を把握する。

- `Glob` で `~/.claude/skills/*/SKILL.md` と `~/.claude/agents/*.md` を列挙
- `Read` で `~/.claude/CLAUDE.md` を取得
- 各ファイルの frontmatter `description` を並列で `Read` し、カバー範囲を一覧化

`ls` / `cat` を Bash で叩かないこと (dedicated tool を優先)。

---

## Phase 2: セッション分析

### 対象ファイルの特定

mtime 絞り込みが必要なので Bash の `find` を使う (Glob は mtime フィルタ不可):

```bash
find ~/.claude/projects/ -name "*.jsonl" -mtime -30 | sort | tail -20
find ~/.claude/projects/ -name "*.plan"  -mtime -30 | sort | tail -30
```

### パターン抽出

内容走査は **Grep ツール** で実行する (`grep -r` は使わない)。以下はクエリ例。

**技術キーワードの頻度** - 全プロジェクト横断:

- `Grep(pattern: "Chakra|Next\\.js|Flask|FastAPI|Knex|MySQL|TypeScript|Supabase|Slack|Bitcoin|Figma|Asana", path: "~/.claude/projects/", glob: "*.plan", output_mode: "count", head_limit: 30)`

**繰り返しのタスク種別** - 計画・修正・バグ・実装の頻出ワード:

- `Grep(pattern: "Chakra UI|マイグレーション|権限|RBAC|ダッシュボード|ログ|API|コードレビュー|PR作成|バグ|テスト", path: "~/.claude/projects/", glob: "*.plan", output_mode: "count", head_limit: 20)`

**エラーパターン** - 直近2週間のセッションからサンプル:

1. Bash で対象 `.jsonl` を選定: `find ~/.claude/projects/ -name "*.jsonl" -mtime -14 | sort | tail -5`
2. 各ファイルを `Grep(pattern: "エラー|Error|failed|Cannot|undefined", path: <file>, output_mode: "content", head_limit: 20)` で走査

キーワードは例示。ユーザーの実際の技術スタックに合わせて調整する。

---

## Phase 3: ギャップ分析

Phase 1 と Phase 2 の結果を比較して以下を評価する:

1. **頻出技術に対応するスキルが存在するか**
   - 月3件以上登場する技術・ワークフローでスキルが未作成のものを特定
2. **繰り返しのワークフローが自動化されているか**
   - 毎セッションで手動実行しているタスクを特定
3. **既存スキル・エージェントが最新の実態と乖離していないか**
   - 説明文のトリガー条件が実態と合っているか確認
4. **CLAUDE.md や既存 skill の肥大・重複**
   - 一次的な違和感レベルで留め、詳細な監査・リファクタは `audit-claude-config` に委譲する (二重実装を避ける)

---

## Phase 4: 作成提案と承認待ち

### 必須ルール (例外なし)

- Phase 3 のギャップ分析が終わった時点では、まだ skill / agent を作成・更新しない
- 新規 skill / agent 作成、または既存 skill / agent 更新が必要だと判断したら、必ず先にユーザーへ提案する
- 提案後はユーザーの返答を待つ。明示承認がない限り、Phase 5 の実装へ進まない
- ユーザーが却下した候補は作成しない。保留理由として最終報告に残す
- ユーザーが一部だけ承認した場合は、承認された候補だけ実装する

提案には最低限これを含める:

1. 作成/更新候補の名前
2. 目的とトリガー条件
3. 既存 skill / agent では不足する理由
4. 作成/更新する予定ファイル
5. 作成しない場合のリスク、または既存 skill で代替する方針

提案例:

```markdown
以下の skill 作成を提案します。実装してよいか返答をください。

- `local-dev-ops`: ローカル開発環境の起動、停止、ポート確認、Docker Compose の運用手順。既存 skill は Cloud/GitHub/UI に寄っており、localhost 運用の反復手順が薄い。
  - 作成予定: `~/.agents/references/local-dev-ops.md`, `~/.agents/skills/local-dev-ops/SKILL.md`, `~/.claude/skills/local-dev-ops/SKILL.md`
```

---

## Phase 5: 実装

### 必須ルール (例外なし)

- ユーザー承認後、実装前に「**これから作成/更新するもの**: [リスト]」と必ず宣言する
- 既存ファイルは更新前に必ず Read で内容確認する
- CLAUDE.md は200行以内に収める

### ファイル構造テンプレート

**新規スキル** `~/.claude/skills/{name}/SKILL.md`:

```
---
name: {skill-name}
description: {いつ使うかの説明 - コンテキストトリガーを含める。例: "〇〇に関する実装や修正を行うときに参照する"}
---

# {スキル名}

## {セクション}
(内容)
```

**新規エージェント** `~/.claude/agents/{name}.md`:

```
---
name: {name}
description: Use this agent when [トリガー条件]. Examples:\n\n<example>\nContext: [状況]\nuser: "[発言例]"\nassistant: "[応答例]"\n<commentary>[なぜこのエージェントを起動するか]</commentary>\n</example>
model: sonnet
color: {blue|green|red|yellow|purple}
---

(エージェントの指示...)
```

**スラッシュコマンドをスキルとして作成** (commands/ は廃止されスキルに統合):

```
---
name: {skill-name}
description: {コマンドの説明 - "`/{skill-name}` で呼び出される" を含めるとよい}
---

# {コマンド名}

(実行手順...)
```

---

## Phase 6: 実行後の確認

実装完了後に以下を報告する:

1. **作成/更新したファイルの一覧**
2. **保留とした項目** (ユーザーが却下した候補、工数が大きい・要調査など)
3. **次回分析の推奨タイミング** (目安: 1〜2ヶ月後、または新プロジェクト開始時)
