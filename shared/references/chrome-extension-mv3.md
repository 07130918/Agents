# chrome-extension-mv3

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Chrome 拡張機能 (Manifest V3) 実装ガイド

Chrome Extension (Manifest V3) 共通の実装パターン・落とし穴・デバッグ手順をまとめる。プロジェクト固有設定はそれぞれの `AGENTS.md` を優先し、本スキルは横断的な知識を提供する。

## 基本原則

- ✅ Manifest V3 は **Service Worker** ベース。永続的な background page は廃止
- ✅ Web 標準コードはほぼそのまま動くが、**`eval` / 動的 `<script>` は CSP で禁止**
- ✅ 拡張内 React/TS は通常のフレームワークと同じ。Chrome API ラップは型 (`@types/chrome`) を使う
- ❌ `chrome.extension.*` (旧) ではなく `chrome.runtime.*` を使う
- ❌ `background.scripts` (V2) ではなく `background.service_worker` (V3)

## manifest.json 最小テンプレート

```json
{
  "manifest_version": 3,
  "name": "拡張名",
  "version": "1.0.0",
  "description": "説明",
  "action": {
    "default_popup": "popup.html",
    "default_icon": { "16": "icons/16.png", "48": "icons/48.png", "128": "icons/128.png" }
  },
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://*/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "permissions": ["storage", "activeTab", "scripting"],
  "host_permissions": ["https://*/*"],
  "web_accessible_resources": [
    { "resources": ["assets/*"], "matches": ["<all_urls>"] }
  ]
}
```

### 押さえるべき変更点 (V2 → V3)

| 項目 | V2 | V3 |
|------|----|-----|
| バックグラウンド | persistent page | Service Worker |
| API スタイル | callback のみ | Promise 対応 (callback も可) |
| host 権限 | `permissions` に混在 | `host_permissions` に分離 |
| 外部スクリプト | 任意 | 禁止 (`web_accessible_resources` で限定) |
| `chrome.browserAction` | あり | `chrome.action` に統合 |

## Service Worker ライフサイクル (最頻出バグ)

- ✅ **アイドル 30 秒で停止する。グローバル変数は揮発する**。state は `chrome.storage` に保存する
- ✅ 初期化は `chrome.runtime.onInstalled` / `chrome.runtime.onStartup` のリスナーに置く
- ✅ `setTimeout` / `setInterval` は SW 停止で消える。定期処理は `chrome.alarms` を使う
- ❌ トップレベルで `setInterval(...)` を書いて待ち続ける、というコードは動かない

```ts
// background.ts
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("periodicSync", { periodInMinutes: 5 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "periodicSync") {
    // 5分おきの処理
  }
});
```

## メッセージング (popup ↔ background ↔ content)

```ts
// 送信側 (popup または content)
const res = await chrome.runtime.sendMessage({ type: "GET_NOTES" });

// 受信側 (background)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "GET_NOTES") {
    chrome.storage.local.get("notes").then((data) => sendResponse(data.notes));
    return true; // ⚠️ 非同期 sendResponse には必ず true を返す
  }
});
```

**落とし穴**: `return true` を忘れると `sendResponse` が呼ばれる前にチャネルが閉じて `Unchecked runtime.lastError` 警告が出る。

タブ内コンテンツへの送信:

```ts
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
await chrome.tabs.sendMessage(tab.id!, { type: "HIGHLIGHT" });
```

## chrome.storage 使い分け

| API | 容量 | 用途 |
|-----|------|------|
| `chrome.storage.local` | 10 MB (`unlimitedStorage` 権限で実質無制限) | アプリ内データ |
| `chrome.storage.sync` | 100 KB (1アイテム 8 KB) | ユーザー設定の同期 |
| `chrome.storage.session` | 10 MB | SW 再起動でも保持、ブラウザ終了で消える |

```ts
// 必ず async/await で扱う (V3 は Promise 対応)
const { notes = [] } = await chrome.storage.local.get("notes");
await chrome.storage.local.set({ notes: [...notes, newNote] });
```

## content script から DOM 操作

`activeTab` + `scripting` 権限があれば、popup から動的に注入できる:

```ts
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
await chrome.scripting.executeScript({
  target: { tabId: tab.id! },
  func: (selector) => document.querySelector(selector)?.scrollIntoView(),
  args: ["#target"],
});
```

`func` は **シリアライズされて別プロセスで実行される**。クロージャは効かない、引数は `args` で渡す。

## CSP の制約

