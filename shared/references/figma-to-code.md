# Figma-to-Code ワークフロー

Figmaデザインを起点にフロントエンド実装を行うパターン集。単にピクセル通りにコピーするのではなく、既存デザインシステム(Chakra UI token, 既存コンポーネント)に合わせて実装するのが目的。

## 基本原則

- ✅ Figmaのhex値を直接使わず、token/theme値にマッピングする
- ✅ 既存コンポーネント(Button, Input, Dialog)があれば優先的に再利用する
- ✅ レスポンシブ対応(SP/PC)はFigmaに両方なくても自分で判断する
- ❌ Figmaのスタイルをinline styleで1:1書き写すのはアンチパターン

## 標準取得フロー

### 1. Figma URLからコンテキスト取得
Figma URL `https://www.figma.com/design/<fileKey>/...?node-id=<nodeId>` から:

```
mcp__figma__get_figma_data       # 基本情報 (fileKey 必須)
mcp__figma__get_design_context   # デザインコンテキスト (実装用)
mcp__figma__get_metadata         # メタデータ (軽量)
```

### 2. 視覚確認・画像取得
```
mcp__figma__get_screenshot       # 素早く全体把握
mcp__figma__download_figma_images # アイコン・画像アセット取得
```

### 3. デザインシステム連携
```
mcp__figma__search_design_system    # 既存コンポーネント検索
mcp__figma__get_context_for_code_connect  # code connect 設定取得
mcp__figma__create_design_system_rules    # デザイン→コードルール生成
```

## 実装パターン

### パターン1: 新規コンポーネント実装
```
1. get_screenshot でレイアウト全体把握
2. get_design_context で色・フォント・スペーシング取得
3. search_design_system で類似既存コンポーネント探す
4. 既存コンポーネントがあれば → 差分のみ実装
   なければ → Chakra UI の primitive (Box/Stack/Flex) で組む
5. download_figma_images でアイコン・画像のみ取得
```

### パターン2: Figma→Chakra UI token 変換

| Figma | Chakra UI v3 |
|---|---|
| `fill: #FFFFFF` | `bg="white"` or theme token `bg="bg.default"` |
| `fontSize: 16px` | `fontSize="md"` |
| `lineHeight: 24px` | `lineHeight="tall"` or `lineHeight="1.5"` |
| `padding: 16px 24px` | `py={4} px={6}` (4px基準) |
| `gap: 8px` | `gap={2}` |
| `borderRadius: 8px` | `borderRadius="md"` |
| `boxShadow: 0 2px 4px rgba(...)` | `boxShadow="sm"` |

### パターン3: レスポンシブ判断
Figmaに1画面だけの場合の方針:
- 横幅 > 768px のデザイン → PC 想定。`{base: ..., md: ...}` でSP時スタックに
- 横幅 < 500px のデザイン → SP 想定。PCはコンテナ最大幅を設定
- 既存プロジェクトの breakpoint (Chakra UI のデフォルト or 上書き設定) に従う

## 注意点・落とし穴

### ⚠️ fileKey と nodeId の抽出
URL: `https://www.figma.com/design/ABC123XYZ/ProjectName?node-id=12-345`
- fileKey = `ABC123XYZ`
- nodeId = `12:345` (`-` を `:` に置換が必要な場合あり)

### ⚠️ get_figma_data のレスポンス肥大化
大きなページを丸ごと取得するとトークン消費が激しい。
- 特定の node-id を指定して部分取得する
- `get_metadata` で構造把握 → 必要なnodeだけ深掘り

### ⚠️ アイコンは SVG 化して import
`download_figma_images` で取得したアイコンは:
- SVG なら `react-icons` 等と同様に ReactComponent として import
- PNG/JPG は `/public/` へ配置 → `next/image` の `<Image>` で表示

### ⚠️ デザインシステム違反を検出
Figma で token 外の色 (e.g. `#F3F4F5`) が使われていたら、デザイナーに確認するかまたは既存tokenで近似する。勝手にhex値をハードコードしない。

### ⚠️ Figma アクセス権
プライベートファイルへのアクセスは `mcp__figma__whoami` で認証状態確認。未認証なら Figma Desktop App を起動してログインを促す。

## 他スキルとの連携

- UI設計が自由度高い場合 → `frontend-design` スキルも併用 (AI美学を避けたクラフト設計)
- Chakra UI v3 特有の prop 変更対応 → `react-chakra-ui` スキル参照
- Next.js App Router での配置 → `nextjs-prisma-patterns` スキル参照

## 実装完了後の検証

- `chrome-devtools-mcp` スキルで `take_screenshot` → Figmaスクリーンショットと並べて差分確認
- Figmaの余白・サイズと実装のピクセル値が大きくズレていないか
