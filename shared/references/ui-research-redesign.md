# UI リサーチ + リデザイン ワークフロー (グローバル汎用版)

任意プロジェクトで UI を刷新する際の再現性ある手順。プロジェクト固有のデザイントークン/コンポーネント規約は **各プロジェクトの frontend skill** (例: `uka-route-frontend`, `karte-frontend`) が担うため、本 skill はその上位レイヤとして「**何を**作るか / **どう調査・決定・検証**するか」に集中する。

## 4 つの不変原則

1. **1 パターンに固着しない**: 毎回 Visual Variant Catalog から **直前刷新と異なる variant** を意図的に選ぶ。同じ語彙の 3 PR 連続は危険信号
2. **プロジェクトの不変ルールに従う**: variant は変えてもトークン/コンポーネント規約は変えない。プロジェクトの frontend skill を必ず先に参照する
3. **UI ジャンルで語彙とリサーチ対象を切り替える**: コンシューマ向けと業務 SaaS では適する variant も参照サイトも逆方向。ジャンル誤認は最大の事故
4. **KGI を 1 つ定義してから手を動かす**: 「モダン」「洗練」は KGI ではない。ジャンルに応じて「読了率」「入力ステップ数」「タスク見落とし率」等の具体的指標に落とす

---

## UI ジャンル判定 (最優先)

着手前に対象機能をどのジャンルに置くかを決める。**ジャンルが違えば適する variant も避けるべきものも逆**になる。

| ジャンル | 主目的 | 主読者 | 適する語彙 |
|---|---|---|---|
| **Consumer-facing** | 閲覧・発見・興味喚起・回遊・CV | 不特定多数の一般ユーザ | エディトリアル / Bold Display / Magazine / Kinetic |
| **Business SaaS** | 業務遂行・データ入力・状態確認・意思決定 | 限定された業務担当者・現場 | Structured SaaS / Operational Console |
| **Hybrid** | 学習・教育・コミュニティ・行政・医療 | エンドユーザ + 運用者 | Soft Playful / Education Friendly + 業務 SaaS |

**逆方向の typical pitfall**:

- ❌ 業務 SaaS でエディトリアル風 (Medium / Smashing) を参考にする → 余白広すぎ・情報密度低すぎで業務効率を下げる
- ❌ Consumer-facing で業務 SaaS 風 (Linear / Vercel Dashboard) のみ参考 → 「無味乾燥」「ブランドが立たない」と評価される
- ❌ 教育・学習系で Bold Display 一辺倒 → 親しみが消えて離脱が増える

迷ったら User に「これは {コンシューマ向け / 業務 / 学習} のどれに近いですか」と問う。

---

## Visual Variant Catalog (デザイン語彙の引き出し)

毎回同じ variant に逃げないため、刷新ごとに意図的に異なるものを選ぶ。各 variant は適切なトークン設計があれば任意のフレームワーク (Chakra / Tailwind / Mantine / shadcn) で実現可能。

### Consumer-facing 向け

| Variant | 適する用途 | 視覚的特徴 | 参考サイト |
|---|---|---|---|
| **Quiet Editorial** | 詳細記事 / コラム / 静的閲読 | 大余白、Serif 寄せ、画像は脇役、L 字レイアウト | Medium / Stripe Blog / NYT Cooking / 暮しの手帖 |
| **Bold Display** | ランディング / Hero / 製品紹介 | 巨大タイポ (h1 6xl+)、強コントラスト、装飾最小 | Linear / Polestar / Apple / Anthropic |
| **Kinetic Mosaic** | ギャラリー / 受賞作品 / 驚き演出 | 非対称グリッド、回転カード、hover で zoom/translate | Awwwards SOTD / SiteInspire / Land-book |
| **Hero Magazine** | 一覧トップ / Featured + 残り | 1 大ヒーロー記事 + 等高 grid、タイポ駆動 | Smashing Magazine / The Verge / NYT Front |
| **Asymmetric Awwwards** | ブランド表現 / 強い印象 | 文字オーバーラップ、絶対配置、巨大画像 break out | Frank's Wines / Bevel / Awwwards SOTD |

### Business SaaS 向け

