# nextjs-drizzle-patterns

Next.js App Router と Drizzle ORM を組み合わせた MySQL アプリで、API 実装、schema 変更、migration、Knex から Drizzle への移行、CI/CD 上の migration 実行を扱うための workflow。

## 使う場面

- Next.js / Drizzle / MySQL / drizzle-kit / `sql/drizzle` / `src/lib/db/schema.ts` に関する実装・修正・レビュー。
- Knex query や `@/lib/knex` 依存を Drizzle query に移行する作業。
- DB migration を Cloud Build、Cloud Run Job、GitHub Actions、Docker image で実行する設計確認。
- Zod request / response schema、Drizzle schema、SQL migration、ドキュメントの整合性を確認する作業。
- Prisma 固有の設計は `nextjs-prisma-patterns`、Chakra UI 部品は `react-chakra-ui`、一般的な CI 調査は `github-actions-ops` を優先する。

## 対象外

- Prisma schema / Prisma Client / `prisma migrate` 固有の作業。
- Chakra UI v3 component prop や見た目だけの修正。
- Drizzle や DB migration に関係しない GitHub Actions の一般的な失敗調査。
- Python / Flask / FastAPI backend の DB 実装。

## 入力

- 対象 repository と branch。
- 変更対象の route、query helper、schema、migration、CI/CD file。
- base branch との差分、または staged diff。
- ローカル DB 起動方法と migration 実行コマンド。

## 出力

- 実装時: schema、migration、query、API、test、CI/CD の整合した変更。
- レビュー時: blocker / non-blocker を分けた指摘。
- 調査時: migration 失敗原因、再現手順、修正方針、検証結果。

## 手順

### 1. 現状を確認する

1. `package.json` で Next.js、Drizzle、drizzle-kit、test runner、DB client を確認する。
2. `drizzle.config.*` と migration 出力先を確認する。
3. `src/lib/db/schema.ts`、query helper、API route、Zod schema の責務分離を確認する。
4. 既存 migration の命名、生成 SQL、meta snapshot、bootstrap SQL の扱いを読む。
5. `@/lib/knex`、`Knex` type、raw SQL が残っていないか確認する。

### 2. Drizzle schema を変更する

- `schema.ts` を真実の型定義として扱い、SQL migration と乖離させない。
- カラム名、nullable、default、index、unique、foreign key、timestamp 更新方針を明示する。
- `NOT NULL` 追加は既存データの backfill と default を先に決める。
- DB 側で守るべき制約と Zod だけで守る制約を分け、判断をドキュメントに残す。
- `updated_at` は mutation のたびに更新されるか確認する。

### 3. migration を作る

- drizzle-kit の生成物と手書き修正の境界を明確にする。
- 生成 SQL、meta snapshot、journal、bootstrap schema のうち repository が追跡すべきものを既存方針に合わせる。
- 破壊的変更では、deploy 順序を考慮して expand -> backfill -> contract に分ける。
- rollback が必要な repository では、FK 制約、index、view、generated column を含めて戻せるか確認する。
- 本番 DB に直接 `ALTER TABLE` しない。必ず migration と deploy pipeline に載せる。

### 4. Knex から Drizzle に移行する

- `getKnex()` の共有 singleton や `Knex` 型 import を query 層から消す。
- `select`、`insert`、`update`、`delete` は Drizzle query builder に寄せる。
- JOIN は明示的に書き、N+1 と cartesian product を避ける。
- 集計は MySQL の timezone / week rule 依存が要件と合うか確認する。曖昧ならアプリ側集計も検討する。
- raw SQL が必要な場合は、型と binding を明示し、ユーザー入力を文字列連結しない。

### 5. API と認可を合わせる

- App Router API route では認証、ロール、所有関係、IDOR 防止を route handler 側で必ず確認する。
- UI 側で隠している操作も API で再検証する。
- request Zod、response Zod、Drizzle select の shape を揃える。
- 日付、decimal、nullable、enum は JSON serialize 後の型まで確認する。
- error response は既存 project の形式に合わせる。

### 6. CI/CD migration を設計する

- migration は application deploy 前に、同じ image revision または互換 revision で実行する。
- Cloud Run Job などの job 名が固定の場合、同時 deploy で別 build の image を実行しない設計になっているか確認する。
- 並列 deploy の可能性があるなら、revision-scoped job 名か deploy 直列化を使う。
- MySQL では migration wrapper で `GET_LOCK` / `RELEASE_LOCK` を使い、二重適用を避ける。
- lock release は success / failure の両方で実行し、timeout と orphan lock を考慮する。
- Dockerfile の migration target は CI で build して、deploy 時に初めて壊れないようにする。

### 7. テストする

- schema 変更: migration 適用、bootstrap、rollback 方針、既存 seed の通過を確認する。
- query 変更: happy path、not found、権限なし、境界値、nullable、重複制約をテストする。
- API 変更: role ごとの 200 / 403 / 404、IDOR、invalid payload をテストする。
- migration image 変更: `docker build --target migration` 相当を CI またはローカルで確認する。
- generated file を除外してレビューする必要がある場合は、除外 path を明示する。

## レビュー観点

- Drizzle schema、SQL migration、Zod、docs が同じ仕様を表しているか。
- DB 制約が Zod のみに寄りすぎていないか。
- `updated_at`、default、nullable、unique、FK、index の抜けがないか。
- query が user-controlled input を raw SQL に埋め込んでいないか。
- role / ownership check が route handler に存在するか。
- migration が同時実行、途中失敗、再実行に耐えるか。
- generated diff と実装 diff を分けて読めているか。

## 失敗時

- `drizzle-kit migrate` が落ちたら、先に適用中の SQL、現在の `__drizzle_migrations`、DB の実 schema を確認する。
- Docker / Cloud Build 上だけ落ちる場合は、migration target に必要 file が copy されているか確認する。
- CI が長い場合は、Drizzle migration check / migration image build を独立 job に分離できるか確認する。
- main rebase 後に壊れた場合は、Knex 削除や schema path 変更を疑い、古い import を先に消す。

## 関連 skill

- `nextjs-prisma-patterns`: Prisma を使う Next.js project。
- `react-chakra-ui`: Chakra UI v3 component 実装。
- `testing-patterns`: Jest / Vitest / pytest の test 設計。
- `github-actions-ops`: GitHub Actions の失敗調査と workflow 運用。
- `docs-code-consistency-audit`: docs と schema / API の乖離監査。

## 発火テスト例

発火すべき:

- Next.js の Drizzle schema にカラムを追加して migration を作りたい。
- `@/lib/knex` 依存の query を Drizzle に移行して。
- Cloud Run Job で drizzle-kit migration を実行する設計をレビューして。
- `src/lib/db/schema.ts` と Zod response schema のズレを直したい。
- Drizzle の migration image を CI で build する job を追加したい。

発火すべきでない:

- Prisma schema の relation を見直して。
- Chakra UI v3 の Dialog が崩れるので直して。
- GitHub Actions の cache hit 率を改善して。
- Flask API の SQLAlchemy query を直して。
- README の文章だけ整えて。
