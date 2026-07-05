<!--
AGENTS.md / CLAUDE.md テンプレート (プロジェクト共通指示)

使い方:
1. AGENTS.md と CLAUDE.md の両方をプロジェクトルートにコピーする
2. {{ }} を埋め、該当しないセクションは削除する。2 ファイルには同じ内容を反映する
   (片方を埋めてからもう片方へコピーし、ツール固有の行だけ調整すると速い)
3. 記入が終わったらこの説明コメントを削除する

2 ファイルは意図的な対称配置: 各ツール (Codex は AGENTS.md、Claude Code は CLAUDE.md) が
ネイティブに読むファイルを、冗長でもそれぞれフル内容で用意する。ラッパーや @import は使わない。

書く基準 (全体で 200 行以内、理想は 60〜130 行):
- ✅ コードから推測できないもの: コマンド、非標準の規約、アーキテクチャ決定、gotcha
- ❌ コードから推測できるもの、一般論 (DRY/SOLID 等)、頻繁に変わる情報 (ロードマップ・ビジネスモデル等)、
     グローバル設定と重複する内容 (言語・uv・絵文字・コミット形式・Git/PR 運用・レビュー順序)
- 迷ったら「この記述を消したらエージェントがミスするか?」で判断する
- 条件付きで必要になる長い手順は、ここではなく skill (.claude/skills/) に切り出す
-->

# {{プロジェクト名}}

⚠️ CLAUDE.md と AGENTS.md は対称管理する。片方を変更したら、もう片方にも同じ変更を反映する。

{{何のためのサービス/ツールかを 1〜3 行。対象ユーザーと主要機能}}

{{設計の正がある場合は宣言する。例: docs/design/mvp.md が実装の契約。実装と食い違ったらそちらが正}}

## クイックスタート

```bash
{{make dev}}        # {{ローカル起動 (URL も書く: http://localhost:3000)}}
{{make check}}      # {{lint + format + 型チェック一括}}
{{make test}}       # {{単体テスト}}
{{make db-migrate}} # {{DB マイグレーション適用}}
```

## 技術スタック

- {{言語/フレームワーク + メジャーバージョン。例: Next.js 16 (App Router) / React 19 / TypeScript}}
- {{UI。例: Chakra UI v3 + theme.ts のデザイントークン}}
- {{DB/ORM。例: MySQL + Drizzle (drizzle-kit で migration)}}
- {{認証。例: NextAuth (ロール: admin / editor / viewer)}}
- {{テスト/lint。例: Vitest + biome (インデント 2 / ダブルクォート)}}
- {{インフラ/CI。例: GCP Cloud Run + Cloud Build / GitHub Actions}}

## アーキテクチャ

{{リクエストの流れ or レイヤ責務を 5〜10 行で。ディレクトリ説明は非自明なものだけに絞る}}

{{例:
- src/app/api/* は「認証・ロール検証 + Zod バリデーション + queries 呼び出し」のみ。ロジックは src/lib/ へ
- DB アクセスは src/lib/db/queries/ に集約する。コンポーネントから直接呼ばない
}}

詳細: {{docs/architecture.md}}

## 実装規約

<!-- 非標準のもの・このプロジェクト特有のものだけを番号付きで。グローバル設定にある規約は書かない -->

1. {{例: UI の色・余白は theme.ts のトークンを使う。マジックナンバー禁止}}
2. {{例: 1 つの tsx ファイルには 1 つの export component のみ}}
3. {{例: テストは it() ではなく test() を使い、説明文は日本語で書く}}
4. {{例: TODO コメントは TODO(asana-XXXXX) 形式でチケット ID を必須にする}}
5. {{チーム開発の場合、メンバー共通で守る規約もここに書く。例: コメント・PR・issue は日本語}}

## 非自明な仕様 (推測不可なもの)

<!-- ドメイン固有の制約、事故由来の規約 (根拠の事故 + 検出手段を併記)、gotcha だけを書く -->

- {{例: ロール editor は自分の担当データのみ更新可。UI 制御だけでなく API 側でも必ずロール検証する}}
- {{例: 関数内 import 禁止。過去に UnboundLocalError 事故があった。ruff PLC0415 で検出}}
- {{例: 一覧系クエリは論理削除 (deleted_at) の除外を必ず入れる。生クエリを書くと漏れる}}

## 環境変数 / Secret の追加・変更

追加・変更・削除時は以下をすべて同時に更新する:

- {{env schema。例: src/lib/env.ts}}
- `.env.example`
- {{CI/CD 設定。例: cloud-build/dev.yaml と cloud-build/prod.yaml}}
- {{Dockerfile。例: NEXT_PUBLIC_* は ARG/ENV の追加も必要}}
- {{Secret 管理。例: GCP Secret Manager / GitHub Secrets}}

⚠️ `.env.example` だけ更新して CI/CD 側を更新しない状態を残さない。

## デプロイ / CI

- {{デプロイ経路。例: develop merge → Cloud Build → Cloud Run (dev)。タグ push → 本番}}
- {{CI ワークフロー名と、PR 前にローカルで通すべき同等コマンド}}
- {{本番マイグレーションの実行方法 (誰が・どこから実行するか)}}

## セキュリティ (必須)

- 秘密情報 (API キー / トークン / パスワード) をコード・ログ・ドキュメント・コミットに含めない
- {{認可の要点。例: 全 API route でセッション + ロール検証を行う}}
- {{個人情報の扱い。例: 実データをテスト fixture やログに入れない}}

## 関連ドキュメント

| ドキュメント | 内容 |
|---|---|
| {{docs/design/xxx.md}} | {{機能設計の正}} |
| {{docs/adr/}} | {{アーキテクチャ決定記録}} |
| {{docs/changelog/}} | {{変更履歴}} |

## 関連スキル / サブエージェント

<!-- .claude/skills/ を整備したら追記する。無ければセクションごと削除する -->

- {{skill 名}}: {{1 行の守備範囲}}
- {{例: バグの深掘りは bug-investigator サブエージェントを使う (Claude Code)}}
