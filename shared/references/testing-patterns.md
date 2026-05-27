# テストパターン実装ガイド

Vitest / Jest / pytest でのテスト実装、モックの落とし穴、カバレッジ向上、権限ロジックのテスト手法、バーティカルスライス TDD ワークフロー。

## 詳細リファレンス

| ファイル | 内容 | 読むタイミング |
|---|---|---|
| `reference-tdd.md` | TDD ワークフロー / 深いモジュール / インターフェース設計 / モック原則 / リファクタ候補 | TDD で進める時、既存コードを deep module 化したい時 |
| `reference-vitest-jest.md` | `vi.mock` 巻き上げ・`vi.hoisted`・`importOriginal`・spy リセット・非同期 await | TS / JS でモック実装時、`vi.mock` が効かない時 |
| `reference-pytest.md` | fixture スコープ、`monkeypatch` vs `mocker`、例外検証 | Python でテスト書く時、fixture 設計時 |

## 基本原則

### AAA パターン (Arrange-Act-Assert)

```ts
it('ユーザーがアーカイブされるとログインできない', async () => {
  // Arrange
  const user = await createUser({ archived: true })

  // Act
  const result = await login(user.email, 'password')

  // Assert
  expect(result.error).toBe('ACCOUNT_ARCHIVED')
})
```

- Arrange と Act の間に空行 (視認性)
- 1 テスト 1 アサーションが理想だが、関連状態の確認はまとめて OK
- テスト名は「〇〇すると△△になる」形式

### テストの独立性

- `beforeEach` / `afterEach` で状態リセット
- 実行順序に依存しない
- グローバル変数・モジュールキャッシュは `afterEach` でクリア

## TDD: バーティカルスライス・ワークフロー

**核心**: テストは public interface を経由して**挙動 (behavior)** を検証する。実装詳細を検証しない。実装は丸ごと変わってもテストは変わらないのが理想。

### Red-Green-Refactor を「垂直」で回す

```
✅ 正しい (vertical / tracer bullet):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...

❌ 間違い (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5
```

- 1 テスト書く → 通すために必要最小の実装 → 次のテスト
- 各サイクルは前サイクルで学んだことに反応する
- 「先に全テスト書く」と**想像上の挙動**をテストするだけになり、実装と乖離する

### アンチパターン: 水平スライス

「全テストをまず書く → 全実装をまとめて書く」が生む 4 つの害:

1. **想像上の挙動をテストする** — 実際の挙動でなく、こうあって欲しい挙動
2. **形のテストになる** — データ構造や関数シグネチャだけ assert し、ユーザに見える挙動を見ない
3. **本物の変化に鈍感になる** — 挙動が壊れても通り、挙動が正常でも落ちる
4. **ヘッドライトより先に走る** — 実装を理解する前にテスト構造を固めてしまう

### Per-cycle チェックリスト

```
[ ] テストが「挙動」を記述している (実装ではない)
[ ] テストが public interface のみを使っている
[ ] テストは内部リファクタで生き残る (内部関数をリネームしても通る)
[ ] コードはこのテストを通す最小限になっている
[ ] このテストに不要な投機的機能を追加していない
```

詳細な Planning フェーズ・Tracer Bullet 手順・Refactor 候補は `reference-tdd.md` を参照。

## 良いテスト・悪いテストの見分け方

### 良いテスト (integration-style)

```ts
// ✅ 観察可能な挙動を検証
test('ユーザは有効なカートでチェックアウトできる', async () => {
  const cart = createCart()
  cart.add(product)
  const result = await checkout(cart, paymentMethod)
  expect(result.status).toBe('confirmed')
})
```

特徴:
- ユーザ/呼び出し元が気にする挙動を検証
- public API のみ使用
- 内部リファクタで生き残る
- WHAT を記述、HOW は記述しない
- 1 テスト 1 論理アサーション

### 悪いテスト (implementation-detail)

```ts
// ❌ 内部実装に結合
test('checkout は paymentService.process を呼ぶ', async () => {
  const processSpy = jest.spyOn(paymentService, 'process')
  await checkout(cart, payment)
  expect(processSpy).toHaveBeenCalledWith(cart.total)
})
```

