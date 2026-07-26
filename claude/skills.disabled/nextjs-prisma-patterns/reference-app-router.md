# App Router + Server/Client Components リファレンス

## ディレクトリ規約

```
app/
  (auth)/                 # ルートグループ (URL に含まれない)
    login/page.tsx
  (dashboard)/
    layout.tsx            # 配下共通レイアウト
    users/
      page.tsx
      [id]/
        page.tsx          # 動的セグメント
        edit/page.tsx
  api/
    webhook/route.ts      # Route Handler (旧 API Routes)
  layout.tsx              # ルートレイアウト (必須)
  page.tsx
  loading.tsx             # Suspense fallback
  error.tsx               # Error Boundary
  not-found.tsx
```

### ルートグループ `(group)` の使い分け

- URL に反映されないグループでレイアウトを分ける
- 認証前後・管理画面・公開画面でレイアウトが異なるとき有効

## Server vs Client Components

### デフォルトは Server Component

App Router 配下はデフォルトで Server。Client にする時のみ `'use client'` を先頭に宣言。

### 境界の設計ルール

```tsx
// ✅ データ取得は Server、操作は Client
// app/users/page.tsx (Server Component)
import { UserTable } from './UserTable'

export default async function UsersPage() {
  const users = await prisma.user.findMany({ take: 50 })
  return <UserTable users={users} />
}

// app/users/UserTable.tsx (Client Component)
'use client'
export function UserTable({ users }: { users: User[] }) {
  const [sortBy, setSortBy] = useState('name')
}
```

### Props のシリアライズ制約

Server → Client Component の Props は **シリアライズ可能な値のみ**:

- ✅ プリミティブ、配列、プレーンオブジェクト、Date
- ❌ 関数、class インスタンス、Symbol、Map/Set
- ⚠️ Prisma `Decimal` は文字列に変換してから渡す

### よくある失敗

- Server Component から Client Component の関数を import → エラー
- Prisma を Client Component で import → ブラウザバンドル混入で実行時エラー
- Server Component で `useState` / `useEffect` → 実行時エラー