| Variant | 適する用途 | 視覚的特徴 | 参考サイト |
|---|---|---|---|
| **Structured SaaS** | 機能一覧 / ダッシュボード / 比較 | 等高カード grid、ピル/タグ多用、icon + label | Vercel / Notion / Linear / Stripe Dashboard |
| **Operational Console** | データ入力 / 一覧 + 詳細ペイン / 現場業務 | 高密度テーブル、左ナビ + 中央表 + 右詳細、低装飾 | Retool / Airtable / Asana / Salesforce Lightning / Intercom Inbox |

### Hybrid 向け

| Variant | 適する用途 | 視覚的特徴 | 参考サイト |
|---|---|---|---|
| **Soft Playful** | オンボーディング / 学習ツール / 入り口 | 角丸大、パステル、イラスト、軽い影 | Notion Onboarding / Pinkoi / 任天堂ストア / Duolingo |
| **Education Friendly** | 学校系 / 生徒向け / 保護者向け | 主要色 1-2、適度な丸み、親しみある icon、堅すぎない | Schoology / Google Classroom / ClassDojo |

### Variant の選び方

1. **ジャンル絞り込みを先に**: Consumer-facing なら Business SaaS variant は候補外。逆も然り
2. **直前 PR と必ず違う variant を選ぶ**: `git log --oneline -20` で最近の刷新を確認。同じ語彙が 3 PR 連続したらサイトが単調になる
3. **対象機能の温度感に合わせる**:
   - 検索フォーム / 機能一覧 → Structured SaaS
   - 詳細閲読 / コラム → Quiet Editorial
   - トップ Hero / ランディング → Bold Display
   - 学習 / 入り口 → Soft Playful
   - データ入力 / 業務一覧 → Operational Console
   - Featured 抜粋 / ギャラリー → Hero Magazine / Kinetic Mosaic
4. **混合は 2 種まで**: 「Bold Display ヒーロー + Structured SaaS 機能 grid」のように。3 種以上は不協和音

---

## Phase 0: 前提確認 + ジャンル/Variant 選定 (ultrathink)

variant 選定とリファレンス対比は「直前 PR と何を変えるか」「対象機能の温度感に何が適合するか」を多面的に比較する必要があるため、`ultrathink` で深く推論してから決定する。着手前に以下を明確化する。不明点は User に問う。

| 項目 | 確認内容 |
|---|---|
| ジャンル | Consumer-facing / Business SaaS / Hybrid のどれか |
| 対象機能 | ページ / コンポーネント (URL or ファイルパス) |
| KGI | このリデザインで改善したい指標は何か (1 つに絞る) |
| 痛点 | 情報密度 / ヒエラルキー / 装飾の古さ / 業務動線の遠さ etc. |
| Variant 仮決め | Visual Variant Catalog から 1〜2 個選び User に提示 |
| 強調レベル | Lv1〜Lv4 (下記) のどれか |
| 直前 PR との差別化 | `git log --oneline -20` で直前刷新の variant を確認 |
| 不変ルール | プロジェクトの frontend skill のトークン/規約を再確認 |

### 強調レベル定義

| レベル | 内容 | 工数感 |
|---|---|---|
| Lv1 | ラベル文言・CTA コピーの改善 | 数十分 |
| Lv2 | 初期表示順を業務動線/読み手動線に合わせる (並び替えのみ) | 数時間 |
| Lv3 | 構造並び替え (頻用機能を上に、補助機能を折りたたむ) | 半日〜1 日 |
| Lv4 | 専用サマリーセクションの新設 / variant 全面刷新 | 1〜数日 |

User の依頼が Lv4 のつもりでも、KGI 達成には Lv2 で足りることがある。先に Lv 提案 → 同意を取る。

---

## Phase 1: 国内 + 海外リファレンス調査 (WebSearch 並列)

**必ず日本語と英語の両方を投げる。** 文化圏で主流パターンが異なる。

### クエリ雛形 (Variant 連動)

選んだ variant に応じてクエリを変える:

