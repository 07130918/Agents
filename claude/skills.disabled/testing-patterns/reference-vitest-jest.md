# Vitest / Jest 落とし穴リファレンス

## `vi.mock()` / `jest.mock()` の巻き上げ

`vi.mock()` はファイル先頭に巻き上げられるため、`import` より先に実行される。

```ts
// ❌ 失敗例: 変数参照エラー
import { foo } from './foo'
const mockValue = 'bar'
vi.mock('./foo', () => ({ foo: () => mockValue })) // mockValue は undefined

// ✅ 正しい: vi.hoisted を使う
const { mockValue } = vi.hoisted(() => ({ mockValue: 'bar' }))
vi.mock('./foo', () => ({ foo: () => mockValue }))
import { foo } from './foo'
```

## モジュール部分モックの罠

```ts
// ❌ 失敗例: 他の export が undefined になる
vi.mock('./utils', () => ({
  formatDate: vi.fn(),
}))

// ✅ 正しい: importOriginal でマージ
vi.mock('./utils', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./utils')>()),
  formatDate: vi.fn(),
}))
```

## Spy のリセット忘れ

```ts
afterEach(() => {
  vi.clearAllMocks()    // mock の呼び出し履歴クリア
  vi.restoreAllMocks()  // spyOn で置き換えた実装も元に戻す
})
```

## 非同期処理の落とし穴

```ts
// ❌ await 忘れ: テストが早期終了
it('保存される', () => {
  saveUser(user)
  expect(db.users).toContain(user)
})

// ✅ 必ず await
it('保存される', async () => {
  await saveUser(user)
  expect(db.users).toContain(user)
})
```

## `vi.mock()` が効かない時のチェック

1. ファイルパスが正しいか (相対パス / alias の解決)
2. `vi.mock()` が import より先にあるか (`vi.hoisted` 使用)
3. `vi.resetModules()` で古いキャッシュを消したか
