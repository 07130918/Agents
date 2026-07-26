# Prisma スキーマ・クエリ・キャッシュ リファレンス

## 命名規約

- **モデル**: PascalCase 単数 (`User`, `OrderItem`)
- **フィールド**: camelCase (`createdAt`, `ownerId`)
- **テーブル**: `@@map("snake_case")` で DB 側にマッピング
- **カラム**: `@map("snake_case")`

```prisma
model User {
  id        String   @id @default(uuid())
  email     String   @unique
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt       @map("updated_at")

  @@map("users")
}
```

## リレーション

```prisma
model User {
  id    String  @id @default(uuid())
  posts Post[]  // 1対多の受け側
}

model Post {
  id       String @id @default(uuid())
  authorId String @map("author_id")
  author   User   @relation(fields: [authorId], references: [id], onDelete: Cascade)

  @@index([authorId])
}
```

- 外部キーには必ず `@@index`
- `onDelete` を明示 (`Cascade` / `SetNull` / `Restrict`)

## マルチテナント設計

```prisma
model Document {
  id       String @id @default(uuid())
  tenantId String @map("tenant_id")
  title    String

  tenant   Tenant @relation(fields: [tenantId], references: [id])

  @@index([tenantId])
  @@index([tenantId, createdAt])
}
```

すべてのクエリで `where: { tenantId }` を強制するため、Prisma ミドルウェア or Repository 層でラップする。

## N+1 回避

```ts
// ❌ N+1
const posts = await prisma.post.findMany()
for (const post of posts) {
  post.author = await prisma.user.findUnique({ where: { id: post.authorId } })
}

// ✅ include
const posts = await prisma.post.findMany({ include: { author: true } })

// ✅ select で必要フィールドのみ
const posts = await prisma.post.findMany({
  select: {
    id: true,
    title: true,
    author: { select: { id: true, name: true } },
  },
})
```

## ページング

カーソルベースが推奨 (深いページで遅い offset/limit より):

```ts
const posts = await prisma.post.findMany({
  take: 20,
  cursor: lastId ? { id: lastId } : undefined,
  skip: lastId ? 1 : 0,
  orderBy: { createdAt: 'desc' },
})
```

## トランザクション

```ts
// インタラクティブ (条件分岐が必要なとき)
await prisma.$transaction(async (tx) => {
  const user = await tx.user.create({ data: { email } })
  await tx.profile.create({ data: { userId: user.id } })
})

// バッチ (独立クエリ群の一括実行)
await prisma.$transaction([
  prisma.user.delete({ where: { id } }),
  prisma.auditLog.create({ data: { action: 'DELETE_USER', userId: id } }),
])
```

## 非正規化フィールドの更新

一覧用に `customer_name` などを非正規化した場合、元データ更新時に必ず同期:

```ts
await prisma.$transaction([
  prisma.customer.update({ where: { id }, data: { name: newName } }),
  prisma.order.updateMany({
    where: { customerId: id },
    data: { customerName: newName },
  }),
])
```

## キャッシュ戦略

### fetch のキャッシュ

```ts
const res = await fetch(url)                            // デフォルト force-cache
const res = await fetch(url, { cache: 'no-store' })     // SSR 相当
const res = await fetch(url, { next: { revalidate: 60 } }) // ISR 60秒
const res = await fetch(url, { next: { tags: ['users'] } }) // タグベース
```

### Route Segment Config

```tsx
export const dynamic = 'force-dynamic'
export const revalidate = 60
export const fetchCache = 'default-cache'
```

### Prisma 結果のキャッシュ

Prisma 自体はキャッシュしない:

```ts
import { unstable_cache } from 'next/cache'

export const getUsers = unstable_cache(
  async (tenantId: string) => prisma.user.findMany({ where: { tenantId } }),
  ['users'],
  { tags: ['users'], revalidate: 300 }
)
```
