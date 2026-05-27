# Software Architecture Development Skill

This skill provides guidance for quality focused software development and architecture. It is based on Clean Architecture and Domain Driven Design principles, augmented with the deep-module discipline from John Ousterhout's "A Philosophy of Software Design" and Michael Feathers' "seam" terminology.

## 詳細リファレンス

| ファイル | 内容 | 読むタイミング |
|---|---|---|
| `reference-language.md` | アーキテクチャ語彙 (Module / Interface / Seam / Adapter / Depth / Leverage / Locality) の正確な定義と関係性 | 語彙のドリフトを防ぎたい時、議論の前に揃える時 |
| `reference-deepening.md` | Shallow なモジュール群を deepen する手順。依存カテゴリ別 (in-process / local-substitutable / remote-but-owned / true external) のテスト戦略 | リファクタ候補を選んだ後、具体に落とす時 |
| `reference-interface-design.md` | "Design It Twice" — 並列サブエージェントで radically 異なる interface を 3+ 案出す手法 | 深いモジュールの interface を選ぶ時、最初の案に固執しないため |

## Code Style Rules

### General Principles

- **Early return pattern**: Always use early returns when possible, over nested conditions for better readability
- Avoid code duplication through creation of reusable functions and modules
- Decompose long (more than 80 lines of code) components and functions into multiple smaller components and functions. If they cannot be used anywhere else, keep it in the same file. But if file longer than 200 lines of code, it should be split into multiple files.
- Use arrow functions instead of function declarations when possible

### Best Practices

#### Library-First Approach

- **ALWAYS search for existing solutions before writing custom code**
  - Check npm for existing libraries that solve the problem
  - Evaluate existing services/SaaS solutions
  - Consider third-party APIs for common functionality
- Use libraries instead of writing your own utils or helpers. For example, use `cockatiel` instead of writing your own retry logic.
- **When custom code IS justified:**
  - Specific business logic unique to the domain
  - Performance-critical paths with special requirements
  - When external dependencies would be overkill
  - Security-sensitive code requiring full control
  - When existing solutions don't meet requirements after thorough evaluation

#### Architecture and Design

- **Clean Architecture & DDD Principles:**
  - Follow domain-driven design and ubiquitous language
  - Separate domain entities from infrastructure concerns
  - Keep business logic independent of frameworks
  - Define use cases clearly and keep them isolated
- **Naming Conventions:**
  - **AVOID** generic names: `utils`, `helpers`, `common`, `shared`
  - **USE** domain-specific names: `OrderCalculator`, `UserAuthenticator`, `InvoiceGenerator`
  - Follow bounded context naming patterns
  - Each module should have a single, clear purpose
- **Separation of Concerns:**
  - Do NOT mix business logic with UI components
  - Keep database queries out of controllers
  - Maintain clear boundaries between contexts
  - Ensure proper separation of responsibilities

#### Anti-Patterns to Avoid

- **NIH (Not Invented Here) Syndrome:**
  - Don't build custom auth when Auth0/Supabase exists
  - Don't write custom state management instead of using Redux/Zustand
  - Don't create custom form validation instead of using established libraries
- **Poor Architectural Choices:**
  - Mixing business logic with UI components
  - Database queries directly in controllers
  - Lack of clear separation of concerns
- **Generic Naming Anti-Patterns:**
  - `utils.js` with 50 unrelated functions
  - `helpers/misc.js` as a dumping ground
  - `common/shared.js` with unclear purpose
- Remember: Every line of custom code is a liability that needs maintenance, testing, and documentation

#### Code Quality

- Proper error handling with typed catch blocks
- Break down complex logic into smaller, reusable functions
- Avoid deep nesting (max 3 levels)
- Keep functions focused and under 50 lines when possible
- Keep files focused and under 200 lines of code when possible

---

## アーキテクチャ語彙

このスキルが提案する全ての文に共通する語彙。**正確に**この語を使う。`component` / `service` / `API` / `boundary` 等への揺れを避ける。一貫した言葉が要点。完全な定義は `reference-language.md` を参照。

| 用語 | 定義 (短縮) | 避ける言い換え |
|---|---|---|
| **Module** | interface と implementation を持つもの (関数 / クラス / パッケージ / 層をまたぐスライス。粒度に依存しない) | unit, component, service |
| **Interface** | 呼び出し元が正しく使うために知らねばならない全て (型シグネチャ + 不変条件 + エラーモード + 順序制約 + 必要設定 + 性能特性) | API, signature (型表面しか指さない) |
| **Implementation** | モジュールの中身 (コード本体) | — |
| **Depth** | interface での leverage。**Deep** = 小さい interface の裏に多くの挙動。**Shallow** = interface が implementation とほぼ同じ複雑さ | (depth-as-line-ratio は誤り) |
| **Seam** | interface が存在する場所。そこで挙動を変えられる場所 (Michael Feathers) | boundary (DDD bounded context と被る) |
| **Adapter** | seam で interface を満たす具体物。役割 (どのスロットを埋めるか) を表す | implementation |
| **Leverage** | depth から呼び出し元が得るもの。学ぶ interface 量に対する挙動の量 | — |
| **Locality** | depth から保守者が得るもの。変更・バグ・知識・検証が 1 箇所に集中する性質 | — |

