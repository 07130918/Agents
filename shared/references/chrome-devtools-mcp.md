# Chrome DevTools MCP ワークフロー

UIの変更完了を「コード上は正しい」ではなく「ブラウザで期待通り動く」まで検証するためのワークフロー。

## 基本原則

- ✅ UIやフロントエンドを変更したら、コミット前にブラウザで実動作確認する
- ✅ 型チェック・テスト通過はコードの正しさの証明であり、機能の正しさの証明ではない
- ❌ 「コンパイル通ったので完了」はUI変更では通用しない

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
```
mcp__chrome-devtools__list_console_messages  # JSエラー検出
mcp__chrome-devtools__list_network_requests  # API呼び出し確認
mcp__chrome-devtools__get_network_request    # 特定リクエスト詳細
mcp__chrome-devtools__evaluate_script        # DOM状態のassert
```

## 頻出パターン

### パターン1: フォーム送信の検証
```
1. navigate_page → take_snapshot
2. fill_form で複数フィールド一括入力
3. click で送信ボタン
4. wait_for で成功表示 or リダイレクトを待つ
5. list_network_requests で API 呼び出しを確認
6. list_console_messages でエラーがないか確認
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
2. list_console_messages で stack trace 取得
3. get_network_request で失敗したAPIレスポンス確認
4. evaluate_script で state/localStorage 状態を取得
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
- 読み取り専用(`document.querySelector(...).textContent` など) に留める

## 検証完了の定義

UI変更タスクで「完了」と報告する前に、最低限以下を確認:

- [ ] ゴールデンパス(正常系)をブラウザで操作した
- [ ] `list_console_messages` でエラー出ていない
- [ ] 関連APIが `list_network_requests` で 2xx 応答
- [ ] 関係するエッジケース(空入力・長い文字列・認証なし等)を1つ以上試した
- [ ] 該当しないタスクでは「テストできない・未確認」と明示した

## パフォーマンス計測

大きな機能変更・体感遅延が出ている場合は trace を取る。

```
mcp__chrome-devtools__performance_start_trace
# 対象操作を実行
mcp__chrome-devtools__performance_stop_trace
mcp__chrome-devtools__performance_analyze_insight
```

ページ全体評価には `lighthouse_audit` も使える。
