# prompt-engineering

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Prompt Engineering for Agents

Codex の skill / slash command / subagent プロンプト / AGENTS.md セクション / コード生成プロンプトを書くときの指針。Anthropic 公式ベストプラクティスと N=28,000 の persuasion 研究に基づく。

汎用的なプロンプト技法 (Few-Shot / Chain-of-Thought / Template / RAG など Codex が既に熟知している内容) は本 skill では扱わない。**agent 向けに固有の判断基準** だけを集約する。

## Core: Context Window は public good

skill / プロンプト / コマンドは system prompt・会話履歴・他 skill とコンテキストを共有する。各情報が token コストを正当化するか毎回問う:

- "Codex really need this explanation?"
- "Can I assume Codex knows this?"
- "Does this paragraph justify its token cost?"

**Default**: Codex は既に賢い。新規情報のみ追加する。

### Concise vs Verbose の判断

良い例 (約 50 tokens):

````markdown
## Extract PDF text

Use pdfplumber:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
````

悪い例 (約 150 tokens): "PDF (Portable Document Format) は…まずインストールが必要で…" のように Codex が既知の前提を説明している。

### 削るべき内容

- Codex が既知の標準言語規約・library API 詳細
- 装飾的見出し ("最強の", "エリート")、自己紹介セクション
- 何回も読み上げるだけの dead bash (echo文の連発)
- 長いチュートリアル形式の文章

## Set appropriate degrees of freedom

タスクの脆さ・ばらつきに応じて指示の具体性を変える。**ロボットが歩く道幅** をイメージする。

### High freedom (テキスト指示)

複数アプローチが妥当 / 文脈で判断が変わる / ヒューリスティクスで進む場合:

```markdown
## Code review process
1. Analyze structure and organization
2. Check for bugs or edge cases
3. Suggest readability/maintainability improvements
4. Verify project conventions
```

### Medium freedom (擬似コード or パラメータ付きスクリプト)

優先パターンがある / バリエーションを許容 / 設定で挙動が変わる:

````markdown
## Generate report
Customize as needed:
```python
def generate_report(data, format="markdown", include_charts=True):
    ...
```
````

### Low freedom (具体的スクリプト、パラメータ少)

操作が壊れやすい / 一貫性が critical / 順序厳守:

````markdown
## Database migration
Run exactly:
```bash
python scripts/migrate.py --verify --backup
```
Do not modify the command or add flags.
````

**Analogy**: 崖の上の細い橋 = low freedom (具体ガード)。広い野原 = high freedom (方向だけ)。

## Persuasion Principles (N=28,000 研究)

LLM は人間と同じ persuasion principle に反応する。compliance rate が 33% → 72% (p<.001) に倍増する。**操作のためではなく** critical practice を確実に守らせるために使う。

### 主要 4 原則

| 原則 | 効くプロンプト | 用途 |
|---|---|---|
| **Authority** | `YOU MUST` / `Never` / `No exceptions` | discipline 系 (TDD、検証要件)、安全性 critical |
| **Commitment** | `Announce when using X` / `Choose A, B, or C` | skill 順守、accountability |
| **Scarcity** | `Before proceeding` / `IMMEDIATELY after X` | 即時検証、遅延防止 |
| **Social Proof** | `Every time` / `X without Y = failure` | 普遍的実践、共通失敗の警告 |

### 補助 (限定使用)

- **Unity** (`we're colleagues`): 協調ワークフロー、対称的タスクで有効。階層的 discipline には不向き
- **Reciprocity** / **Liking**: ほぼ使わない (sycophancy 助長、honest feedback と衝突)

### プロンプトタイプ別の組み合わせ

| プロンプト種別 | 使うべき | 避けるべき |
|---|---|---|
| Discipline 強制 | Authority + Commitment + Social Proof | Liking, Reciprocity |
| Guidance / 技法 | 控えめな Authority + Unity | 強い Authority |
| 協調 | Unity + Commitment | Authority, Liking |
| Reference | 明瞭性のみ | 全 persuasion |

### 例