```
# Bold Display 選択時
"modern landing hero bold typography 2026"
"巨大タイポ ヒーロー デザイン 2026"

# Quiet Editorial 選択時
"editorial blog detail page design 2026"
"エディトリアル ブログ詳細 余白 2026"

# Operational Console 選択時
"business saas dashboard high density table 2026"
"業務 SaaS ダッシュボード 情報密度 2026"

# Education Friendly 選択時
"education saas student dashboard friendly 2026"
"学校 SaaS 生徒画面 親しみやすさ 2026"
```

### 並列実行のコツ

- **1 メッセージ内で日英クエリを同時 WebSearch** (token 効率)
- **トレンドだけでなく具体的な会社/サイト事例を含める** ("Linear dashboard navigation 2026" 等)
- **年号固定**: 現在年 (例: 2026) をクエリに入れて古い記事を弾く
- **Source 記録**: 最終回答で参照 URL を markdown リンクで列挙

### ジャンル別調査チェックポイント

**Consumer-facing**:
- ヒーローのタイポ強度 / グラデ / 画像扱い
- カードの情報密度・装飾の古さ
- スクロール演出 / 視覚アクセント

**Business SaaS**:
- テーブル/リストの情報密度
- ステータスバッジ・ラベルの色使い
- フォームの入力補助 (インライン補足、エラー表示位置)
- 空状態 (データなし) のデザイン
- モバイル対応の有無と方針

---

## Phase 2: 設計方針の言語化 (3 案並列・ultrathink)

**1 案だけ提示すると User に「決まり」と読まれて固着する。必ず 3 案出して選んでもらう。** 各案の整合性 (プロジェクト token / 直前 PR との差別化 / 対象機能の温度感) を多面的に検討する必要があるため、`ultrathink` で深く推論してから案を出す。

### 雛形

```
## 設計方針 3 案

### 案 A (Bold Display): タイポ駆動ヒーロー
海外参考: Linear / Polestar / Anthropic
国内参考: スマートニュース / note 編集部
プロジェクト整合: brand.primary + heroAccent 文字グラデ
KGI 寄与: 第一印象の強化、滞在時間延伸

### 案 B (Hero Magazine): Featured + 等高 grid
海外参考: Smashing Magazine / NYT Front
国内参考: Web 幹事 / 暮しの手帖
プロジェクト整合: SectionCard を Featured 大カードと grid で同時利用
KGI 寄与: 回遊率向上、二記事目クリック率

### 案 C (Quiet Editorial): タイポ + 余白 + L 字
海外参考: Medium / Stripe Blog
国内参考: 暮しの手帖 / note エディトリアル
プロジェクト整合: bg.page 多用、画像はサムネ右配置
KGI 寄与: 読了率向上、滞在時間延伸
```

User に「どれにしますか」と問い 1 つ確定。決まらないなら 2 種混合 (例: "Bold Display ヒーロー + Structured SaaS 機能 grid")。

---

## Phase 2.5: 情報設計の制約ルール (variant 横断)

variant が変わっても以下は守る。サイト全体の調和を保つ。

### 形状は 2 種まで

1 画面内で使う角丸バリアントは 2 種類まで (例: `rounded="md"` + `rounded="full"`)。3 種以上は無秩序。

### 色は 4 カテゴリに限定

| カテゴリ | 用途 | 例 |
|---|---|---|
| ブランド | 主要 CTA、リンク、選択状態 | `brand.primary`, `brand.light` |
| 本文 | テキスト | `gray.800`, `gray.600` |
| 補助 | muted テキスト、ラベル、ボーダー | `gray.500`, `gray.400` |
| 例外 | 状態・成績・警告 (意味のある色) | `status.success`, `grade.a` |

例外色を使う場合は **必ずプロジェクトのトークンファイル** (例: `src/lib/system.ts`, `theme.ts`) に **セマンティックトークンとして登録してから使う**。色を直接 `#RRGGBB` で書かない。

### フォント階層は 4 段階

1. ページタイトル (Heading lg / h1)
2. セクションタイトル (Heading md / h2)
3. 本文・テーブル (`fontSize="sm"` 〜 `md"`)
4. 補足・メモ (`fontSize="xs"`)

### AI クリシェ禁則 (variant 横断・即「ダサい」と言われる)

