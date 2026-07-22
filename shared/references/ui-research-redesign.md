# UI リサーチ + リデザイン ワークフロー

任意のプロジェクトで UI を改善するための汎用手順。プロジェクト固有のトークン、コンポーネント、認証、テスト規約は各プロジェクトの frontend skill が担う。本 skill は、その上位で「何を調べ、どう比較し、何を作り、どう証明するか」を扱う。

## 不変原則

1. 見た目ではなく、ユーザーが完了させたい仕事と KGI から始める。
2. 現行 UI、ルート、権限、状態、デザインシステムを調べてから外部事例を見る。
3. 現行バージョンの公式ドキュメント、公式ヘルプ、標準仕様を一次情報として優先する。
4. 製品の画面を模倣せず、観測した操作パターンを原則へ翻訳する。
5. 見た目だけでなく操作モデルが異なる 3 案を比較する。
6. visual variant は仕事とブランドへの適合で選ぶ。新規性は同点時の判断材料に留める。
7. 実ブラウザで主要ユーザー、画面幅、状態、失敗経路まで証拠を残す。

---

## Phase 0: 現状と成功条件を固定する

### 0-1. ユーザージョブと KGI

次を 1 文にする。

> `<ユーザー>` が `<起点>` から `<完了したい仕事>` までを、`<現在の障害>` なしに終えられる。

「モダン」「洗練」「かっこいい」は KGI ではない。可能なら次のいずれかを Before/After で置く。

- 完了までのステップ数、所要時間、再探索回数
- 入力エラー、誤操作、見落とし、問い合わせの発生率
- 読了率、回遊率、タスク完了率、継続率
- 初見ユーザーが主要操作を見つけられる割合

### 0-2. 現行契約マップ

コード、実画面、既存ドキュメントから次を調べる。UI のスクリーンショットだけで推測しない。

| 契約 | 確認すること |
|---|---|
| 起点 | 一覧、検索、通知、共有 URL、ランディングなど |
| 到達先 | 詳細、Dialog、checkout、編集フォームなど |
| 主対象 | 読む、比較する、更新する中心オブジェクト |
| 既存操作 | link、button、menu、Like、返信、drag など |
| URL | canonical URL、query、戻り先の文脈 |
| ユーザー | role/persona ごとの閲覧・操作可否 |
| API/データ | 表示可能な項目、認可、更新、副作用 |
| 状態 | loading/empty/error/success/disabled/permission denied |
| UI 基盤 | token、共通部品、breakpoint、icon、motion |
| 実利用 | device、頻度、情報量、入力環境、支援技術 |

### 0-3. UI ジャンルと変更レベル

| ジャンル | 主目的 | 基本語彙 |
|---|---|---|
| Consumer-facing | 発見、理解、回遊、CV | editorial、display、brand expression |
| Business SaaS | 状態把握、判断、入力、処理 | structured、dense、operational |
| Hybrid | 学習、行政、医療、コミュニティ | approachable + task oriented |

| レベル | 変更内容 |
|---|---|
| Lv1 | ラベル、補足、CTA コピー |
| Lv2 | 初期表示順、アクション順、軽い開示方法 |
| Lv3 | 情報階層、一覧と詳細、ナビゲーション |
| Lv4 | 新しい詳細面、業務コンソール、visual direction |

依頼の表現が Lv4 でも、KGI を Lv2 で達成できるなら小さい変更を提案する。判断が実装範囲を大きく変える時だけユーザーへ確認する。

---

## Phase 1: 一次情報から操作パターンを調査する

### 1-1. ユーザージョブを検索語へ変換する

`modern dashboard UI` だけで検索しない。対象の仕事、情報構造、操作、制約を組み合わせる。

```text
copy permalink to timeline item
conversation deep link inbox
activity feed card secondary actions
responsive master detail workflow
accessible clipboard status message
mobile table bulk actions
editorial long-form reading navigation
checkout error recovery pattern
```

日本語と英語の両方を使うが、件数を増やすことを目的にしない。一次情報へ到達できる製品名、component 名、`official docs`、`help center`、`design system` を加える。

### 1-2. 情報源の優先順位

