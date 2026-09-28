# Chrome DevTools MCP ワークフロー

この PC では、ブラウザ操作・UI検証・スクリーンショット取得はこの workflow に統一する。別のブラウザ自動化 runner を追加しない。

UIの変更完了を「コード上は正しい」ではなく「ブラウザで期待通り動く」まで検証するためのワークフロー。

## 基本原則

- ✅ UIやフロントエンドを変更したら、コミット前にブラウザで実動作確認する
- ✅ 型チェック・テスト通過はコードの正しさの証明であり、機能の正しさの証明ではない
- ❌ 「コンパイル通ったので完了」はUI変更では通用しない

## 診断情報は取得前に絞る

認証付き画面の診断では、ツールを呼ぶ前に対象と必要な項目を決め、本文だけでなく付随するURL・ヘッダー・自動snapshotの出力仕様を確認する。取得後に伏字へ変えても、先にツール出力へ載った値は取り消せない。

- 最初は対象DOMの有無、対象APIのHTTPステータス、既知のエラー分類を選ぶ。Cookie、token、Authorization、認証URLのquery/fragment、storageやconsoleの全文を一括取得しない。URLは認証値を含むpathにも注意し、既知のroute名で報告する。
- 初動の読取処理では、選んだboolean・数値・既知の分類だけを返す。DOM本文、エラーmessage/stack、レスポンス本文・ヘッダー、stateのobjectをそのまま返さない。原文が必要な場合は、付随出力も含め非秘密と事前確認した対象のmessage/stackやresponse本文など、仮説に必要な範囲へ限定する。
- `list_console_messages`のerror絞込み・件数制限は本文の除去ではない。`get_network_request`は認証ヘッダーを含み得る。`list_pages`やnetwork一覧、snapshotもURLを返し得る。対象を絞る機能と、出力項目を絞る機能を混同しない。
- native Chrome、アクセシビリティ(AX)取得、別のbrowser toolでも同じ順序を守る。初回のアプリ/タブ選択や操作が自動で返す画面情報も対象。コンソールや認証設定を開いて全画面のAX・画像を取得し、後から隠す方法は使わない。
- 呼出し自体で不要な値が出る、または出力範囲が不明なら、その経路は使わない。限定したDOM確認や既存の安全なテストへ切り替え、取得できない項目は未確認として記録する。必要な確認を省略して合格にせず、残りの許可済み確認は続ける。診断のために更新・送信APIを再実行しない。

例えば、対象画面のコードで確認したselectorへ置き換え、読取評価の戻り値を存在判定だけにする。要素の有無は画面状態の補助証拠であり、認可の成功を証明しない。

```javascript
() => ({
  accountMenuPresent: document.querySelector('[data-testid="account-menu"]') !== null,
  signInFormPresent: document.querySelector('[data-testid="sign-in-form"]') !== null,
})
```

専用の合成データで確認する場合も、戻り値に必要な情報が残り、URL・DOM本文・storageなどのダミー秘密値が出ないことを照合する。この手順はツール全体の秘密情報除去を機械保証するものではない。

## 標準検証フロー

### 1. ページ起動・ナビゲート
```
mcp__chrome-devtools__list_pages    # 既存タブ確認
mcp__chrome-devtools__new_page      # 新規タブ (or select_page で既存利用)
mcp__chrome-devtools__navigate_page # 対象URL へ遷移
```

### 2. 画面状態の取得
状態把握には `take_snapshot`(DOM構造), 視覚確認には `take_screenshot` を使い分ける。

- `take_snapshot`: 要素のuid を得てクリック・入力に使う (LLM的に効率的)
- `take_screenshot`: 視覚的なレイアウト崩れ・スタイル確認用

### 3. インタラクション
```
mcp__chrome-devtools__click         # ボタン・リンク
mcp__chrome-devtools__fill          # 単一入力
mcp__chrome-devtools__fill_form     # 複数フィールド一括 (推奨)
mcp__chrome-devtools__type_text     # キー入力シミュレート
mcp__chrome-devtools__press_key     # Enter/Tab等
mcp__chrome-devtools__hover         # ホバー状態
mcp__chrome-devtools__wait_for      # 非同期処理待ち (必須)
```

