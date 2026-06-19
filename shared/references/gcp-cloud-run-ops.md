# gcp-cloud-run-ops

GCP Cloud Run、Cloud Build、Cloud SQL、Secret Manager、Artifact Registry、Terraform を使う開発/本番環境の調査と変更 workflow。

## 使う場面

- 「Cloud Run のログを見て」「GCP開発環境/本番環境に反映」「Cloud Build が失敗」「Secret を更新」と依頼されたとき。
- Cloud Run revision、環境変数、Secret Manager、Cloud SQL 接続、Cloud Build、Terraform、サービスアカウントが絡むとき。
- ローカルでは動くが GCP 環境だけ失敗する問題を調査するとき。

## 対象外

- localhost、Docker Compose、`.next` などローカル起動は `local-dev-ops` を使う。
- GitHub Actions の workflow 自体の失敗調査は `github-actions-ops` を併用する。
- DB schema 変更は `nextjs-drizzle-patterns` / `nextjs-prisma-patterns`、またはプロジェクト固有の migration skill を使う。

## 基本方針

- 読み取り調査を先に行い、変更操作は対象 project/service/revision/environment を明示してから行う。
- 本番環境の env、secret、traffic、DB、Terraform apply は、ユーザーの明示確認なしに変更しない。
- Secret の値は表示しない。存在、version、参照名、最終更新時刻だけを扱う。
- `gcloud config get-value project` と `gcloud auth list` で、実行先を必ず確認する。

## 入力

- 対象 GCP project ID、環境名、Cloud Run service 名。
- 問題の URL、revision、GitHub run、Cloud Build build ID。
- 期待する状態と現在の症状。

## 出力

- 対象環境と確認したリソース。
- 原因候補と証拠。
- 実施した変更、またはユーザー確認が必要な変更案。
- 動作確認結果。

## 調査手順

1. 対象を確定する。
   - project、region、service、environment、revision、commit SHA を分けて記録する。
   - `dev` と `prod` を同時に扱う場合は、表で比較する。
2. デプロイ経路を確認する。
   - GitHub Actions、Cloud Build、手動 `gcloud run deploy`、Terraform のどれかを特定する。
   - 直近の成功 revision と失敗 revision を比較する。
3. Cloud Run の状態を見る。
   - service describe、revision list、traffic split、env vars、secret refs、container image を確認する。
   - 環境変数は名前と参照先だけを扱い、秘密値は出さない。
4. ログを見る。
   - startup error、env validation、DB connection、Cloud SQL Auth Proxy、permission denied、timeout、memory limit を優先する。
   - リクエスト単位の失敗なら trace/request ID を探す。
5. 依存リソースを確認する。
   - Cloud SQL、Secret Manager、Artifact Registry、service account IAM、VPC connector、scheduler、pub/sub。
6. 変更する場合は、変更方法を選ぶ。
   - Terraform 管理なら Terraform を正とする。
   - 一時復旧の手動変更は、後でコード化する TODO を残す。
   - CI/CD 管理なら GitHub/Cloud Build の再実行を優先する。

## 変更前チェックリスト

- [ ] project ID と環境が正しい。
- [ ] service 名、region、revision が正しい。
- [ ] 本番変更ならユーザーが明示承認している。
- [ ] Secret 値を出力していない。
- [ ] Terraform 管理リソースを手動で恒久変更しようとしていない。
- [ ] rollback 方法がある。
- [ ] 変更後の確認 URL/API が決まっている。

## よくある原因

| 症状 | 優先して見る場所 |
|---|---|
| 起動失敗 | env validation、secret ref、container command、port |
| 本番だけ失敗 | Secret 未設定、Cloud SQL 接続、IAM、migration 未適用 |
| デプロイ失敗 | Cloud Build logs、Artifact Registry 権限、Docker build、Node version |
| 通知や cron が動かない | Cloud Scheduler、認証 header、service URL、service account |
| DB接続失敗 | Cloud SQL instance、private IP、connector、DB user、network |

## ドキュメント更新

Terraform、Cloud Build、GitHub Actions、Dockerfile、GCP リソース構成、外部サービス連携、認証、通知、定期実行を変更した場合は、プロジェクトの architecture docs 更新要否を確認する。

## 関連 skill

- `github-actions-ops`: GitHub Actions run の調査。
- `local-dev-ops`: ローカル環境での再現確認。
- `bug-investigation`: アプリケーション側の根本原因調査。
- `docs-code-consistency-audit`: docs と実構成の乖離監査。