MV3 のデフォルト CSP は厳しい:
- ❌ `<script src="https://...">` (外部スクリプト読み込み)
- ❌ インライン `<script>...</script>`
- ❌ `eval()` / `new Function()`
- ✅ ローカルファイルの `<script src="./bundle.js">`

そのため React/Vue 等のテンプレートエンジン側で `eval` を使うものは要注意 (Vue runtime-only ビルドを選ぶなど)。

## ビルド構成

### Vite + React (推奨)

`@crxjs/vite-plugin` を使うと manifest を TS で書け、HMR が効く:

```ts
// vite.config.ts
import { defineConfig } from "vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json";

export default defineConfig({
  plugins: [crx({ manifest })],
});
```

### Create React App

CRA で popup を作る場合、`build/` をそのまま `chrome://extensions/` の「パッケージ化されていない拡張機能を読み込む」で指定する。`homepage: "."` を `package.json` に設定して相対パス化する必要がある。

## デバッグ手順

1. **再読み込み**: コード変更後は `chrome://extensions/` のリロードボタン (循環矢印アイコン)
2. **popup の DevTools**: 拡張アイコン右クリック → 「ポップアップを検証」
3. **background SW のログ**: `chrome://extensions/` → 拡張カードの「Service Worker」リンク → DevTools 起動
4. **content script のログ**: 通常のページ DevTools の Console に出る (Top コンテキスト)
5. **manifest 構文エラー**: `chrome://extensions/` カード上に赤いエラーが出る。**必ず最初にここを確認**

## チェックリスト (PR 前)

- [ ] `manifest.json` の `permissions` は本当に必要なものだけか (審査落ち防止)
- [ ] background SW がアイドル復帰後も動作するか (state を `chrome.storage` に置いたか)
- [ ] `sendMessage` のレスポンスが async なら `return true` したか
- [ ] `web_accessible_resources` が必要最小限の `matches` になっているか
- [ ] 拡張 ID は読み込み毎に変わるため、ハードコードされていないか
- [ ] 本番ビルドの zip 化前に source map を含めない設定にしたか

## 参考リンク

