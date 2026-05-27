# nextjs-prisma-patterns

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Next.js + Prisma 実装ガイド

App Router と Prisma を組み合わせたプロジェクトで使う設計パターン。`react-chakra-ui` は UI コンポーネントを扱うが、本 skill はルーティング・データ取得・Server Actions を扱う。

## 詳細リファレンス (タスクに応じて読む)

| ファイル | 内容 | 読むタイミング |
|---|---|---|
| `reference-app-router.md` | App Router ディレクトリ規約、Server/Client Components 境界、シリアライズ制約 | ページ・レイアウト・コンポーネント分割の設計時 |
| `reference-server-actions.md` | Server Actions 基本形、必須セキュリティチェック、Result 型、`useActionState` 連携 | フォーム・mutation 実装時 |
| `reference-prisma.md` | スキーマ設計 (命名・リレーション・マルチテナント)、N+1 回避、ページング、トランザクション、キャッシュ戦略 | DB スキーマ追加・クエリ実装時 |

## 最頻出の落とし穴 (即時参照)

### 境界系

- **Server Component から Client Component の関数 import** → エラー。Client → Server は Server Actions のみ
- **Prisma を Client Component で import** → ブラウザに bundle され実行時エラー
- **Server Component で `useState` / `useEffect`** → 実行時エラー (hooks は Client 専用)
- **Server → Client Props は serializable のみ**: 関数・class・Symbol・Map/Set 不可、Decimal は文字列化

### キャッシュ・ビルド

- `.next/` の不整合で変更が反映されない → `rm -rf .next && npm run dev` (AGENTS.md のバグ調査原則)
- スキーマ変更後の `npx prisma generate` 忘れ → CI の `postinstall` に組み込む

### 環境変数の境界

- `process.env.FOO` は Server のみ、`NEXT_PUBLIC_FOO` は Client に露出 (秘密を入れない)
- マルチテナントで `tenantId` を URL クエリから信頼しない (必ず session から)

## Server Actions セキュリティの絶対ルール

すべての Server Action で以下を必ず実行する (詳細は `reference-server-actions.md`):

1. **認証**: `auth()` / `getServerSession()` でユーザー取得
2. **認可**: テナント境界 + ロール確認
3. **入力バリデーション**: zod / valibot
4. **エラーは throw せず Result 型で返す** (フォーム部分エラー表示のため)

## Prisma スキーマの絶対ルール

- **外部キーには必ず `@@index`** を張る (JOIN/WHERE で遅くなる)
- **`onDelete` を明示** (`Cascade` / `SetNull` / `Restrict`)
- マルチテナントは `@@index([tenantId])` 必須、全クエリで `where: { tenantId }` 強制
- 命名: モデル PascalCase 単数、フィールド camelCase、DB 側は `@@map` / `@map` でスネークケース

## 関連スキル

- `react-chakra-ui`: Chakra UI v3 コンポーネント実装
- `python-backend`: FastAPI / Knex.js (Prisma とは別系統だが権限設計は共通)
- `testing-patterns`: Server Actions / Prisma を使うテスト
- `software-architecture`: 二層テナントモデル (corporation / provider)

## Claude Code 版

# Next.js + Prisma 実装ガイド

App Router と Prisma を組み合わせたプロジェクトで使う設計パターン。`react-chakra-ui` は UI コンポーネントを扱うが、本 skill はルーティング・データ取得・Server Actions を扱う。

## 詳細リファレンス (タスクに応じて読む)

| ファイル | 内容 | 読むタイミング |
|---|---|---|
| `reference-app-router.md` | App Router ディレクトリ規約、Server/Client Components 境界、シリアライズ制約 | ページ・レイアウト・コンポーネント分割の設計時 |
| `reference-server-actions.md` | Server Actions 基本形、必須セキュリティチェック、Result 型、`useActionState` 連携 | フォーム・mutation 実装時 |
| `reference-prisma.md` | スキーマ設計 (命名・リレーション・マルチテナント)、N+1 回避、ページング、トランザクション、キャッシュ戦略 | DB スキーマ追加・クエリ実装時 |

## 最頻出の落とし穴 (即時参照)

### 境界系

- **Server Component から Client Component の関数 import** → エラー。Client → Server は Server Actions のみ
- **Prisma を Client Component で import** → ブラウザに bundle され実行時エラー
- **Server Component で `useState` / `useEffect`** → 実行時エラー (hooks は Client 専用)
- **Server → Client Props は serializable のみ**: 関数・class・Symbol・Map/Set 不可、Decimal は文字列化

### キャッシュ・ビルド

- `.next/` の不整合で変更が反映されない → `rm -rf .next && npm run dev` (CLAUDE.md のバグ調査原則)
- スキーマ変更後の `npx prisma generate` 忘れ → CI の `postinstall` に組み込む

### 環境変数の境界

- `process.env.FOO` は Server のみ、`NEXT_PUBLIC_FOO` は Client に露出 (秘密を入れない)
- マルチテナントで `tenantId` を URL クエリから信頼しない (必ず session から)

## Server Actions セキュリティの絶対ルール

すべての Server Action で以下を必ず実行する (詳細は `reference-server-actions.md`):

1. **認証**: `auth()` / `getServerSession()` でユーザー取得
2. **認可**: テナント境界 + ロール確認
3. **入力バリデーション**: zod / valibot
4. **エラーは throw せず Result 型で返す** (フォーム部分エラー表示のため)

## Prisma スキーマの絶対ルール

- **外部キーには必ず `@@index`** を張る (JOIN/WHERE で遅くなる)
- **`onDelete` を明示** (`Cascade` / `SetNull` / `Restrict`)
- マルチテナントは `@@index([tenantId])` 必須、全クエリで `where: { tenantId }` 強制
- 命名: モデル PascalCase 単数、フィールド camelCase、DB 側は `@@map` / `@map` でスネークケース

## 関連スキル

- `react-chakra-ui`: Chakra UI v3 コンポーネント実装
- `python-backend`: FastAPI / Knex.js (Prisma とは別系統だが権限設計は共通)
- `testing-patterns`: Server Actions / Prisma を使うテスト
- `software-architecture`: 二層テナントモデル (corporation / provider)
