# Server Actions リファレンス

## 基本形

```tsx
// app/actions/user.ts
'use server'

import { prisma } from '@/lib/prisma'
import { revalidatePath } from 'next/cache'
import { z } from 'zod'

const UpdateUserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
})

export async function updateUser(formData: FormData) {
  const parsed = UpdateUserSchema.safeParse({
    id: formData.get('id'),
    name: formData.get('name'),
  })
  if (!parsed.success) {
    return { error: 'invalid_input', issues: parsed.error.flatten() }
  }

  await prisma.user.update({
    where: { id: parsed.data.id },
    data: { name: parsed.data.name },
  })

  revalidatePath('/users')
  return { ok: true }
}
```

## 必須セキュリティチェック

Server Action はクライアントから任意のデータで呼ばれうる。以下を必ず行う:

1. **認証**: `auth()` / `getServerSession()` でログイン中ユーザーを取得
2. **認可**: 対象リソースを操作できるか (テナント境界、ロール)
3. **入力バリデーション**: zod / valibot で型と制約を検証
4. **CSRF**: Next.js は同一オリジンチェックがあるが、重要操作は追加でトークン検証

```ts
'use server'
export async function deleteDocument(id: string) {
  const session = await auth()
  if (!session?.user) return { error: 'unauthorized' }

  const doc = await prisma.document.findUnique({ where: { id } })
  if (!doc) return { error: 'not_found' }
  if (doc.tenantId !== session.user.tenantId) return { error: 'forbidden' }

  await prisma.document.delete({ where: { id } })
  revalidatePath('/documents')
  return { ok: true }
}
```

## エラー返却パターン

- **例外を throw しない**: throw すると `error.tsx` に飛び、フォームの部分エラー表示ができない
- **Result 型を返す**: `{ ok: true, data } | { ok: false, error: string }` のユニオン型

## useActionState との連携

```tsx
'use client'
import { useActionState } from 'react'
import { updateUser } from './actions'

export function EditForm({ user }) {
  const [state, formAction] = useActionState(updateUser, null)
  return (
    <form action={formAction}>
      <input name="name" defaultValue={user.name} />
      {state?.error && <p>{state.error}</p>}
      <button type="submit">保存</button>
    </form>
  )
}
```