1. 標準仕様、法令、公的デザインシステム
2. 対象製品の公式ドキュメント、公式ヘルプ、公式デザインシステム
3. 公式デモ、実製品を自分で操作した観測
4. 信頼できる専門家の分析
5. ギャラリー、まとめ記事、SNS

下位情報源は候補発見に使い、重要判断は可能な限り上位情報源で裏付ける。公開情報だけで画面挙動を確認できない場合は「推論」または「未確認」と明記する。

### 1-3. 証拠台帳

material な UI 改善では原則 3 件以上の独立した一次情報を確認する。小さな Lv1 変更では、関連する標準または公式仕様 1 件と現行 UI の観測で十分な場合がある。

| 一次情報 | ユーザージョブ | 観測事実 | 抽出した原則 | 今回の採否 |
|---|---|---|---|---|
| 公式 URL/実画面 | 何を完了するためか | 情報源が直接示すこと | 効く理由の推論 | 採用/一部採用/不採用と理由 |

製品名だけの列挙、スクリーンショットだけの収集、形容詞だけの要約をリサーチ完了としない。

### 1-4. パターン dossier

各事例を次の同じ軸で分解すると比較できる。

- 主対象と情報階層
- 起点から完了までのステップ
- primary/secondary/tertiary action
- 常時表示と段階的開示
- 成功、失敗、処理中のフィードバック
- mouse、keyboard、touch、支援技術
- desktop から mobile への再配置
- URL、認証、権限、機密情報
- product 固有で転用すべきでない要素

### 1-5. 一次情報の starting points

次は固定の模倣対象ではない。タスクに近い現行の一次情報へ差し替える。