### 中核原則

- **Depth は interface の性質、implementation の性質ではない**。深いモジュールの内部は小さくモック可能・差し替え可能なパーツで構成されていて良い (それらが interface に出ていなければ良い)
- **Deletion test**: モジュールを削除すると想像する。複雑性が消える → pass-through だった (shallow)。複雑性が N 個の caller に出現する → 機能していた (deep)
- **Interface = test surface**: 呼び出し元とテストは同じ seam を通る。interface の**先**をテストしたくなったら、モジュールの形が間違っている可能性が高い
- **1 adapter = 仮説的 seam、2 adapter で初めて real seam**: 何かが seam の両側で実際に変わらない限り port を導入しない。1 adapter の seam は単なる indirection

---

## Deep Module 設計

```
✅ Deep module (小さい interface + 多くの implementation)

  ┌─────────────────────┐
  │   Small Interface   │  ← メソッド少、パラメータ単純
  ├─────────────────────┤
  │                     │
  │  Deep Implementation│  ← 複雑さを内側に隠す
  │                     │
  └─────────────────────┘

❌ Shallow module (大きい interface + 薄い implementation)

  ┌─────────────────────────────────┐
  │       Large Interface           │  ← メソッド多、パラメータ複雑
  ├─────────────────────────────────┤
  │  Thin Implementation            │  ← ただの pass-through
  └─────────────────────────────────┘
```

interface 設計時の問い:

- メソッド数を減らせるか?
- パラメータを単純化できるか?
- もっと多くの複雑性を内側に隠せるか?

**注**: interface の小ささを「行数比」で測るのは誤り (implementation を膨らませると score が上がってしまう)。**Leverage** で測る。「呼び出し元が学ぶ単位 interface 量に対して、どれだけの挙動が手に入るか」。

### Deletion test の使い方

Shallow を疑うモジュールを見つけたら、頭の中で削除する。

- **複雑性が消える** → pass-through だった。インライン化または近接モジュールに統合
- **複雑性が N 個の caller に拡散する** → 機能していた。残す

### 内部 seam vs 外部 seam

Deep module は内部 seam (privately で自分のテストだけが使う) と外部 seam (interface) の両方を持って良い。**内部 seam を「テストが使うから」だけの理由で interface に晒さない**。

---

## アーキテクチャ改善ワークフロー

shallow なモジュール群に深さを持たせる機会を発見し、優先順位で提示する 3 ステップ。**テスト容易性と AI navigability** を狙う。

詳細手順は `reference-deepening.md` を参照。interface の代替案検討は `reference-interface-design.md` を参照。

### 1. Explore

ドメイン用語集 (`CONTEXT.md`) と該当領域の `docs/adr/` をまず読む。次に `Explore` サブエージェントでコードベースを歩き、以下の摩擦をメモする:

- 1 つの概念を理解するために多数の小モジュールを行き来する場所
- **Shallow** なモジュール (interface が implementation とほぼ同じ複雑さ)
- テスト容易性のためだけに抽出された pure 関数で、本物のバグは「どう呼ばれるか」に隠れている (locality を失った)
- 結合の強いモジュールが seam を漏らしている場所
- テストされていない、または現状の interface ではテストしにくい場所

疑った shallow モジュールに **deletion test** を当てる。「Yes 集中する」が欲しいシグナル。

### 2. Present candidates

番号付きリストで提示。各候補に:

- **Files** — どのファイル/モジュールが関与するか
- **Problem** — 現アーキテクチャがなぜ摩擦を生んでいるか
- **Solution** — 平易な日本語で何が変わるか
- **Benefits** — locality と leverage の観点、テストがどう改善するか

CONTEXT.md vocabulary をドメインに、`reference-language.md` vocabulary をアーキテクチャに使う。`CONTEXT.md` が「Order」と定義していたら「Order intake モジュール」と呼ぶ — 「FooBarHandler」でも「Order service」でもなく。

**ADR と矛盾する候補**: 既存 ADR と衝突する候補は、摩擦が「ADR を再考するに値するほど」大きい時のみ提示する。明示ラベルを付ける (例: 「ADR-0007 と矛盾するが、再考価値あり、理由は…」)。理論的に禁じられているだけの候補は出さない。

