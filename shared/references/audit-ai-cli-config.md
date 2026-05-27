# audit-ai-cli-config

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Codex 設定ファイル監査 & リファクタ

Codex 公式ベストプラクティスに沿って、対象プロジェクトの Codex 設定MDファイルを監査・リファクタする。冗長性・重複・陳腐化・構造バグを検出し、公式準拠の形に書き換える。大きな変更は必ず事前確認する。`ultrathink` で深く分析してください。

## 対象の決定

### 引数 `$ARGUMENTS` の解釈

| パターン | 動作 |
|---------|------|
| 引数なし | `$PWD` の `./AGENTS.md`, `./.agents/skills/`, `./.codex/` 配下すべてを対象 |
| 既存ディレクトリパス | そのディレクトリ配下を同様にスキャン |
| `AGENTS.md` / `SKILL.md` / `*.toml` / `*.md` 具体ファイル | そのファイルのみ最適化 |
| `.agents/skills/<name>/SKILL.md` | その skill のみ |
| `.codex/agents/<name>.toml` | その subagent のみ |
| `.codex/commands/<name>.md` | その command を skill に変換 + 最適化 |

### 自動検出 (ディレクトリ対象時)

Glob で以下を一括列挙:

```
{target}/AGENTS.md
{target}/.agents/skills/*/SKILL.md
{target}/.codex/agents/*.toml
{target}/.codex/commands/*.md      ← 存在すれば skills 化候補
```

`find` や `ls` は使わず `Glob` ツールを使う(公式推奨)。

## 公式ベストプラクティス

迷ったら以下を WebFetch で再確認する:

- https://developers.openai.com/codex
- https://developers.openai.com/codex/guides/agents-md
- https://developers.openai.com/codex/learn/best-practices
- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/subagents

### AGENTS.md ルール

| チェック | 公式ルール |
|---------|-----------|
| 行数 | **<200行** — 超えると Codex が半分無視する |
| 構造 | markdown 見出し + 箇条書きで scan 可能に |
| 具体性 | 検証可能な指示 (「`make ci` を実行」◎ / 「ちゃんとテスト」✗) |
| 矛盾排除 | 他 AGENTS.md / `.codex/rules/` と矛盾しない |
| 強調マーカー | `IMPORTANT:` / `YOU MUST:` / `⚠️` を重要ルールに使用可 |
| @imports | 起動時ロード。大きな docs は link で十分 |

**✅ 含めるべき**:
- Codex が推測できない bash/make コマンド
- 非標準の規約 (例: `test` ではなく `it` を使うプロジェクト固有ルール)
- プロジェクト固有のアーキテクチャ決定
- 環境の癖・gotcha (例: 環境変数を複数箇所で更新)

**❌ 除外すべき**:
- コードから推測可能な内容
- 標準言語規約 (Codex が既に知っている)
- 詳細 API docs (→ リンク化)
- 頻繁に変わる情報
- 長い説明文・チュートリアル
- file-by-file description
- 自明な実践論 (「clean code を書く」)

**黄金のテスト**: *"Would removing this cause Codex to make mistakes?"* → No なら削除

### Skills (SKILL.md) ルール

| チェック | 公式ルール |
|---------|-----------|
| 行数 | **<500行** 推奨。超えたら supporting files に分割 |
| 配置 | `.agents/skills/<name>/SKILL.md` (ディレクトリ必須) |
| `name` | ≤64字、lowercase/numbers/hyphens のみ |
| `description` | 推奨。1,536字で切り詰められる→ トリガーキーワードを front-load |
| progressive disclosure | 詳細参照は `reference.md` 等の supporting file に分離 |
| `disable-model-invocation: true` | 副作用あるワークフロー (commit/deploy/PR作成/リソース変更) で必須 |
| `allowed-tools` | 必要最小限のツールを明示 (例: `Bash(git *) Bash(gh *)`) |
| `argument-hint` | `$ARGUMENTS` を使う場合に autocomplete ヒント |
| 重複排除 | 他 skill との重複は「参照」化 (例: `uka-route-frontend skill 参照`) |
| ultrathink | 深い推論が必要な skill は本文に `ultrathink` を含める |

### Subagents (.codex/agents/*.toml) ルール