- [Chrome Extensions (公式)](https://developer.chrome.com/docs/extensions)
- [Manifest V3 移行ガイド](https://developer.chrome.com/docs/extensions/develop/migrate)
- [chrome-extensions-samples](https://github.com/GoogleChrome/chrome-extensions-samples)

## Claude Code 版

# Chrome 拡張機能 (Manifest V3) 実装ガイド

Chrome Extension (Manifest V3) 共通の実装パターン・落とし穴・デバッグ手順をまとめる。プロジェクト固有設定はそれぞれの `CLAUDE.md` を優先し、本スキルは横断的な知識を提供する。

## 基本原則

- ✅ Manifest V3 は **Service Worker** ベース。永続的な background page は廃止
- ✅ Web 標準コードはほぼそのまま動くが、**`eval` / 動的 `<script>` は CSP で禁止**
- ✅ 拡張内 React/TS は通常のフレームワークと同じ。Chrome API ラップは型 (`@types/chrome`) を使う
- ❌ `chrome.extension.*` (旧) ではなく `chrome.runtime.*` を使う
- ❌ `background.scripts` (V2) ではなく `background.service_worker` (V3)

## manifest.json 最小テンプレート

```json
{
  "manifest_version": 3,
  "name": "拡張名",
  "version": "1.0.0",
  "description": "説明",
  "action": {
    "default_popup": "popup.html",
    "default_icon": { "16": "icons/16.png", "48": "icons/48.png", "128": "icons/128.png" }
  },
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://*/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "permissions": ["storage", "activeTab", "scripting"],
  "host_permissions": ["https://*/*"],
  "web_accessible_resources": [
    { "resources": ["assets/*"], "matches": ["<all_urls>"] }
  ]
}
```

### 押さえるべき変更点 (V2 → V3)

| 項目 | V2 | V3 |
|------|----|-----|
| バックグラウンド | persistent page | Service Worker |
| API スタイル | callback のみ | Promise 対応 (callback も可) |
| host 権限 | `permissions` に混在 | `host_permissions` に分離 |
| 外部スクリプト | 任意 | 禁止 (`web_accessible_resources` で限定) |
| `chrome.browserAction` | あり | `chrome.action` に統合 |

## Service Worker ライフサイクル (最頻出バグ)

- ✅ **アイドル 30 秒で停止する。グローバル変数は揮発する**。state は `chrome.storage` に保存する
- ✅ 初期化は `chrome.runtime.onInstalled` / `chrome.runtime.onStartup` のリスナーに置く
- ✅ `setTimeout` / `setInterval` は SW 停止で消える。定期処理は `chrome.alarms` を使う
- ❌ トップレベルで `setInterval(...)` を書いて待ち続ける、というコードは動かない

```ts
// background.ts
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("periodicSync", { periodInMinutes: 5 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "periodicSync") {
    // 5分おきの処理
  }
});
```

## メッセージング (popup ↔ background ↔ content)

```ts
// 送信側 (popup または content)
const res = await chrome.runtime.sendMessage({ type: "GET_NOTES" });

// 受信側 (background)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "GET_NOTES") {
    chrome.storage.local.get("notes").then((data) => sendResponse(data.notes));
    return true; // ⚠️ 非同期 sendResponse には必ず true を返す
  }
});
```

**落とし穴**: `return true` を忘れると `sendResponse` が呼ばれる前にチャネルが閉じて `Unchecked runtime.lastError` 警告が出る。

タブ内コンテンツへの送信:

```ts
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
await chrome.tabs.sendMessage(tab.id!, { type: "HIGHLIGHT" });
```

## chrome.storage 使い分け

| API | 容量 | 用途 |
|-----|------|------|
| `chrome.storage.local` | 10 MB (`unlimitedStorage` 権限で実質無制限) | アプリ内データ |
| `chrome.storage.sync` | 100 KB (1アイテム 8 KB) | ユーザー設定の同期 |
| `chrome.storage.session` | 10 MB | SW 再起動でも保持、ブラウザ終了で消える |

```ts
// 必ず async/await で扱う (V3 は Promise 対応)
const { notes = [] } = await chrome.storage.local.get("notes");
await chrome.storage.local.set({ notes: [...notes, newNote] });
```

## content script から DOM 操作

`activeTab` + `scripting` 権限があれば、popup から動的に注入できる:

```ts
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
await chrome.scripting.executeScript({
  target: { tabId: tab.id! },
  func: (selector) => document.querySelector(selector)?.scrollIntoView(),
  args: ["#target"],
});
```

`func` は **シリアライズされて別プロセスで実行される**。クロージャは効かない、引数は `args` で渡す。

## CSP の制約

MV3 のデフォルト CSP は厳しい:
- ❌ `<script src="https://...">` (外部スクリプト読み込み)
- ❌ インライン `<script>...</script>`
- ❌ `eval()` / `new Function()`
- ✅ ローカルファイルの `<script src="./bundle.js">`

そのため React/Vue 等のテンプレートエンジン側で `eval` を使うものは要注意 (Vue runtime-only ビルドを選ぶなど)。

## ビルド構成

### Vite + React (推奨)

`@crxjs/vite-plugin` を使うと manifest を TS で書け、HMR が効く:

```ts
// vite.config.ts
import { defineConfig } from "vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json";

export default defineConfig({
  plugins: [crx({ manifest })],
});
```

### Create React App

CRA で popup を作る場合、`build/` をそのまま `chrome://extensions/` の「パッケージ化されていない拡張機能を読み込む」で指定する。`homepage: "."` を `package.json` に設定して相対パス化する必要がある。

## デバッグ手順

1. **再読み込み**: コード変更後は `chrome://extensions/` のリロードボタン (循環矢印アイコン)
2. **popup の DevTools**: 拡張アイコン右クリック → 「ポップアップを検証」
3. **background SW のログ**: `chrome://extensions/` → 拡張カードの「Service Worker」リンク → DevTools 起動
4. **content script のログ**: 通常のページ DevTools の Console に出る (Top コンテキスト)
5. **manifest 構文エラー**: `chrome://extensions/` カード上に赤いエラーが出る。**必ず最初にここを確認**

## チェックリスト (PR 前)

- [ ] `manifest.json` の `permissions` は本当に必要なものだけか (審査落ち防止)
- [ ] background SW がアイドル復帰後も動作するか (state を `chrome.storage` に置いたか)
- [ ] `sendMessage` のレスポンスが async なら `return true` したか
- [ ] `web_accessible_resources` が必要最小限の `matches` になっているか
- [ ] 拡張 ID は読み込み毎に変わるため、ハードコードされていないか
- [ ] 本番ビルドの zip 化前に source map を含めない設定にしたか

## 参考リンク

- [Chrome Extensions (公式)](https://developer.chrome.com/docs/extensions)
- [Manifest V3 移行ガイド](https://developer.chrome.com/docs/extensions/develop/migrate)
- [chrome-extensions-samples](https://github.com/GoogleChrome/chrome-extensions-samples)