interface はまだ提案しない。ユーザに問う: 「どれを深掘りしたい?」

### 3. Grilling loop

ユーザが選んだ候補について、設計ツリーをユーザと一緒に walk する。制約・依存・深いモジュールの形・seam の裏に何が入るか・どのテストが生き残るかを洗う。

判断が結晶化したらインラインで副作用を起こす:

- **`CONTEXT.md` に無い概念で deepened module を命名しそう?** → `CONTEXT.md` をその場で更新 (`grill-with-docs/CONTEXT-FORMAT.md`)。ファイルが無ければ lazy に作る
- **対話の中で曖昧な語が研がれた?** → `CONTEXT.md` をその場で更新
- **ユーザが load-bearing な理由で候補を却下?** → ADR を提案する。「将来のレビューが同じ提案を再度しないよう ADR にしますか?」と framing する。ephemeral な理由 (今は時間が無いだけ) や自明な理由はスキップ
- **deepened module の interface を複数案検討したい?** → `reference-interface-design.md` の並列サブエージェント手法に進む

---

## RBAC / Multi-Tenancy Patterns

複数のSaaSプロジェクトで共通する、マルチテナント RBAC の設計原則。

### 二層テナントモデル (corporation / provider)

典型的な B2B SaaS では、テナント階層を 2 層で設計するケースが多い:

- **corporation (法人テナント)**: 契約単位、最上位スコープ
- **provider (事業者・拠点テナント)**: corporation 配下の実際の業務単位
- **user**: provider に所属し、role を持つ

```
corporation (A社)
  ├── provider (東京拠点)
  │     ├── user (admin)
  │     └── user (operator)
  └── provider (大阪拠点)
        └── user (viewer)
```

クエリ・権限チェック時は **corporation_id と provider_id の両方で境界を引く**:

```sql
SELECT * FROM orders
WHERE corporation_id = :current_corporation_id  -- 法人境界
  AND provider_id = :current_provider_id         -- 拠点境界
```

### ロールベース (RBAC) vs 属性ベース (ABAC)

| 観点 | RBAC | ABAC |
|------|------|------|
| 定義方法 | role → 権限セット | 属性 + ルール |
| 柔軟性 | 低 (事前定義) | 高 (動的評価) |
| 可読性 | 高 | 低 (ルール複雑化) |
| 実装コスト | 低 | 高 |
| 推奨ケース | 役割が明確に分かれる SaaS | 所有者・時刻・地域など多軸判定 |

**推奨**: まず RBAC で始め、複雑な条件 (「自分が作成したもの」「過去30日以内」など) が出てきたら RBAC + リソース所有者チェックのハイブリッドにする。ABAC 全面採用は最終手段。

### 権限チェックの責務分離

権限チェックは層ごとに役割を分ける:

- **Middleware / Guard**: 認証済みかどうか、基本ロールの確認 (例: admin 必須のエンドポイント)
- **Service / UseCase**: ビジネスルールとしての権限 (例: 「このユーザーはこのドキュメントを編集できるか」)
- **Repository**: tenant_id の強制 (例: 全クエリに `where tenant_id = :current` を付ける)

```
Request
  ↓
Middleware      ← 認証 + 基本ロール
  ↓
Controller
  ↓
Service         ← ビジネスルール権限 (resource ownership, role x operation)
  ↓
Repository      ← tenant_id 境界の強制
  ↓
DB
```

**重要**: Repository 層で tenant_id を強制することで、Service 層の実装ミスがあっても他テナントのデータが漏れない **Defense in Depth** が実現できる。

### 権限関数の命名

- `can{Action}{Resource}(user, resource)` 形式で統一: `canEditDocument`, `canDeleteOrder`
- 戻り値は `boolean` か `Result<void, ForbidError>` (詳細な理由が必要な場合)
- 権限ロジックは **AuthorizationService** など専用クラスに集約し、サービスごとにバラけさせない

### よくあるアンチパターン

- ❌ **権限チェックを UI だけで行う**: API 直叩きで突破される
- ❌ **role 文字列を直接比較**: `user.role === 'admin'` を各所に書くと変更コストが爆発。`can{Action}` 関数に集約する
- ❌ **tenant_id を URL クエリから信頼**: 必ず認証済みセッションから取得する
- ❌ **Repository で tenant_id を忘れる**: テナント漏洩の最頻出原因
- ❌ **「管理者は全テナントを見られる」実装を一般ユーザーと同じ経路に混ぜる**: 権限昇格のリスク。別経路・別 Repository にする