| チェック | 公式ルール |
|---------|-----------|
| TOML | `name` / `description` / `model` / optional `tools` |
| 装飾文言削除 | 「最強」「🚀」「🔄 継続的改善」のような自己紹介を排除 |
| 使用例の集約 | `<example>` は frontmatter `description` 内で完結、body で重複しない |
| skill との重複削除 | 既存 skill の内容は参照で済ませる |
| 出力フォーマット | 冗長なテンプレートは簡潔に |
| 陳腐化データ | 日付入りテーブル (`2026-02-25 調査時点`) は削除 or 可変化 |

### Commands (.codex/commands/*.md) ルール

公式: *"Custom commands have been merged into skills."*

- 新規作成は **skills を推奨**
- 既存 commands は動作するが、以下の理由で skills に変換推奨:
  - `disable-model-invocation` / `allowed-tools` / `argument-hint` が使える
  - supporting files を持てる
  - live change detection が効く
- skill と command が同名なら skill が優先

**変換手順**:
1. `mkdir -p .agents/skills/<name>`
2. `Write .agents/skills/<name>/SKILL.md` (frontmatter 追加)
3. `rm .codex/commands/<name>.md` (ユーザー確認後)

### 公式 Anti-patterns (明示されているもの)

検出したら優先的に修正:

| Anti-pattern | 検出条件 | 対処 |
|-------------|---------|------|
| The over-specified AGENTS.md | AGENTS.md > 200 行 | prune |
| Duplicate rules | AGENTS.md と skill で同ルール重複 | どちらか一方に集約 |
| Decorative content | 「最強」「🚀」等の装飾、自己紹介セクション | 削除 |
| Stale data | 日付入りテーブル、ハードコード値 | 可変化 or 削除 |
| Dead commands | 実行されない bash コード全文 (commands では Codex が読み上げるだけ) | 削除し手順のみ残す |
| Number bugs | 箇条書きの番号重複 (「8.」が2回) | 修正 |
| Missing frontmatter | skill に `name`/`description` が欠落 | 追加 |

## 実行フロー

### Step 1: 対象を特定

`$ARGUMENTS` を解釈し、Read/Glob で対象ファイルリストを作成。次のケースを判定:

- 引数がファイルパス (`*.md`) で存在する → 単体ファイルモード
- 引数がディレクトリ → ディレクトリモード (全検出)
- 引数なし → `$PWD` ディレクトリモード

### Step 2: 並列読み込み + 計測

すべての対象ファイルを **並列で** Read し、併せて `Bash(wc -l)` で行数を計測。

### Step 3: 分析 (ultrathink)

各ファイルに対してチェックリストを適用し、以下を記録:

- 現在の行数 vs 推奨上限
- 検出された anti-pattern
- ファイル間の重複 (skill と skill、AGENTS.md と skill)
- 構造バグ (番号重複、欠落 frontmatter)
- 陳腐化したコンテンツ

公式 doc と矛盾しそうな判断に迷ったら WebFetch で確認する。

### Step 4: 最適化プラン提示 (ユーザー確認)

**以下を含めて提示**:

1. ファイル別の Before → After 行数目標
2. 削除 / 短縮 / 再構成する内容とその根拠
3. 参照化する内容 (`@docs/...` や他 skill へ)
4. commands → skills 変換の有無
5. 削除する文章の要旨

**削減率が大きい場合 (>50%) は明示的に合意を取る**。また、プロジェクト固有の非自明ルール (絶対 import、環境変数の更新箇所など) が失われないことを確認させる。

### Step 5: 実行

Edit/Write で並列編集。

**commands → skills 変換**の場合:

```
1. mkdir -p .agents/skills/<name>
2. Write .agents/skills/<name>/SKILL.md
   - frontmatter に name, description を必須
   - 副作用あれば disable-model-invocation: true
   - 必要な allowed-tools を設定
   - $ARGUMENTS 使用なら argument-hint
3. rm .codex/commands/<name>.md (ユーザー最終確認)
4. commands/ が空になったら rmdir
```

### Step 6: 検証 & レポート

