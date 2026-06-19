# local-dev-ops

ローカル開発環境の起動、停止、再起動、疎通確認、ポート競合、キャッシュ不整合を扱う workflow。

## 使う場面

- 「ローカル開発環境を起動して」「localhost を見たい」「ポートを教えて」と依頼されたとき。
- `docker compose`、`make dev`、`npm run dev`、`.next`、コンテナ、DB seed、ローカル疎通確認が絡むとき。
- 実装後にローカルで画面/APIを確認し、PR本文に動作確認を書く必要があるとき。

## 対象外

- Cloud Run、Cloud Build、GCP Secret、Terraform などクラウド環境の変更は `gcp-cloud-run-ops` を使う。
- DB schema 変更や migration 作成は `nextjs-drizzle-patterns` / `nextjs-prisma-patterns`、またはプロジェクト固有の migration skill を使う。
- UI 実装やブラウザ操作そのものは `chrome-devtools-mcp`、`frontend-design`、プロジェクト固有の frontend skill を併用する。

## 入力

- 作業ディレクトリ。
- ユーザーが触りたい画面/APIの URL またはパス。
- 既に起動中のサーバーやコンテナがあるか。
- 環境変数、DB、外部サービスが必要か。

## 出力

- 起動した URL とポート。
- 起動に使ったコマンド。
- 確認した画面/APIと結果。
- 残った問題、ログ、次に見るべき場所。

## 手順

1. 既存の起動手順を読む。
   - `Makefile`、`package.json`、`docker-compose.yml`、`README.md`、`AGENTS.md` を優先する。
   - プロジェクト固有の skill があれば先に読む。
2. 現在の状態を確認する。
   - `docker compose ps`
   - `lsof -i :<port>` またはプロジェクトの既定コマンド
   - 起動中セッションがユーザー作業か自分の作業かを区別する。
3. 起動コマンドを選ぶ。
   - Makefile があるなら Makefile を優先する。
   - 既存ポートが埋まっている場合は、ユーザーのプロセスを落とさず、別ポートか既存 URL の利用を検討する。
   - DB が必要な場合は app より先に DB/依存コンテナを起動する。
4. ログを確認する。
   - 起動直後の error、missing env、migration failure、port conflict、cache warning を見る。
   - Next.js で不可解な挙動がある場合は `.next` のキャッシュ不整合を候補に入れる。
5. 疎通確認を行う。
   - 画面は Browser/Chrome/Playwright で開く。
   - API は `curl` や既存テストで確認する。
   - ログインが必要なら、seed のテストアカウントやプロジェクト文書を確認する。
6. 終了や再起動を依頼された場合は、対象を絞る。
   - プロジェクトの compose project 名、container 名、port を確認する。
   - 無関係な Docker container や他プロジェクトの server を止めない。

## よくある切り分け

| 症状 | 最初に見るもの |
|---|---|
| 起動しない | env validation、port conflict、DB container、package install |
| 無限リロード | bind mount、Next.js cache、env watch、container clock、generated files |
| 画面が古い | `.next`、browser cache、service worker、SWR cache |
| APIだけ失敗 | Network response body、server log、DB seed、auth cookie |
| DBだけ失敗 | migration state、volume、seed、connection string |

## 停止条件

- 本番や共有環境へ影響する操作が必要になったら止めて確認する。
- ユーザーの既存プロセスを kill する必要がある場合は、対象 PID と理由を明示してから進める。
- 秘密値が不足している場合は、値を推測せず、欠落している環境変数名だけを報告する。

## 検証

- 起動 URL を開ける。
- 対象画面/APIで期待する status code または UI 状態を確認する。
- console error、server log、network failure の有無を確認する。
- PR 作成前なら、確認内容を PR 本文へ転記できる粒度で残す。

## 関連 skill

- `gcp-cloud-run-ops`: Cloud Run / GCP 側の調査と変更。
- `bug-investigation`: ローカルで再現した不具合の根本原因調査。
- `chrome-devtools-mcp`: ブラウザでの動作確認。
- `create-pr`: PR 本文の動作確認欄。
