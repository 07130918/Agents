# ドキュメント・コード乖離監査

## 目的

ドキュメントに書かれたコマンド、ルート、API、環境変数、バージョン、アーキテクチャ規約、テスト方針が、現在のコードベースと一致しているかを精査して報告する。主目的は監査と報告であり、ユーザーが明示しない限り修正やPR作成は行わない。

## 開始条件

- ユーザーが「docs とコードの乖離を調査」「最新 main をフルスキャン」「ドキュメントが実装と合っているか確認」「unit test が十分か調べて」などを依頼したら使う。
- 対象ブランチが指定されていなければ、既定ブランチの最新リモート状態を基準にする。
- 作業ツリーに未コミット変更がある場合は、切り替えやpullの前に状態を報告し、破壊的操作はしない。

## 基本方針

- 事実はコード、設定ファイル、テスト、CI設定から確認する。
- ドキュメント側は claims として扱い、コード側に対応する根拠があるかを照合する。
- 不明瞭な記述は「乖離」ではなく「要明確化」として扱う。
- UIの見た目より、運用事故につながりやすいコマンド、ルート、API、環境変数、認証、デプロイ、テスト対象を優先する。
- 最新情報が必要な外部仕様やライブラリ仕様を評価する場合は、公式ドキュメントを確認する。単にリポジトリ内の乖離を見るだけならWeb検索は不要。

## 推奨ワークフロー

### 1. 基準コミットを確定する

最初に次を確認する。

- 現在のブランチと作業ツリー状態
- origin の既定ブランチ
- 監査対象コミット
- package manager と主要スクリプト

例:

```bash
git status --short --branch
git symbolic-ref refs/remotes/origin/HEAD
git fetch origin
git rev-parse origin/main
rg --files | rg '(^package.json$|^Makefile$|^vitest.config|^next.config|^Dockerfile$|^cloud-build/)'
```

`main` が既定でない場合は、`origin/HEAD` が指すブランチを基準にする。ローカル `main` へ切り替える必要はない。可能なら `origin/main` などのリモート参照に対して調査する。

### 2. ドキュメントを棚卸しする

対象に含める候補:

- `AGENTS.md`
- `README.md`
- `docs/**/*.md`
- `.env.example`
- `package.json`
- `Makefile`
- `Dockerfile`
- `cloud-build/**/*.yaml`
- `.github/workflows/**/*.yml`

見るべき claim:

- 実行コマンド: `make setup`, `make up`, `make ci`, `npm run ...`
- ページルート: `/search`, `/learning-style-assessment`, `/universities` など
- APIルート: `/api/v1/...`, `/api/v2/...`
- 環境変数: `NEXT_PUBLIC_*`, サーバ専用 env, Cloud Build substitutions
- バージョン: Next.js, React, Prisma, Chakra UI, Vitest, Node
- アーキテクチャ規約: import rule, directory rule, Server Component方針, auth helper
- テスト方針: unit/integration対象、coverage include/exclude、CIで走る範囲

検索例:

```bash
rg -n "make |npm run|pnpm|yarn|/api/|NEXT_PUBLIC_|process\\.env|Cloud Build|Next\\.js|Prisma|Vitest|coverage|テスト|unit" AGENTS.md README.md docs .env.example package.json Makefile Dockerfile cloud-build .github
```

### 3. コード側の実態を棚卸しする

確認対象:

- コマンド: `package.json` scripts、`Makefile`
- ページルート: `src/app/**/page.tsx`
- APIルート: `src/app/api/**/route.ts`
- 環境変数: `src/lib/env.ts`, `src/lib/envs.ts`, `process.env`, `getEnvs`, `env`
- デプロイ設定: `cloud-build`, `Dockerfile`, `.env.example`
- テスト設定: `vitest.config.*`, test scripts, coverage include/exclude
- 重要ロジック: `src/lib/**`, `src/features/**/utils`, `src/features/**/queries`, `src/features/**/serverFetch`

検索例:

```bash
rg --files src/app | rg '/(page|route)\\.(ts|tsx)$'
rg -n "process\\.env|NEXT_PUBLIC_|getEnvs\\(|env\\." src Dockerfile cloud-build .env.example
rg -n "coverage|include|exclude|COVERAGE_TARGET|test:coverage|test:lib|test:features" package.json vitest.config.* Makefile
rg --files src/features src/lib | rg '(utils|queries|serverFetch|transform|schema|domain)'
```