- ❌ カード左辺だけの 4px 色 border (`borderLeft="4px solid brand.100"`)
- ❌ タイトル頭文字を `bg="brand.100"` の塗り circle に白文字で表示する「頭文字バッジ」
- ❌ カードが「タイトル + chevron」のみで情報密度が極端に低い
- ❌ 完全等高 grid だけで終わる単調レイアウト (`Hero Magazine` で Featured を必ず作る等の対比が要る)
- ❌ 検索フォームの Autocomplete を `flex={1}` `maxW="640px"` 等で意味なく長く伸ばす
- ❌ 4 カラム均等分割グリッド (データ少ない時に間延びする)。`1fr / 2fr+1fr / 3fr` 等の非均等を活用

### Business SaaS で特に避けるべきもの

- ❌ 過度な装飾 (グラデ多用・大きなヒーローバナー) → KGI を下げる
- ❌ データ密度を下げる「余白広いカード」
- ❌ 業務動線を遮るアニメーション
- ❌ マーケ的な CTA 強調 (「今すぐ申し込む」等の大型ボタン)
- ❌ エディトリアル風の雑誌連番見出し・Pull Quote

---

## Phase 3: 実装

### 3.1 プロジェクト固有 skill 参照 (必須)

実装前に **プロジェクトの frontend skill** (例: `uka-route-frontend`, `karte-frontend`) を必ず読み、不変ルール (デザイントークン / CTA カラー / Skeleton / ショートハンド / レイアウト基準) に完全準拠する。本 skill では variant に応じた **変奏可能領域** (レイアウト / 装飾 / タイポ強度 / ホバー演出) のみ意図的に変える。

### 3.2 Chakra UI v3 リデザイン固有の罠

基本的な v2 → v3 prop 変更 (`isDisabled` → `disabled`, `colorScheme` → `colorPalette`, `Stack spacing` → `gap` 等) は **`~/.claude/skills/react-chakra-ui`** を参照。

リデザインで頻発する追加の罠:

| 症状 | 回避策 |
|------|--------|
| `<Box asChild><a>{条件レンダリング}</a></Box>` が `React.Children.only` で実行時クラッシュ | `asChild` を使わず `<Box as="a" {...{ href } as any}>` を `AnchorBox` として共通化 |
| `chakra("a")` を Server Component で呼ぶとエラー | Server Component では `AnchorBox` (`Box as="a"` + spread) を使う |
| `<HStack asChild>` でも Children.only に引っかかる | Stack 自体を `as="a"` しない。リンクは `AnchorBox`、中身に HStack |
| `bgGradient="linear(to-br, ...)"` の v2 構文が効かない | プロジェクトのトークンファイルに `gradients` を登録 → `bgGradient="tokenName"` |
| `<Text as="time" dateTime="...">` 型エラー | 素の `<time dateTime="...">` を使う |
| Server Component で `<Box as={LuChevronRight} boxSize={4} />` がランタイムクラッシュ ("Functions cannot be passed directly to Client Components") | `<Box color="..."><LuChevronRight size={16} /></Box>` のように直接 JSX レンダー、または当該コンポーネントを `"use client"` 化 |
| `role="group"` を付けると biome `lint/a11y/useSemanticElements` で警告 | 子要素に `className="card-shell"` 等を付け、親 `_hover` で `& .card-shell` セレクタ経由制御 |
| Hero 外側 Box に `px` を持たせると後続セクションの `px` と二重で効いて PC で左端がズレる | 外側 Box は `bg` のみ、内側 Stack で `maxW + mx="auto" + px={{ base: 5, md: 10 }}` を統一 |
| Tab 内コンテンツで `maxW="95vw"` 等のビューポート単位を使うと Hero と兄弟セクションで左端整列が崩れる | `maxW="container.lg"` + `px={{ base: 5, md: 10 }}` で全タブを揃える |

### 3.3 ホバー / モーション (Variant 別)

`_hover` の強度は variant に揃える。ジャンルが Business SaaS なら強い変位は基本入れない。

