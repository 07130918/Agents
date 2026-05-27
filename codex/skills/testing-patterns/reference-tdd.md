# TDD リファレンス

`testing-patterns/SKILL.md` の TDD 節からリンクされる詳細リファレンス。Planning フェーズ・Tracer Bullet 手順・Deep Module 設計・Interface 設計・モック原則・Refactor 候補をまとめる。

参考: Matt Pocock "tdd" skill, John Ousterhout "A Philosophy of Software Design", Michael Feathers "Working Effectively with Legacy Code".

---

## 哲学

**核心原則**: テストは public interface を経由して**挙動 (behavior)** を検証する。実装詳細は検証しない。実装は丸ごと変わってもテストは変わらないのが理想。

**良いテスト** は integration スタイル — 実コードパスを public API 経由で動かす。「ユーザがカートでチェックアウトできる」のような能力 (capability) を記述する仕様書のように読める。リファクタで生き残る。

**悪いテスト** は実装に結合する。内部コラボレータをモックし、private メソッドをテストし、外部手段 (DB を直接 SELECT 等) で検証する。**警告サイン**: 挙動が変わっていないリファクタで落ちるなら、それは実装をテストしていた。内部関数のリネームでテストが落ちるなら、それは実装テスト。

---

## Workflow

### 1. Planning

コードベース探索時は、プロジェクトのドメイン用語集 (`CONTEXT.md`) を使ってテスト名と interface vocabulary をプロジェクトの言葉に合わせる。該当領域の ADR は尊重する。

実装前のチェックリスト:

- [ ] どの interface が変わるかをユーザと合意する
- [ ] どの挙動をテストするかをユーザと合意する (優先順位)
- [ ] **Deep module** (小さい interface + 多くの implementation) の機会を見つける
- [ ] **テスト容易性のための interface 設計**
- [ ] テストすべき挙動 (実装手順ではない) をリストアップ
- [ ] 計画にユーザの承認を得る

ユーザに問う: 「public interface はどう見えるべきか? どの挙動が最重要か?」

**全部はテストできない**。どの挙動が最重要かをユーザと正確に合意する。クリティカルパスと複雑なロジックに労力を集中させる。すべてのエッジケースを網羅しようとしない。

### 2. Tracer Bullet

システムについて 1 つのことを確認する 1 つのテストを書く:

```
RED:   1 つ目の挙動のテストを書く → 失敗
GREEN: 通すための最小コードを書く → 成功
```

これが tracer bullet — パスがエンドツーエンドで動くことを証明する。

### 3. Incremental Loop

残りの各挙動について:

```
RED:   次のテスト → 失敗
GREEN: 通す最小コード → 成功
```

ルール:

- 1 度に 1 テスト
- 現テストを通す最小コードのみ
- 将来のテストを先取りしない
- テストは観察可能な挙動に集中

### 4. Refactor

全テストが通った後、リファクタ候補を探す:

- [ ] 重複を抽出 → 関数/クラスに
- [ ] **Shallow なモジュールを deepen** (複雑性を小さい interface の裏に隠す)
- [ ] SOLID 原則を自然な形で適用
- [ ] 新コードが既存コードについて何を明らかにしたかを考える
- [ ] 各リファクタステップ後にテストを走らせる

**RED 中はリファクタしない**。先に GREEN にする。

#### 探すべきリファクタ候補

- **重複** → 関数/クラスを抽出
- **長いメソッド** → private ヘルパに分解 (テストは public interface に残す)
- **Shallow なモジュール** → 結合または deepen
- **Feature envy** — データの持ち主の所にロジックを移動
- **Primitive obsession** — value object を導入
- **既存コード** が新コードによって問題と判明したら手を入れる

---

## Deep Modules

John Ousterhout "A Philosophy of Software Design" より:

**Deep module** = 小さい interface + 多くの implementation

```
┌─────────────────────┐
│   Small Interface   │  ← メソッド少、パラメータ単純
├─────────────────────┤
│                     │
│                     │
│  Deep Implementation│  ← 複雑なロジックを隠す
│                     │
│                     │
└─────────────────────┘
```