| 公式情報 | 調べる時の観点 |
|---|---|
| [Slack: Forward messages](https://slack.com/help/articles/203274767-Forward-messages-in-Slack) | 項目単位の共有と元権限を維持したリンク |
| [Intercom: Conversations FAQs](https://www.intercom.com/help/en/articles/8838326-conversations-faqs) | 会話内の特定返信へ直接到達するリンク |
| [Intercom: Side conversations](https://www.intercom.com/help/en/articles/8398956-side-conversations) | 通知から対象スレッドへ戻る deep link |
| [Linear: Select issues](https://linear.app/docs/select-issues) | 高密度リストの選択とコンテキスト操作 |
| [デジタル庁: ボタン](https://design.digital.go.jp/dads/components/button/) | アクション階層とボタンの使い分け |
| [デジタル庁: ボタンのアクセシビリティ](https://design.digital.go.jp/dads/components/button/accessibility/) | 操作領域、disabled、ラベル |
| [W3C WAI: Link pattern](https://www.w3.org/WAI/ARIA/apg/patterns/link/) | native link の意味とキーボード操作 |
| [W3C: Status messages](https://www.w3.org/WAI/WCAG21/Techniques/failures/F103) | 動的な成功・失敗通知の知覚可能性 |

---

## Phase 2: 操作モデルを比較してから visual direction を選ぶ

### 2-1. 3 つの操作モデル

色、角丸、余白だけを変えた 3 案は比較にならない。情報構造または操作の流れが material に異なる案を作る。

例:

1. 一覧から独立した詳細ページへ移動する
2. 一覧と詳細を同時表示する master-detail にする
3. 一覧内で展開して完結させる

### 2-2. 評価表

| 評価軸 | 問い |
|---|---|
| KGI | 完了時間、手順、再探索を最も減らすか |
| 発見性 | 初見で操作を見つけ、結果を予測できるか |
| 情報階層 | 判断に必要な情報が適切な時に見えるか |
| 操作衝突 | nested interactive や誤タップを生まないか |
| 安全性 | 権限、機密情報、破壊的操作を守れるか |
| アクセシビリティ | semantics、focus、status、target size を守れるか |
| responsive | mobile で情報欠落や横スクロールを生まないか |
| 整合性 | 既存 product と design system に沿うか |
| 実装リスク | 状態、API、テストを含め最小の安全な差分か |

採用案と不採用理由を記録する。ユーザーが設計選択を求めている場合は 3 案を提示する。実装まで明示的に任され、合理的な推奨案がある場合は、判断と理由を記録して進めてよい。

### 2-3. Visual Variant Catalog

操作モデルが決まった後に視覚表現を選ぶ。

| Variant | 向く用途 | 主な特徴 |
|---|---|---|
| Quiet Editorial | 長文、記事、静かな閲読 | 大きめの余白、タイポ主体、画像は補助 |
| Bold Display | landing、hero、製品紹介 | 強い見出し、明確な対比、装飾を絞る |
| Hero Magazine | featured を持つ一覧 | 1 つの主役と複数の補助項目 |
| Kinetic Mosaic | gallery、creative brand | 非対称配置、強い motion、探索性 |
| Structured SaaS | dashboard、比較、管理 | 高密度、明確な group、状態表現 |
| Operational Console | 一覧 + 詳細、現場処理 | 低装飾、非均等 pane、情報と操作の近接 |
| Soft Playful | onboarding、consumer learning | 親しみ、柔らかい形、軽い motion |
| Education Friendly | 生徒、保護者、公共 | 明快、親しみ、過度に幼くしない |

選定ルール:

1. ユーザージョブと UI ジャンルへの適合を優先する。
2. 既存ブランドと design system の不変部分を守る。
3. 混合は主 variant と補助 variant の 2 種までにする。
4. 直前 PR と同じ variant でも、仕事に最適なら継続する。
5. 複数案が同等なら、product 全体の単調さを避ける方向を選ぶ。

---

## Phase 3: 設計契約を言語化する

```markdown
## 設計契約: <機能名>
- ユーザージョブ:
- KGI/評価指標:
- UIジャンル/変更レベル:
- 採用する操作モデル:
- 不採用案と理由:
- Visual variant:
- 主対象と情報階層:
- アクション階層:
- entry point/destination/canonical URL:
- persona/role別の表示と認可:
- desktop/mobileの再配置:
- loading/empty/error/success/disabled:
- 一次情報から取り入れる原則:
- 採用しないproduct固有要素:
```

### タイムライン、一覧/詳細、共有リンクの判断基準

| 面 | 主な責務 |
|---|---|
| 一覧/タイムライン | 走査、比較、軽い反応、対象を開く、共有する |
| 詳細 | 共有された対象の理解、長文確認、返信や更新の完了 |

- カード内に Like、返信、menu などがある場合、カード全体を link にしない。移動用の独立した native link を置く。
- 「詳細を開く」と「リンクをコピー」は別の仕事として別操作にする。
- 共有が主要ユースケースなら copy/share を常時表示し、稀なら overflow menu を検討する。
- 詳細から一覧へ戻れるようにし、filter/query の文脈を可能な範囲で保つ。
- canonical URL はリソースの identity から作り、現在地の偶発的な query/hash に依存させない。
- URL を知ることを権限として扱わず、到達先の API/server でも認可する。
- 権限外レスポンスや preview に機密情報を含めない。
- copy 成功は control の表示変化と programmatic な status で伝え、色だけに依存しない。
- desktop の master-detail は主内容を広く、補助操作を狭くする。mobile は意味順を保った縦積みにする。

### アクション階層

- primary: その面の主要業務を完了する操作。原則 1 つ。
- secondary: 詳細表示、共有など primary を支える操作。
- tertiary: 低頻度の補助操作。必要なら menu にまとめる。
- link は移動、button は command または状態変更に使う。
- disabled だけで理由を隠さず、必要なら補足または代替導線を示す。
- touch target は採用する design system とアクセシビリティ基準を満たす。

### 視覚制約

- semantic token と共通 component を優先し、生の色や一回限りの component を増やさない。
- heading、body、metadata、status の階層を先に作り、装飾で穴埋めしない。
- 形状、影、motion は意味のある少数の variant に絞る。
- Business SaaS で大きな hero、広すぎる余白、強い card motion を入れない。
- Consumer-facing で dashboard pattern だけを当て、brand の温度を消さない。
- card in card、意味のない gradient、頭文字 badge、均一な card grid の連続など、AI 生成 UI のクリシェを避ける。

---

## Phase 4: プロジェクト規約に落とし込んで実装する

1. プロジェクトの AGENTS.md/CLAUDE.md と frontend skill を読む。
2. 外部 component API に不確実性があれば現行の公式ドキュメントを確認する。
3. 既存 token、layout primitive、button、link、form、feedback component を再利用する。
4. native element の semantics と keyboard behavior を保つ。
5. 状態と権限を UI の条件分岐だけに閉じ込めない。
6. 変更範囲に対応する unit/integration test を追加する。
7. loading、empty、error、success を後付けにせず同時に実装する。

framework 固有の prop、Server/Client 境界、画像、motion の詳細はプロジェクト skill へ委譲する。本 skill に一時的な workaround を蓄積しない。

---

## Phase 5: 自動検証する

プロジェクトの標準コマンドを優先し、少なくとも次を確認する。

- format/lint
- type-check
- 関連 unit/integration test
- production build
- docs と実装契約の整合性

cache を疑う前にエラーログと import trace を読む。cache 削除は原因を隠す常用手順にしない。

---

## Phase 6: 実ブラウザで証拠を取る

UI 変更は dev server を起動し、実際の操作で確認する。type-check と screenshot だけでは完了にしない。

| 軸 | 必須証拠 |
|---|---|
| persona/role | 主要ユーザー、権限外ユーザー、未認証 |
| viewport | 実運用 desktop、375px 前後の mobile、必要なら tablet |
| input | mouse、keyboard、touch 相当 |
| state | loading、empty、error、success、disabled、permission denied |
| navigation | entry、destination、back、deep link、refresh |
| feedback | focus、validation、copy、submit、failure recovery |
| runtime | console error、network status/response、hydration |
| visual | overflow、target size、contrast、主要情報と操作の優先順位 |

### deep link/Clipboard の証拠

1. 一覧から対象を開き、destination URL を記録する。
2. コピーした URL を実際に貼り付け、canonical 値と一致するか確認する。
3. 新規タブ、refresh、未認証、権限外で同じ URL を開く。
4. success 表示が control と支援技術の両方で認識できるか確認する。
5. API response と画面に権限外の情報が含まれないか確認する。

スクリーンショットには viewport、persona/role、state、URL を紐付ける。手動確認できない項目は「未確認」と理由を明記し、成功扱いにしない。

---

## Phase 7: セルフレビューとフィードバック

PR 前にプロジェクト指定のレビューを行い、次を再確認する。

- KGI と変更が直接つながっているか
- 一次情報の観測と自分の推論を混同していないか
- 不採用案の方が単純で安全ではないか
- nested interactive、権限漏れ、mobile 破綻がないか
- visual novelty のためだけの変更が混ざっていないか
- 関連 docs と実装が同期しているか

material な Business SaaS 変更では、現場担当と運用担当が同じ業務を完了できるか確認する。外部へ依頼や連絡を行う場合は、ユーザーの許可範囲に従う。

---

## アウトプット定型

```markdown
## リデザイン記録: <機能名> (YYYY-MM-DD)

### 成功条件
- ユーザージョブ:
- KGI/評価指標:
- UIジャンル/変更レベル:

### リサーチ
| 一次情報 | 観測したパターン | 抽出した原則 | 実装への反映 |
|---|---|---|---|

### 選択
- 採用する操作モデル:
- 不採用案と理由:
- Visual variantと選定理由:

### 実装
- 主な変更:
- persona/role/APIへの影響:

### 検証証拠
- ✅ format/lint/type-check/test/build
- ✅ desktop/mobile/keyboard
- ✅ loading/empty/error/success
- ✅ 対象ユーザー/権限外ユーザー
- ✅ console/network/URL/Clipboard
- ⚠️ 未確認項目と理由:
```

## 関連スキル

- プロジェクト固有 frontend skill — token、共通 component、framework 規約
- `frontend-design` — visual direction と仕上げ
- `react-chakra-ui` — Chakra UI v3 の component API
- `chrome-devtools-mcp` — 実ブラウザ検証
- `figma-to-code` — Figma が正典の場合の実装
- `principle-of-programming-reviewer` — PR 前の構造レビュー