| Variant | ホバー演出 |
|---|---|
| Quiet Editorial | `_hover={{ opacity: 0.85 }}` のみ。動かさない |
| Bold Display | `transform: translateY(-2px)` + `boxShadow: cardHover` |
| Kinetic Mosaic | `transform: rotate(0deg) translateY(-4px) scale(1.02)` + zIndex 上げ |
| Soft Playful | `transform: scale(1.03)` + 角丸変化 (lg → 2xl) |
| Structured SaaS | `borderColor: brand.100` のみ変化 |
| Operational Console | hover では何も動かさない (focus-visible のみ) |
| Hero Magazine | image scale 1.1 + title underline |
| Asymmetric | translateX + 子要素のずれ強調 |
| Education Friendly | 軽い scale + 主要色 fill 化 |

イージング指針:

- 静か: `ease`
- リフト: `cubic-bezier(0.16, 1, 0.3, 1)` (overshoot 風)
- 跳ねる: `cubic-bezier(0.34, 1.56, 0.64, 1)` (Soft Playful)
- 業務 UI: そもそも transition を最小限に

### 3.4 画像 (next/image) の扱い

- `fill` を使う場合も `object-fit: cover` はデフォルトでないため、`style={{ objectFit: "cover" }}` で明示
- `next/image` には `sizes` 属性を必ず設定: `sizes="(max-width: 768px) 100vw, 50vw"`。`fill` 時は必須
- ヒーロー全面背景は主張が強すぎがち。Quiet Editorial なら **左タイトル / 右 320px 前後のサムネ** のサイドカード配置が落ち着く
- Bold Display なら画像なしでタイポのみ、または上下に巨大画像 break out

### 3.5 レイアウト・パターン雛形 (Variant 別)

```tsx
// Hero Magazine: Featured + Grid
const featured = items[0];
const rest = items.slice(1);
// → Featured を SectionCard で大きく、下に 3 列 grid

// Quiet Editorial: 単一カラム
// → SectionCard を縦に並べる、画像はサムネ右配置、余白多め

// Asymmetric / Kinetic: 絶対配置 + rotate
// → data 駆動で card.align (left/right) を制御

// Structured SaaS: 等高 grid + ピル
// → SimpleGrid columns={{ base: 2, md: 3 }} + cardVariants で featured / default

// Operational Console: 左ナビ + 中央表 + 右詳細
// → Grid templateColumns="220px 1fr 360px" のレイアウトで作り込む
```

**既存実装が同じ variant を使っていれば新規ページは別 variant に振る**。例: Home が Hero Magazine 系なら Blog 一覧は Quiet Editorial にして対比させる。

---

## Phase 4: 品質担保

プロジェクトの CI コマンドを通す。エラーが出たら次に進まない。

```bash
# プロジェクトに応じて
make ci                    # 一括
npm run check              # lint + format
npm run type-check         # 型
npm run test               # 単体
npm run build              # ビルド検証
```

**Turbopack / Vite の stale エラー対処**:

ファイル rename 後の `Could not parse module '.../xxx.tsx', file not found` 等はビルドキャッシュ不整合。

1. ブラウザを ignore-cache でリロード
2. 治らなければ該当ファイルを `touch` で HMR 再トリガ
3. Docker 利用時は `docker logs <container> --tail 30` でサーバ側の実エラーを確認
4. 最終手段: `.next` / `node_modules/.vite` 削除 + 再起動

---

## Phase 5: ブラウザ検証

**`~/.claude/skills/chrome-devtools-mcp` のワークフローに従う**。本 skill 固有の確認:

| 観点 | 確認内容 |
|---|---|
| デスクトップ | lg ブレークポイント以上 (サイドバー有り状態) |
| モバイル | base ブレークポイント、375〜430px 幅 (`resize_page { width: 390, height: 844 }`) |
| ホバー演出 | `take_snapshot` で uid → `hover { uid }` → 再スクショ |
| フォーカス | Tab キーで巡回、focus-visible が出るか |
| TOC/アンカー | `href="#xxx"` と `<h2 id="xxx">` が一致、`scrollMarginTop` でヘッダーに隠れないか |
| コンソールエラー | 赤いエラーが出ていないか (`list_console_messages`) |
| ネットワーク | API レスポンスが期待通りか (`list_network_requests`) |

UI 変更の場合 **dev server を立ち上げてブラウザで実際に触る** こと。type-check / test がパスしてもデザインが正しい証明にはならない。

---

## Phase 6: 状態間の整合性 + Variant 連続化チェック