**Shallow module** = 大きい interface + 薄い implementation (避ける)

```
┌─────────────────────────────────┐
│       Large Interface           │  ← メソッド多、パラメータ複雑
├─────────────────────────────────┤
│  Thin Implementation            │  ← ただの pass-through
└─────────────────────────────────┘
```

interface 設計時に問う:

- メソッド数を減らせるか?
- パラメータを単純化できるか?
- もっと多くの複雑性を内側に隠せるか?

---

## Interface Design for Testability

良い interface は自然にテスト可能:

### 1. 依存を**受け取る**、**作らない**

```ts
// ✅ テスト可能
function processOrder(order, paymentGateway) {}

// ❌ テストしにくい
function processOrder(order) {
  const gateway = new StripeGateway()
}
```

### 2. **結果を返す**、**副作用を起こさない**

```ts
// ✅ テスト可能
function calculateDiscount(cart): Discount {}

// ❌ テストしにくい
function applyDiscount(cart): void {
  cart.total -= discount
}
```

### 3. **小さい surface area**

- メソッドが少ない = 必要なテストも少ない
- パラメータが少ない = テストセットアップが単純

---

## いつモックするか

**System boundary でのみ**モックする:

- 外部 API (payment、email 等)
- データベース (場合による — できればテスト DB)
- 時刻・乱数
- ファイルシステム (場合による)

モックしないもの:

- 自分のクラス・モジュール
- 内部コラボレータ
- 自分が制御するもの全て

### モック容易性のための設計

System boundary では、モックしやすい interface を設計する:

#### 1. Dependency Injection

外部依存を内部で生成せず、引数で受け取る:

```ts
// ✅ モックしやすい
function processPayment(order, paymentClient) {
  return paymentClient.charge(order.total)
}

// ❌ モックしにくい
function processPayment(order) {
  const client = new StripeClient(process.env.STRIPE_KEY)
  return client.charge(order.total)
}
```

#### 2. Generic fetcher より SDK スタイル

外部操作ごとに専用関数を作る。1 つの汎用関数 + 条件分岐より勝る:

```ts
// ✅ 各関数が独立にモック可能
const api = {
  getUser: (id) => fetch(`/users/${id}`),
  getOrders: (userId) => fetch(`/users/${userId}/orders`),
  createOrder: (data) => fetch('/orders', { method: 'POST', body: data }),
}

// ❌ モックの中で条件分岐が必要
const api = {
  fetch: (endpoint, options) => fetch(endpoint, options),
}
```

SDK スタイルの利点:

- 各モックは特定の形だけ返せばよい
- テストセットアップに条件分岐不要
- どのエンドポイントを叩いているか一目瞭然
- エンドポイント単位の型安全

---

## Per-cycle チェックリスト

```
[ ] テストが「挙動」を記述している (実装ではない)
[ ] テストが public interface のみを使っている
[ ] テストは内部リファクタで生き残る
[ ] コードはこのテストを通す最小限になっている
[ ] このテストに不要な投機的機能を追加していない
```

---

## アンチパターン: 水平スライス

**全テストをまず書く → 全実装をまとめて書く**は禁忌 (RED を「全テスト」、GREEN を「全コード」と扱うこと)。

これは crap test を生む:

- 大量に書かれたテストは**想像上**の挙動をテスト、**実際**の挙動ではない
- データ構造や関数シグネチャの**形**をテストする結果になり、ユーザに見える挙動を見ない
- テストが本物の変化に鈍感 — 挙動が壊れても通り、挙動が正常でも落ちる
- ヘッドライトより先に走る — 実装を理解する前にテスト構造を固める

**正しいやり方**: tracer bullet によるバーティカルスライス。1 テスト → 1 実装 → 繰り返し。各サイクルは前サイクルで学んだことに反応する。**今書いたばかりだから**、どの挙動が重要でどう検証するかが正確に分かる。

```
❌ 間違い (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

✅ 正しい (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```