```markdown
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.

✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.

✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.

✅ Checklists without TodoWrite tracking = steps get skipped. Every time.
❌ Some people find TodoWrite helpful for checklists.
```

## なぜ効くか

- **Bright-line rules reduce rationalization**: `YOU MUST` は decision fatigue を消し、「これは例外?」の自問を封じる
- **Implementation intentions**: `When X, do Y` は `generally do Y` より自動実行されやすい
- **LLMs are parahuman**: 訓練データ中で authority 言語の後に compliance、commitment 後に action が頻出するため

## 倫理基準

| 正当 | 不当 |
|---|---|
| critical practice を守らせる | 個人的利益のための操作 |
| 効果的なドキュメント | false urgency の演出 |
| 予測可能な失敗の予防 | 罪悪感ベースの compliance |

**The test**: ユーザーがこの技法を完全に理解していたら、それでも genuine interest に資するか?

## プロンプト設計のチェックリスト

新しい skill / agent / command を書くとき:

1. **どのタイプか**: discipline / guidance / reference / collaboration
2. **どの行動を変えたいか**: 単一の具体的行動を 1 つ
3. **freedom level は適切か**: 脆い操作なら low、自由度の高いタスクなら high
4. **どの principle を使うか**: 通常は authority + commitment 1〜2 個に絞る
5. **削れる部分は無いか**: Codex が既知の説明、dead bash、装飾を削る
6. **倫理テスト**: ユーザーの genuine interest に資するか

## Common pitfalls

- **Over-engineering**: 単純なプロンプトを試す前に複雑化する
- **Context overflow**: 例を過剰に入れて token 上限に当たる
- **Ambiguous instructions**: 複数解釈の余地を残す
- **Decorative content**: 「最強の」「エリート」など機能を持たない装飾

## 関連 skill

- 経験的にプロンプト品質を測る: `empirical-prompt-tuning`
- 既存設定の監査・整理: `audit-codex-config`
- 新規 skill 発掘: `discover-skills`

## Claude Code 版

# Prompt Engineering for Agents

Claude Code の skill / slash command / subagent プロンプト / CLAUDE.md セクション / コード生成プロンプトを書くときの指針。Anthropic 公式ベストプラクティスと N=28,000 の persuasion 研究に基づく。

汎用的なプロンプト技法 (Few-Shot / Chain-of-Thought / Template / RAG など Claude が既に熟知している内容) は本 skill では扱わない。**agent 向けに固有の判断基準** だけを集約する。

## Core: Context Window は public good

skill / プロンプト / コマンドは system prompt・会話履歴・他 skill とコンテキストを共有する。各情報が token コストを正当化するか毎回問う:

- "Claude really need this explanation?"
- "Can I assume Claude knows this?"
- "Does this paragraph justify its token cost?"

**Default**: Claude は既に賢い。新規情報のみ追加する。

### Concise vs Verbose の判断

良い例 (約 50 tokens):

````markdown
## Extract PDF text

Use pdfplumber:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
````

悪い例 (約 150 tokens): "PDF (Portable Document Format) は…まずインストールが必要で…" のように Claude が既知の前提を説明している。

### 削るべき内容

- Claude が既知の標準言語規約・library API 詳細
- 装飾的見出し ("最強の", "エリート")、自己紹介セクション
- 何回も読み上げるだけの dead bash (echo文の連発)
- 長いチュートリアル形式の文章

## Set appropriate degrees of freedom

タスクの脆さ・ばらつきに応じて指示の具体性を変える。**ロボットが歩く道幅** をイメージする。

### High freedom (テキスト指示)

複数アプローチが妥当 / 文脈で判断が変わる / ヒューリスティクスで進む場合:

```markdown
## Code review process
1. Analyze structure and organization
2. Check for bugs or edge cases
3. Suggest readability/maintainability improvements
4. Verify project conventions
```

### Medium freedom (擬似コード or パラメータ付きスクリプト)

優先パターンがある / バリエーションを許容 / 設定で挙動が変わる:

````markdown
## Generate report
Customize as needed:
```python
def generate_report(data, format="markdown", include_charts=True):
    ...
```
````

### Low freedom (具体的スクリプト、パラメータ少)