同じ画面が取りうる全状態で見た目が一貫しているかチェック:

| 状態 | 確認内容 |
|---|---|
| ローディング | Skeleton が適切に表示されるか |
| エラー | エラー UI が日本語で表示されるか |
| 空状態 | データなし時の表示はあるか (空であることが伝わるか) |
| ロール別 | 管理者/一般/ゲスト等で表示差異が正しいか |
| フォームエラー | バリデーションメッセージが日本語で出るか |
| 保存中 | ボタンが `loading` になっているか |
| ページ送り後 | フィルタ適用 / 1 ページ目との見た目差異がないか |
| モバイル↔PC | レイアウト・タッチターゲットが破綻しないか |

**カード in カード禁則**: 外枠が白カード (border + shadow) なら、内側の TOC / 引用は `bg.page` 等の淡いタイルに抑える。二重白カードは即「見辛い」フィードバックになる。

**Variant 連続化チェック**:

- 直前 PR で使った variant と本 PR の variant が **異なる** か `git log --oneline -20` で確認
- 同じ variant が 3 PR 連続したら危険信号。次回別 variant に振る計画をメモに残す

---

## Phase 7: レビュー

CLAUDE.md の規約に従い `/codex-review` → `/popr` の順で実行する。

レビューの観点別の主担当:

- `/codex-review` — バグ・セキュリティ・ベストプラクティス・a11y (フォーカス可視性)。`sanitize-html` 系は `allowedAttributes` と `transformTags` の整合性 (rel 属性落ちによる逆タブナビング等) を見てくれる
- `/popr` — 構造・責務分離・可読性 (Principle of Programming)

---

## Phase 8: ステークホルダーフィードバック (任意・Business SaaS で重要)

業務 SaaS のリデザインでは現場ユーザのフィードバックを反映する手順を組む。

### フィードバック収集の観点

- **現場担当**: 入力ステップが減ったか、よく使う機能に素早くアクセスできるか
- **管理者**: 運用画面の操作が分かりやすいか
- **エンドユーザ**: 主要動線で迷わないか

### フィードバックの反映原則

- Lv1〜Lv2 (文言・順序変更) は即対応
- Lv3〜Lv4 (構造変更) は設計を再確認してから対応
- 「Lv1 で済む案を Lv4 で実装する」のは過剰修正なので戻す

---

## アウトプット定型

```markdown
## リデザイン記録: <ページ名> (YYYY-MM-DD)

### ジャンル / Variant
- ジャンル: Consumer-facing / Business SaaS / Hybrid
- 選択 Variant: {名前} (例: Quiet Editorial)
- 強調レベル: Lv1 / Lv2 / Lv3 / Lv4
- 直前刷新との差別化: 直前 PR は {variant 名}、本 PR は {variant 名} で意図的に変奏

### KGI
- 改善したい指標: {1 つ}

### 設計方針 (Phase 2 の確定案)
- {採用案の概要}

### 主な変更点
1. {コンポーネント1} の刷新内容
2. {コンポーネント2} の刷新内容

### 実装ファイル
- `src/...`

### 品質チェック
- ✅ type-check / lint / format / test 全パス
- ✅ ブラウザ検証 (デスクトップ/モバイル)
- ✅ ランタイムエラー / コンソール警告なし

### Sources (国内/海外デザイン参考)
- [タイトル](URL)
- [タイトル](URL)
```

---

## 関連スキル

- **プロジェクト固有 frontend skill** (例: `uka-route-frontend`, `karte-frontend`) — 不変ルール / トークン / 共通コンポーネント (必読)
- `~/.claude/skills/react-chakra-ui` — Chakra v3 prop バグ・v2→v3 移行表の正典
- `~/.claude/skills/frontend-design` — 高品質 UI の創造的美学 (variant 探索時の発想源)
- `~/.claude/skills/figma-to-code` — Figma デザインから実装への変換
- `~/.claude/skills/chrome-devtools-mcp` — ブラウザ検証の詳細ワークフロー
- `~/.claude/skills/nextjs-prisma-patterns` — App Router / Server Component の境界
- `~/.claude/skills/prompt-engineering` — variant 比較 / 3 案並列で User に問う際の言い回し設計