### 4. 照合カテゴリ

最低限、次を個別に判定する。

1. コマンド乖離
   - docsにあるコマンドが `package.json` または `Makefile` に存在するか。
   - CI必須と書かれているコマンドが実際にCIやMakefileに含まれるか。

2. ルート乖離
   - docs記載のページ/APIルートが `src/app` に存在するか。
   - 実装済みルートが docs の重要一覧から漏れていないか。
   - API v1/v2 の表記が実装と一致しているか。

3. 環境変数・デプロイ乖離
   - `src/lib/env.ts` と `.env.example` が一致するか。
   - サーバ変数と `NEXT_PUBLIC_*` の扱いが Dockerfile / Cloud Build と一致するか。
   - docsに「追加時に更新する」とあるファイル群が実際に更新対象として妥当か。

4. バージョン乖離
   - docsの Next.js、React、Chakra UI、Prisma、Vitest などのバージョン表記が `package.json` と一致するか。
   - 「Next.js 16 App Router」などの大きな前提は重点的に確認する。

5. アーキテクチャ規約乖離
   - import方向、features構造、共有型の置き場所、認証ヘルパー、Server Component方針などが実装例と矛盾していないか。
   - 規約違反があっても、docsの乖離ではなくコード側の違反として分けて報告する。

6. テスト・coverage乖離
   - docsやCIが期待する test command と実際の scripts が一致するか。
   - coverage include/exclude が、重要な非UIロジックを含んでいるか。
   - 0% または低coverageの重要ロジックを抽出する。

### 5. テスト十分性の評価

「unit testは十分か」は単純なcoverage率だけで判定しない。次の観点で見る。

- 重要なドメインロジック、認証・認可、DBクエリ、外部通知、SEO、変換処理にテストがあるか。
- UIコンポーネント中心のcoverageで、実際のfeature logicが抜けていないか。
- error path、fallback、schema validation failure、外部API failureがテストされているか。
- hookやcomponentのテストが内部mockに寄りすぎて、public behaviorを見ていない箇所がないか。

必要に応じて実行する。

```bash
npm run test:coverage
npm run test:lib
npm run test:features
make ci
```

重い場合は、まず `vitest.config.*` と既存coverage出力を確認し、実行コストと目的をユーザーに短く説明する。

### 6. 報告フォーマット

報告は日本語で、先に結論を出す。推奨構成:

```markdown
**結論**
{全体判定。重大な乖離の有無、テスト十分性の要約}

**監査基準**
- 対象: origin/main の {commit}
- 確認範囲: docs, README, AGENTS, package scripts, src/app, env, vitest config
- 実行コマンド: {実行したもの}

**乖離・リスク**
| 優先度 | 種別 | 内容 | 根拠 | 推奨対応 |
|---|---|---|---|---|
| P1 | コマンド | ... | docs/... と package.json | ... |

**一致を確認した点**
- ...

**unit test評価**
- 十分な点: ...
- 不足: ...
- 優先追加候補: ...

**次に切るべきPR**
1. ...
2. ...
```

優先度:

- P0: ユーザー操作、デプロイ、セキュリティに直結し即修正が必要
- P1: 誤運用や回帰検知漏れにつながる重要な乖離
- P2: docsの古さやテスト不足として計画的に直すべきもの
- P3: 明確化、整理、重複削除

### 7. PR化を依頼された場合

監査とPR作成は分けて考える。ユーザーがPR作成も依頼した場合:

- docs更新、coverage設定、テスト追加は原則として別PRに分ける。
- 1 PR 1目的にする。
- PR本文には監査で見つけた根拠と確認コマンドを書く。
- 既存の未コミット変更は触らない。

分割例:

1. docsのコマンド・ルート・バージョン更新
2. coverage include の拡張
3. feature logic の不足テスト追加
4. lib utilities の不足テスト追加
5. jsdom未実装APIログの抑制

## 注意

- `README` や `docs` の記述を長く引用しない。必要な範囲だけ要約する。
- 調査中に見つけたコードの設計改善案は、docs乖離と混ぜない。
- 「テストがない」だけで即P1にしない。影響範囲、事故時の被害、既存E2Eやintegration coverageの有無を加味する。
- `git reset --hard` や `git checkout --` は使わない。
- ユーザーが「最新 main」と言った場合は、必ず fetch して基準コミットを明記する。