操作が壊れやすい / 一貫性が critical / 順序厳守:

````markdown
## Database migration
Run exactly:
```bash
python scripts/migrate.py --verify --backup
```
Do not modify the command or add flags.
````

**Analogy**: 崖の上の細い橋 = low freedom (具体ガード)。広い野原 = high freedom (方向だけ)。

## Persuasion Principles (N=28,000 研究)

LLM は人間と同じ persuasion principle に反応する。compliance rate が 33% → 72% (p<.001) に倍増する。**操作のためではなく** critical practice を確実に守らせるために使う。

### 主要 4 原則

| 原則 | 効くプロンプト | 用途 |
|---|---|---|
| **Authority** | `YOU MUST` / `Never` / `No exceptions` | discipline 系 (TDD、検証要件)、安全性 critical |
| **Commitment** | `Announce when using X` / `Choose A, B, or C` | skill 順守、accountability |
| **Scarcity** | `Before proceeding` / `IMMEDIATELY after X` | 即時検証、遅延防止 |
| **Social Proof** | `Every time` / `X without Y = failure` | 普遍的実践、共通失敗の警告 |

### 補助 (限定使用)

- **Unity** (`we're colleagues`): 協調ワークフロー、対称的タスクで有効。階層的 discipline には不向き
- **Reciprocity** / **Liking**: ほぼ使わない (sycophancy 助長、honest feedback と衝突)

### プロンプトタイプ別の組み合わせ

| プロンプト種別 | 使うべき | 避けるべき |
|---|---|---|
| Discipline 強制 | Authority + Commitment + Social Proof | Liking, Reciprocity |
| Guidance / 技法 | 控えめな Authority + Unity | 強い Authority |
| 協調 | Unity + Commitment | Authority, Liking |
| Reference | 明瞭性のみ | 全 persuasion |

### 例

```markdown
✅ Write code before test? Delete it. Start over. No exceptions.
❌ Consider writing tests first when feasible.

✅ When you find a skill, you MUST announce: "I'm using [Skill Name]"
❌ Consider letting your partner know which skill you're using.

✅ After completing a task, IMMEDIATELY request code review before proceeding.
❌ You can review code when convenient.

✅ Checklists without TodoWrite tracking = steps get skipped. Every time.
❌ Some people find TodoWrite helpful for checklists.
```

## なぜ効くか

- **Bright-line rules reduce rationalization**: `YOU MUST` は decision fatigue を消し、「これは例外?」の自問を封じる
- **Implementation intentions**: `When X, do Y` は `generally do Y` より自動実行されやすい
- **LLMs are parahuman**: 訓練データ中で authority 言語の後に compliance、commitment 後に action が頻出するため

## 倫理基準

| 正当 | 不当 |
|---|---|
| critical practice を守らせる | 個人的利益のための操作 |
| 効果的なドキュメント | false urgency の演出 |
| 予測可能な失敗の予防 | 罪悪感ベースの compliance |

**The test**: ユーザーがこの技法を完全に理解していたら、それでも genuine interest に資するか?

## プロンプト設計のチェックリスト

新しい skill / agent / command を書くとき:

1. **どのタイプか**: discipline / guidance / reference / collaboration
2. **どの行動を変えたいか**: 単一の具体的行動を 1 つ
3. **freedom level は適切か**: 脆い操作なら low、自由度の高いタスクなら high
4. **どの principle を使うか**: 通常は authority + commitment 1〜2 個に絞る
5. **削れる部分は無いか**: Claude が既知の説明、dead bash、装飾を削る
6. **倫理テスト**: ユーザーの genuine interest に資するか

## Common pitfalls

- **Over-engineering**: 単純なプロンプトを試す前に複雑化する
- **Context overflow**: 例を過剰に入れて token 上限に当たる
- **Ambiguous instructions**: 複数解釈の余地を残す
- **Decorative content**: 「最強の」「エリート」など機能を持たない装飾

## 関連 skill

- 経験的にプロンプト品質を測る: `empirical-prompt-tuning`
- 既存設定の監査・整理: `audit-claude-config`
- 新規 skill 発掘: `discover-skills`