レッドフラグ:
- **内部コラボレータをモックしている**
- private メソッドをテストしている
- call count / call order を assert している
- 挙動が変わっていないリファクタでテストが落ちる
- テスト名が WHAT ではなく HOW を記述している
- interface 経由ではなく外部 (DB を直接 SELECT 等) で検証している

### interface 経由で検証する

```ts
// ❌ interface を迂回して DB 直接 SELECT
test('createUser は DB に保存する', async () => {
  await createUser({ name: 'Alice' })
  const row = await db.query('SELECT * FROM users WHERE name = ?', ['Alice'])
  expect(row).toBeDefined()
})

// ✅ interface で往復させて検証
test('createUser で作成されたユーザは取得できる', async () => {
  const user = await createUser({ name: 'Alice' })
  const retrieved = await getUser(user.id)
  expect(retrieved.name).toBe('Alice')
})
```

## モックは system boundary でのみ

### モックすべきもの

- 外部 API (Stripe、SendGrid、Twilio 等)
- データベース (場合による。テスト DB が使えるなら実 DB)
- 時刻・乱数
- ファイルシステム (場合による)

### モックすべきでないもの

- 自分のクラス・モジュール
- 内部コラボレータ
- 自分が制御できる全て

### モック容易性のための設計

#### 1. Dependency Injection を使う

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

#### 2. Generic fetcher より SDK スタイルを優先

```ts
// ✅ 各関数を独立にモックできる
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
- テストセットアップに条件分岐が不要
- どのエンドポイントを叩いているか一目でわかる
- エンドポイント単位の型安全

## カバレッジ改善

### 計測コマンド

```bash
npx vitest run --coverage
uv run pytest --cov=src --cov-report=term-missing --cov-report=html
```

### 優先順位

1. **権限・認可ロジック** — 抜けるとセキュリティ事故に直結
2. **金銭・決済関連** — 不具合のインパクトが大きい
3. **DB マイグレーション後の backfill** — 本番データで初めて動く
4. **エラーハンドリング分岐** — 正常系だけだと例外時に壊れる
5. UI / 表示ロジック — E2E でカバーしやすい

### カバレッジ 100% の罠

- カバー率が高くても「条件分岐の意味」を検証していなければ無意味
- `if (user.role === 'admin')` を通過しただけでは保証されない
- **境界値** (0, 空配列, null, 最大値) を意図的にテスト

## 権限・認可ロジックのテスト

### 典型パターン

```ts
describe('AuthorizationService', () => {
  describe('canEditDocument', () => {
    it.each([
      { role: 'admin',   ownerId: 'other', expected: true },
      { role: 'editor',  ownerId: 'self',  expected: true },
      { role: 'editor',  ownerId: 'other', expected: false },
      { role: 'viewer',  ownerId: 'self',  expected: false },
    ])('role=$role ownerId=$ownerId => $expected', ({ role, ownerId, expected }) => {
      const user = { id: 'self', role }
      const doc = { ownerId }
      expect(canEditDocument(user, doc)).toBe(expected)
    })
  })
})
```

- `it.each` / `pytest.mark.parametrize` で権限マトリクスを網羅
- ロール × リソース所有者 × 操作の組み合わせを表で書く
- **禁止操作のテストを忘れない** (false の assertion)

### マルチテナント境界テスト

`tenant_id = A` のユーザーが `tenant_id = B` のリソースを取得したら 404 / 403 を返すか必ずテストする。

## DB を使うテスト

| 種別 | 推奨 |
|---|---|
| 単体テスト | mock OK (Repository インタフェースをモック) |
| 統合テスト | 実 DB に接続 (Docker MySQL / SQLite in-memory) |
| マイグレーションテスト | 必ず実 DB (mock では SQL syntax error 検出不可) |

### トランザクションロールバック (pytest)

```python
@pytest.fixture
def db_session():
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()
```

## CI で失敗、ローカルで成功

- タイムゾーン依存 (UTC vs JST)
- ファイルシステムの大小区別 (macOS vs Linux)
- 並行実行での race condition (`--runInBand` で確認)
- 環境変数の差異 (.env vs CI secrets)

## 関連 skill

- Next.js / Prisma を使うテスト: `nextjs-prisma-patterns`
- Python 実行環境: `uv-python-tooling`
- バグの回帰テスト設計: `bug-investigation`
- Deep module 設計と interface 設計: `software-architecture`