### 4. 検証
上の取得前確認を満たす手段を選ぶ。以下のconsole/network取得を全画面で必須実行するものではない。

```
mcp__chrome-devtools__list_console_messages  # 本文に秘密値が出ない対象でJSエラー確認
mcp__chrome-devtools__list_network_requests  # URLに秘密値が出ない対象でAPI確認
mcp__chrome-devtools__get_network_request    # ヘッダー・本文も非秘密と確認済みの場合のみ
mcp__chrome-devtools__evaluate_script        # 必要なDOM判定値だけを返す
```

## 頻出パターン

### パターン1: フォーム送信の検証
```
1. navigate_page → take_snapshot
2. fill_form で複数フィールド一括入力
3. click で送信ボタン
4. wait_for で成功表示 or リダイレクトを待つ
5. 対象APIのステータスと、受入条件に必要な保存値・状態変化を確認
6. 安全に取得できるエラー情報を確認し、取得できないものは未確認として残す
```

### パターン2: レスポンシブ確認
```
1. resize_page でモバイルサイズ (e.g. 375x667) に
2. take_screenshot
3. resize_page でタブレット (768x1024)
4. take_screenshot
5. resize_page でデスクトップ (1440x900)
```

### パターン3: エラー再現・デバッグ
```
1. navigate_page → エラー再現操作
2. 対象DOMの有無・対象APIのステータス・既知のエラー分類で切り分け
3. 仮説に追加情報が必要なら、非秘密項目だけ返せる取得手段を選ぶ
4. 必要な判定値を確認。原文が必要なら、付随出力も非秘密と事前確認した対象へ限定
```

## 注意点・落とし穴

### ⚠️ wait_for の使い忘れ
非同期処理 (API呼び出し, アニメーション) の直後に次の操作をすると、意図した状態になる前に click/snapshot が走る。
- `wait_for` で特定テキスト・要素の出現を待つのが確実

### ⚠️ take_snapshot の uid は同一スナップショット内でのみ有効
- スナップショット取得 → 何か操作 → 同じuid でもう一度操作 は NG
- 操作のたびに最新の snapshot を取り直す

### ⚠️ 複数タブを開いたまま
- テスト終了時に `close_page` で片付ける (タブが増え続けると select_page が煩雑になる)

### ⚠️ evaluate_script の副作用
- DOM を書き換えるスクリプトは後続テストに影響する
- 読み取り専用に留め、戻り値も必要な判定値へ絞る。読み取り専用でも秘密値を返す処理は使わない

## 検証完了の定義

UI変更タスクで「完了」と報告する前に、最低限以下を確認:

- [ ] ゴールデンパス(正常系)をブラウザで操作した
- [ ] 安全に取得した情報で関連エラーの有無を確認した。取得できない範囲は未確認として残した
- [ ] 関連APIの応答ステータスを安全に確認した。未取得を2xx扱いにしていない
- [ ] 受入条件に必要な保存前後の値や操作結果を照合した。2xxや件数だけで代用しない
- [ ] 関係するエッジケース(空入力・長い文字列・認証なし等)を1つ以上試した
- [ ] 該当しないタスクでは「テストできない・未確認」と明示した

ハーネスから呼ばれた場合、成功・失敗・未検証の結果と必要な証跡を[確認記録](review-harness-records.md)へ保存する。取得前に選別した結果だけを記録し、秘密情報・個人情報を残さない。記録形式はこの正本を使い、対象・確認結果・未解決事項を進行役へ返す。

## パフォーマンス計測

大きな機能変更・体感遅延が出ている場合は trace を検討する。URL等を含む出力・保存内容も上の取得前確認の対象とし、秘密情報を含まない合成データや専用環境を使う。

```
mcp__chrome-devtools__performance_start_trace
# 対象操作を実行
mcp__chrome-devtools__performance_stop_trace
mcp__chrome-devtools__performance_analyze_insight
```

ページ全体評価には `lighthouse_audit` も使える。
