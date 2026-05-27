# Python バックエンド実装ガイド

## 実行環境

`uv` で実行する (詳細は `uv-python-tooling` skill 参照)。

---

## Knex.js / SQL クエリパターン

### 相関サブクエリ vs JOIN (パフォーマンス重要)

```sql
-- ❌ 相関サブクエリ - レコード数分だけ実行される (O(n)回クエリ)
SELECT
  u.id,
  u.name,
  (SELECT COUNT(*) FROM activities a WHERE a.user_id = u.id) as activity_count
FROM users u

-- ✅ LEFT JOIN + GROUP BY - 1回のクエリで完結
SELECT
  u.id,
  u.name,
  COUNT(a.id) as activity_count
FROM users u
LEFT JOIN activities a ON a.user_id = u.id
GROUP BY u.id, u.name
```

### Knex.js での実装

```js
// ✅ 推奨: JOIN パターン
const users = await knex('users as u')
  .leftJoin('activities as a', 'a.user_id', 'u.id')
  .select('u.id', 'u.name')
  .count('a.id as activity_count')
  .groupBy('u.id', 'u.name')

// ✅ 複数条件の JOIN
knex('orders as o')
  .leftJoin('order_items as oi', function() {
    this.on('oi.order_id', '=', 'o.id')
        .andOn('oi.status', '=', knex.raw('?', ['active']))
  })
```

### NULL 安全な比較

```js
// ✅ NULL チェック
.whereNull('deleted_at')
.whereNotNull('confirmed_at')

// ✅ NULL を含む条件分岐
.where(function() {
  this.whereNull('parent_id').orWhere('parent_id', parentId)
})

// ✅ COALESCE パターン
knex.raw('COALESCE(display_name, name) as label')
```

---

## DB マイグレーション設計

### 原則

- ✅ 必ずマイグレーションファイルを作成する
- ❌ 直接 `ALTER TABLE` を本番DBに実行しない
- ✅ up/down 両方を実装する
- ✅ `NOT NULL` カラムには必ず `defaultTo()` を設定

```js
// ✅ マイグレーションファイルの構造
exports.up = function(knex) {
  return knex.schema.table('users', function(table) {
    table.string('role', 50).notNullable().defaultTo('viewer').comment('ユーザーロール')
    table.index(['role', 'status'], 'idx_users_role_status')
  })
}

exports.down = function(knex) {
  return knex.schema.table('users', function(table) {
    table.dropIndex(['role', 'status'], 'idx_users_role_status')
    table.dropColumn('role')
  })
}
```

### インデックス設計の指針

- 検索頻度・カーディナリティを考慮して設計
- 複合インデックスは検索条件の順序に合わせる
- 外部キーには必ずインデックスを作成する

---

## 権限・ロール実装パターン

### ロール定義

```python
# ✅ Enum での定義
from enum import Enum

class UserRole(Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    VIEWER = 'viewer'

# ✅ 権限チェック関数
ROLE_PERMISSIONS = {
    UserRole.ADMIN.value: ['read', 'write', 'delete', 'manage_users'],
    UserRole.MANAGER.value: ['read', 'write'],
    UserRole.VIEWER.value: ['read'],
}

def has_permission(user_role: str, required_permission: str) -> bool:
    return required_permission in ROLE_PERMISSIONS.get(user_role, [])
```

### Flask での権限デコレータ

```python
from functools import wraps
from flask import g, jsonify

def require_permission(permission: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not has_permission(g.current_user.role, permission):
                return jsonify({'error': '権限がありません'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ✅ 使用例
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_permission('delete')
def delete_user(user_id: int):
    ...
```

---

## Flask エンドポイント設計

```python
from flask import Blueprint, request, jsonify, g

bp = Blueprint('users', __name__, url_prefix='/api/users')

@bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id: int):
    user = db.execute('SELECT * FROM users WHERE id = %s', [user_id]).fetchone()
    if not user:
        return jsonify({'error': 'ユーザーが見つかりません'}), 404
    return jsonify(dict(user))

@bp.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f'Unhandled error: {e}')
    return jsonify({'error': 'サーバーエラーが発生しました'}), 500
```

## FastAPI エンドポイント設計

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserResponse(BaseModel):
    id: int
    name: str
    role: str

@app.get('/api/users/{user_id}', response_model=UserResponse)
async def get_user(user_id: int, db=Depends(get_db)):
    user = await db.fetch_one('SELECT * FROM users WHERE id = :id', {'id': user_id})
    if not user:
        raise HTTPException(status_code=404, detail='ユーザーが見つかりません')
    return user
```

---

## デバッグパターン

```python
# ✅ SQL クエリのデバッグ (Knex.js)
knex.on('query', (query) => {
  console.log('SQL:', query.sql)
  console.log('Bindings:', query.bindings)
})

# ✅ パフォーマンス計測
import time

start = time.time()
result = db.execute(query)
print(f'Query time: {time.time() - start:.3f}s')
```