```markdown
## 最適化結果

| ファイル | Before | After | 削減率 | 主な変更 |
|---------|--------|-------|--------|---------|
| AGENTS.md | 300 | 95 | -68% | docs 目次削除 + Import 例圧縮 |
| ... | ... | ... | ... | ... |

## 公式準拠チェック
- ✅ AGENTS.md 200行未満
- ✅ Skills 500行未満、progressive disclosure 適用
- ✅ Subagent 使用例は frontmatter に集約
- ✅ commands → skills 移行完了
- ✅ 番号バグ修正

## 残存する改善余地
- (あれば列挙)

Sources:
- [Codex docs](https://developers.openai.com/codex)
- [AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Best Practices](https://developers.openai.com/codex/learn/best-practices)
- [Skills](https://developers.openai.com/codex/skills)
- [Subagents](https://developers.openai.com/codex/subagents)
```

## 重要原則

1. **破壊的でない**: プロジェクト固有の非自明ルール (絶対 import / 環境変数の複数箇所更新 / 非標準テスト規約など) は絶対に失わない。迷ったら残す
2. **事前計画**: 削減率が大きい変更・ファイル削除はユーザー確認を取る
3. **公式準拠**: 判断に迷ったら公式 docs を WebFetch で再確認 (上記4つのURL)
4. **根拠ベース**: 「長いから削る」ではなく「他 skill と重複なので参照化」のように **公式ルール/重複** を根拠に示す
5. **一括プロジェクト vs 単体ファイル**: 引数の種類で必ずモードを分岐させる
6. **memory/auto memory は対象外**: `~/.codex/memories/` の auto memory ファイルは Codex が自己管理するため触らない

## 使用例

```
# 現在のディレクトリ全体
/audit-codex-config

# 別プロジェクトまるごと
/audit-codex-config ~/projects/my-app

# プロジェクトルート AGENTS.md のみ
/audit-codex-config AGENTS.md

# 特定の skill だけ
/audit-codex-config .agents/skills/my-skill/SKILL.md

# 特定の subagent だけ
/audit-codex-config .codex/agents/reviewer.toml

# command を skill に変換
/audit-codex-config .codex/commands/deploy.md
```

## 関連リソース

- [Codex docs](https://developers.openai.com/codex) — Codex 公式ドキュメントの入口
- [Best Practices for Codex](https://developers.openai.com/codex/learn/best-practices) — prompting、validation、MCP、skills、automation
- [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) — AGENTS.md の探索順序、`~/.codex`、設定例
- [Agent Skills](https://developers.openai.com/codex/skills) — SKILL.md 構造、progressive disclosure、`.agents/skills`
- [Subagents](https://developers.openai.com/codex/subagents) — subagent 設計、`.codex/agents/*.toml`

## Claude Code 版

# Claude 設定ファイル監査 & リファクタ

Claude Code 公式ベストプラクティスに沿って、対象プロジェクトの Claude 設定MDファイルを監査・リファクタする。冗長性・重複・陳腐化・構造バグを検出し、公式準拠の形に書き換える。大きな変更は必ず事前確認する。`ultrathink` で深く分析してください。

## 対象の決定

### 引数 `$ARGUMENTS` の解釈

| パターン | 動作 |
|---------|------|
| 引数なし | `$PWD` の `./CLAUDE.md`, `./.claude/` 配下すべてを対象 |
| 既存ディレクトリパス | そのディレクトリ配下を同様にスキャン |
| `CLAUDE.md` / `*.md` 具体ファイル | そのファイルのみ最適化 |
| `.claude/skills/<name>/SKILL.md` | その skill のみ |
| `.claude/agents/<name>.md` | その subagent のみ |
| `.claude/commands/<name>.md` | その command を skill に変換 + 最適化 |

### 自動検出 (ディレクトリ対象時)

Glob で以下を一括列挙:

```
{target}/CLAUDE.md
{target}/.claude/CLAUDE.md
{target}/.claude/skills/*/SKILL.md
{target}/.claude/agents/*.md
{target}/.claude/commands/*.md      ← 存在すれば skills 化候補
```

`find` や `ls` は使わず `Glob` ツールを使う(公式推奨)。

## 公式ベストプラクティス

迷ったら以下を WebFetch で再確認する:

- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/best-practices
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/sub-agents

### CLAUDE.md ルール

| チェック | 公式ルール |
|---------|-----------|
| 行数 | **<200行** — 超えると Claude が半分無視する |
| 構造 | markdown 見出し + 箇条書きで scan 可能に |
| 具体性 | 検証可能な指示 (「`make ci` を実行」◎ / 「ちゃんとテスト」✗) |
| 矛盾排除 | 他 CLAUDE.md / `.claude/rules/` と矛盾しない |
| 強調マーカー | `IMPORTANT:` / `YOU MUST:` / `⚠️` を重要ルールに使用可 |
| @imports | 起動時ロード。大きな docs は link で十分 |

**✅ 含めるべき**:
- Claude が推測できない bash/make コマンド
- 非標準の規約 (例: `test` ではなく `it` を使うプロジェクト固有ルール)
- プロジェクト固有のアーキテクチャ決定
- 環境の癖・gotcha (例: 環境変数を複数箇所で更新)

**❌ 除外すべき**:
- コードから推測可能な内容
- 標準言語規約 (Claude が既に知っている)
- 詳細 API docs (→ リンク化)
- 頻繁に変わる情報
- 長い説明文・チュートリアル
- file-by-file description
- 自明な実践論 (「clean code を書く」)

**黄金のテスト**: *"Would removing this cause Claude to make mistakes?"* → No なら削除

### Skills (SKILL.md) ルール

| チェック | 公式ルール |
|---------|-----------|
| 行数 | **<500行** 推奨。超えたら supporting files に分割 |
| 配置 | `.claude/skills/<name>/SKILL.md` (ディレクトリ必須) |
| `name` | ≤64字、lowercase/numbers/hyphens のみ |
| `description` | 推奨。1,536字で切り詰められる→ トリガーキーワードを front-load |
| progressive disclosure | 詳細参照は `reference.md` 等の supporting file に分離 |
| `disable-model-invocation: true` | 副作用あるワークフロー (commit/deploy/PR作成/リソース変更) で必須 |
| `allowed-tools` | 必要最小限のツールを明示 (例: `Bash(git *) Bash(gh *)`) |
| `argument-hint` | `$ARGUMENTS` を使う場合に autocomplete ヒント |
| 重複排除 | 他 skill との重複は「参照」化 (例: `uka-route-frontend skill 参照`) |
| ultrathink | 深い推論が必要な skill は本文に `ultrathink` を含める |

### Subagents (.claude/agents/*.md) ルール

| チェック | 公式ルール |
|---------|-----------|
| frontmatter | `name` / `description` / `model` / (optional) `tools` |
| 装飾文言削除 | 「最強」「🚀」「🔄 継続的改善」のような自己紹介を排除 |
| 使用例の集約 | `<example>` は frontmatter `description` 内で完結、body で重複しない |
| skill との重複削除 | 既存 skill の内容は参照で済ませる |
| 出力フォーマット | 冗長なテンプレートは簡潔に |
| 陳腐化データ | 日付入りテーブル (`2026-02-25 調査時点`) は削除 or 可変化 |

### Commands (.claude/commands/*.md) ルール

公式: *"Custom commands have been merged into skills."*

- 新規作成は **skills を推奨**
- 既存 commands は動作するが、以下の理由で skills に変換推奨:
  - `disable-model-invocation` / `allowed-tools` / `argument-hint` が使える
  - supporting files を持てる
  - live change detection が効く
- skill と command が同名なら skill が優先

**変換手順**:
1. `mkdir .claude/skills/<name>`
2. `Write .claude/skills/<name>/SKILL.md` (frontmatter 追加)
3. `rm .claude/commands/<name>.md` (ユーザー確認後)

### 公式 Anti-patterns (明示されているもの)

検出したら優先的に修正:

| Anti-pattern | 検出条件 | 対処 |
|-------------|---------|------|
| The over-specified CLAUDE.md | CLAUDE.md > 200 行 | prune |
| Duplicate rules | CLAUDE.md と skill で同ルール重複 | どちらか一方に集約 |
| Decorative content | 「最強」「🚀」等の装飾、自己紹介セクション | 削除 |
| Stale data | 日付入りテーブル、ハードコード値 | 可変化 or 削除 |
| Dead commands | 実行されない bash コード全文 (commands では Claude が読み上げるだけ) | 削除し手順のみ残す |
| Number bugs | 箇条書きの番号重複 (「8.」が2回) | 修正 |
| Missing frontmatter | skill に `name`/`description` が欠落 | 追加 |

## 実行フロー

### Step 1: 対象を特定

`$ARGUMENTS` を解釈し、Read/Glob で対象ファイルリストを作成。次のケースを判定:

- 引数がファイルパス (`*.md`) で存在する → 単体ファイルモード
- 引数がディレクトリ → ディレクトリモード (全検出)
- 引数なし → `$PWD` ディレクトリモード

### Step 2: 並列読み込み + 計測

すべての対象ファイルを **並列で** Read し、併せて `Bash(wc -l)` で行数を計測。

### Step 3: 分析 (ultrathink)

各ファイルに対してチェックリストを適用し、以下を記録:

- 現在の行数 vs 推奨上限
- 検出された anti-pattern
- ファイル間の重複 (skill と skill、CLAUDE.md と skill)
- 構造バグ (番号重複、欠落 frontmatter)
- 陳腐化したコンテンツ

公式 doc と矛盾しそうな判断に迷ったら WebFetch で確認する。

### Step 4: 最適化プラン提示 (ユーザー確認)

**以下を含めて提示**:

1. ファイル別の Before → After 行数目標
2. 削除 / 短縮 / 再構成する内容とその根拠
3. 参照化する内容 (`@docs/...` や他 skill へ)
4. commands → skills 変換の有無
5. 削除する文章の要旨

**削減率が大きい場合 (>50%) は明示的に合意を取る**。また、プロジェクト固有の非自明ルール (絶対 import、環境変数の更新箇所など) が失われないことを確認させる。

### Step 5: 実行

Edit/Write で並列編集。

**commands → skills 変換**の場合:

```
1. mkdir -p .claude/skills/<name>
2. Write .claude/skills/<name>/SKILL.md
   - frontmatter に name, description を必須
   - 副作用あれば disable-model-invocation: true
   - 必要な allowed-tools を設定
   - $ARGUMENTS 使用なら argument-hint
3. rm .claude/commands/<name>.md (ユーザー最終確認)
4. commands/ が空になったら rmdir
```

### Step 6: 検証 & レポート

```markdown
## 最適化結果

| ファイル | Before | After | 削減率 | 主な変更 |
|---------|--------|-------|--------|---------|
| CLAUDE.md | 300 | 95 | -68% | docs 目次削除 + Import 例圧縮 |
| ... | ... | ... | ... | ... |

## 公式準拠チェック
- ✅ CLAUDE.md 200行未満
- ✅ Skills 500行未満、progressive disclosure 適用
- ✅ Subagent 使用例は frontmatter に集約
- ✅ commands → skills 移行完了
- ✅ 番号バグ修正

## 残存する改善余地
- (あれば列挙)

Sources:
- [Best Practices](https://code.claude.com/docs/en/best-practices)
- [Memory (CLAUDE.md)](https://code.claude.com/docs/en/memory)
- [Skills](https://code.claude.com/docs/en/skills)
- [Sub-agents](https://code.claude.com/docs/en/sub-agents)
```

## 重要原則

1. **破壊的でない**: プロジェクト固有の非自明ルール (絶対 import / 環境変数の複数箇所更新 / 非標準テスト規約など) は絶対に失わない。迷ったら残す
2. **事前計画**: 削減率が大きい変更・ファイル削除はユーザー確認を取る
3. **公式準拠**: 判断に迷ったら公式 docs を WebFetch で再確認 (上記4つのURL)
4. **根拠ベース**: 「長いから削る」ではなく「他 skill と重複なので参照化」のように **公式ルール/重複** を根拠に示す
5. **一括プロジェクト vs 単体ファイル**: 引数の種類で必ずモードを分岐させる
6. **memory/auto memory は対象外**: `~/.claude/projects/*/memory/` の auto memory ファイルは Claude が自己管理するため触らない

## 使用例

```
# 現在のディレクトリ全体
/audit-claude-config

# 別プロジェクトまるごと
/audit-claude-config ~/projects/my-app

# プロジェクトルート CLAUDE.md のみ
/audit-claude-config CLAUDE.md

# 特定の skill だけ
/audit-claude-config .claude/skills/my-skill/SKILL.md

# 特定の subagent だけ
/audit-claude-config .claude/agents/reviewer.md

# command を skill に変換
/audit-claude-config .claude/commands/deploy.md
```

## 関連リソース

- [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices) — anti-patterns、CLAUDE.md の ✅/❌ 一覧
- [How Claude remembers your project](https://code.claude.com/docs/en/memory) — CLAUDE.md 200行ルール / @imports / .claude/rules
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — SKILL.md frontmatter 全仕様 / commands→skills 統合
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — subagent 設計
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) — context window / progressive disclosure
