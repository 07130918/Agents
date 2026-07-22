# UI リサーチ + リデザイン ワークフロー

任意のプロジェクトで UI を改善するための汎用手順。プロジェクト固有のトークン、コンポーネント、認証、テスト規約は各プロジェクトの frontend skill が担う。本 skill は、その上位で「何を調べ、どう比較し、何を作り、どう証明するか」を扱う。

## 目次

1. 不変原則
2. 現状と成功条件
3. UI リサーチの進め方
4. パターン抽出と証拠台帳
5. 操作モデルと visual direction
6. 設計契約と UI 種別ごとの観点
7. 実装への翻訳
8. 証拠付き検証とレビュー
9. アウトプット定型

---

## 1. 不変原則

1. 見た目ではなく、ユーザーが完了させたい仕事と KGI から始める。
2. 現行 UI、ルート、権限、状態、デザインシステムを調べてから外部事例を見る。
3. 現行バージョンの公式ドキュメント、公式ヘルプ、標準仕様を一次情報として優先する。
4. 製品の画面を模倣せず、観測した操作パターンを原則へ翻訳する。
5. 構造を変える場合は、見た目ではなく操作モデルが異なる案を比較する。
6. visual variant は仕事とブランドへの適合で選ぶ。新規性は同点時の判断材料に留める。
7. 実ブラウザで主要ユーザー、画面幅、状態、失敗経路まで証拠を残す。

UI リサーチの目的は、人気製品の見た目を集めることではない。ユーザーの仕事を阻害している構造を特定し、その障害を解いているパターンを探すこと。

---

## 2. 現状と成功条件

### 2-1. ユーザージョブと KGI

次を 1 文にする。

> `<ユーザー>` が `<起点>` から `<完了したい仕事>` までを、`<現在の障害>` なしに終えられる。

「モダン」「洗練」「かっこいい」は KGI ではない。可能なら次のいずれかを Before/After で置く。

- 完了までのステップ数、所要時間、再探索回数
- 入力エラー、誤操作、見落とし、問い合わせの発生率
- 読了率、回遊率、タスク完了率、継続率
- 初見ユーザーが主要操作を見つけられる割合

### 2-2. Research Brief

検索前に次を 1 ページ以内で埋める。

| 項目 | 問い |
|---|---|
| ユーザー | 誰が、どの頻度と習熟度で使うか |
| ユーザージョブ | 何を判断・入力・確認・完了したいか |
| 起点と完了 | どこから始まり、何が起きれば完了か |
| 現在の障害 | 探索、入力、理解、待機、誤操作のどこに負荷があるか |
| 主対象 | 行、フォーム、会話、数値、記事など何を扱うか |
| 情報量 | 件数、項目数、長文、更新頻度はどれくらいか |
| 操作 | 閲覧、検索、比較、編集、承認、返信など何をするか |
| 制約 | role、権限、desktop/mobile、時間、アクセシビリティ |
| KGI | ステップ数、完了時間、見落とし、誤操作など何を改善するか |

### 2-3. 現行契約マップ

コード、実画面、既存ドキュメントから次を調べる。スクリーンショットだけで推測しない。

| 契約 | 確認すること |
|---|---|
| 起点 | 一覧、検索、通知、ダッシュボード、ランディングなど |
| 到達先 | 詳細、Dialog、checkout、編集フォームなど |
| 主対象 | 読む、比較する、更新する中心オブジェクト |
| 既存操作 | link、button、menu、selection、drag など |
| ナビゲーション | 戻り先、filter、query、選択状態 |
| ユーザー | role/persona ごとの閲覧・操作可否 |
| API/データ | 表示可能な項目、認可、更新、副作用 |
| 状態 | loading/empty/error/success/disabled/permission denied |
| UI 基盤 | token、共通部品、breakpoint、icon、motion |
| 実利用 | device、頻度、情報量、入力環境、支援技術 |

### 2-4. UI ジャンルと変更レベル

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

## 3. UI リサーチの進め方

### 3-1. 調査問いを作る

問いは「ユーザー + 対象 + 仕事 + 制約 + 成功条件」で作る。

```text
❌ モダンなダッシュボードはどんな見た目か
✅ 更新頻度の高い項目から、担当者が要対応だけを短時間で特定するには、どの情報階層とfilterが有効か
```

### 3-2. 検索クエリを組み立てる

```text
[user job] + [surface] + [interaction] + [constraint] + [primary source modifier]
```

| 部品 | 例 |
|---|---|
| user job | triage, compare, review, approve, learn, recover |
| surface | data table, form, dashboard, timeline, detail page, onboarding |
| interaction | filtering, bulk action, validation, progressive disclosure, keyboard navigation |
| constraint | mobile, high density, novice user, role based, accessibility |
| primary source | official docs, help center, design system, accessibility guidelines |

クエリ例:

- `support inbox triage unread filtering official help`
- `long form validation error recovery design system`
- `dense data table bulk actions keyboard accessibility`
- `student progress dashboard hierarchy education platform`
- `mobile multi step form save progress official design system`

日本語と英語の両方を使うが、件数を増やすことを目的にしない。`modern`、`clean`、`cool` のような形容詞だけで検索しない。

### 3-3. 製品ではなく問題クラスから探す

| 問題クラス | 近い製品カテゴリ |
|---|---|
| 大量情報から優先対象を探す | CRM、issue tracker、support inbox |
| 複雑な入力を完了する | accounting、admin form、checkout、public service |
| 状態変化を時系列で追う | activity feed、conversation、audit log |
| 数値を監視し異常を見つける | analytics、observability、finance dashboard |
| 学習や継続を支える | LMS、habit tracker、education app |
| 対象を見ながら処理する | master-detail、review console、editor |

対象業界と同じ製品だけに限定しない。同じ認知課題、情報量、操作頻度を持つ別業界の方が参考として近い場合がある。

### 3-4. 情報源の優先順位

1. W3C、法令、公的デザインシステム
2. 対象製品の公式 design system、公式 help、公式 docs
3. 実製品を自分で操作した観測
4. 信頼できる専門家や調査機関の分析
5. gallery、まとめ記事、SNS

下位情報源は候補発見に使い、重要な設計判断は上位情報源で再確認する。公開情報から確認できない挙動は「未確認」または「推論」と明記する。

### 3-5. 調査量と停止条件

Lv3/Lv4 では原則 3 件以上の独立した一次情報を確認する。次を満たしたら収集から比較へ進む。

- 調査問いごとに 2〜3 個の異なる解法が見つかった。
- 少なくとも 1 件は標準仕様または公的デザインシステムで裏付けた。
- 採用候補だけでなく、不採用にすべき条件も説明できる。
- 新しい結果が既存パターンの繰り返しになった。

Lv1/Lv2 では、問いに直接答える標準または公式仕様 1 件と現行 UI の観測で足りる場合がある。

---

## 4. パターン抽出と証拠台帳

### 4-1. 証拠台帳

| 情報源 | 調査問い | 観測事実 | 推論した原則 | 適用条件 | 採否 |
|---|---|---|---|---|---|
| URL/実画面 | 何を知るためか | 直接確認できたこと | なぜ有効と考えるか | どの状況で成立するか | 採用/一部採用/不採用 |

観測事実には形容詞を使わず、配置、順序、表示条件、操作結果を記録する。

```text
❌ 操作が分かりやすい
✅ 行を選択した時だけ操作バーが表の上部に現れ、選択件数を表示する
```

### 4-2. 共通の分解軸

| 軸 | 確認内容 |
|---|---|
| 主対象 | 最初に認識させる情報は何か |
| 情報階層 | title、metadata、status、detail の順序 |
| 操作階層 | primary/secondary/tertiary action |
| 発見性 | 常時表示、文脈表示、menu のどれか |
| 開示 | inline、popover、Dialog、side panel、別ページのどれか |
| 状態 | loading、empty、error、success、disabled |
| feedback | 操作直後に何が、どこで、どれくらい表示されるか |
| 入力方式 | mouse、keyboard、touch、支援技術 |
| responsive | 小さい画面で何を残し、移動し、畳むか |
| 安全性 | role、確認、undo、競合、機密情報 |

### 4-3. 原則への翻訳

製品固有の実装を、そのまま要件にしない。

```text
観測: 選択時だけ画面下部に操作バーが現れる
原則: 低頻度の一括操作は、選択という文脈が生じるまで隠して通常時の密度を下げる
適用条件: 複数選択があり、操作対象件数を明示できる
不適用条件: 毎回必ず使う主要操作、またはmobileで選択状態が見失われる場合
```

転用しない要素:

- ブランド固有の色、illustration、motion
- product 固有の権限やデータ構造
- desktop 専用の hover 依存操作
- 実データ量と合わない情報密度
- 利用頻度の違いを無視した menu 配置

---

## 5. 操作モデルと visual direction

### 5-1. 操作モデルを比較する

Lv3/Lv4 では、色、角丸、余白だけを変えた案を 1 案として数えない。情報構造または操作の流れが異なる 3 案を作る。Lv1/Lv2 では現状維持案と改善案の比較で十分な場合がある。

| 例 | 案 A | 案 B | 案 C |
|---|---|---|---|
| 詳細の開示 | inline 展開 | side panel/Dialog | 独立ページ |
| 編集 | 一覧内編集 | 専用フォーム | step 分割 |
| 大量操作 | 行ごと | 選択後の action bar | 条件指定による一括処理 |
| dashboard | KPI 中心 | 要対応中心 | workflow 中心 |

評価軸:

- KGI への直接効果
- 初見の発見性と結果の予測可能性
- 情報量と操作頻度への適合
- 誤操作、破壊的操作、権限漏れのリスク
- keyboard、touch、支援技術
- desktop/mobile の一貫性
- 既存 product と design system への適合
- API、状態、テストを含む実装コスト

差が小さい場合は、既存 product との一貫性と最小差分を優先する。新規性だけを理由に複雑な案を選ばない。

### 5-2. Visual Variant Catalog

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

## 6. 設計契約と UI 種別ごとの観点

### 6-1. 設計契約

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
- ナビゲーション/戻り先:
- persona/role別の表示と認可:
- desktop/mobileの再配置:
- loading/empty/error/success/disabled:
- 一次情報から取り入れる原則:
- 採用しないproduct固有要素:
```

### 6-2. UI 種別ごとの調査観点

| UI 種別 | 主な問い |
|---|---|
| 一覧/テーブル | 走査、比較、filter、sort、pagination、bulk action、列の優先順位 |
| フォーム | 入力順、default、補足、validation、保存、離脱、再開 |
| ダッシュボード | 誰が何を判断するか、異常、比較期間、次の action |
| タイムライン | 時系列、未読、actor、grouping、filter、軽い反応、長文の開示 |
| 詳細ページ | 主対象、metadata、関連情報、主要 action、戻り先 |
| 検索 | query 支援、結果の順位、絞り込み、0 件、履歴 |
| オンボーディング | 初回だけ必要な説明、skip、進捗、成功体験 |
| 空状態 | なぜ空か、次にできること、権限や filter の影響 |
| mobile | 意味順、片手操作、keyboard、固定要素、overflow |

種別の名前だけで解法を固定しない。同じ table でも、閲覧中心と毎日更新する業務では必要な密度と操作が異なる。

### 6-3. アクションと視覚制約

- primary action は、その面の主要業務を完了する操作にする。
- 頻度、緊急度、可逆性に応じて常時表示と段階的開示を選ぶ。
- link は移動、button は command または状態変更に使う。
- disabled だけで理由を隠さず、必要なら補足または代替導線を示す。
- semantic token と共通 component を優先し、生の色や一回限りの component を増やさない。
- heading、body、metadata、status の階層を先に作り、装飾で穴埋めしない。
- Business SaaS で大きな hero、広すぎる余白、強い card motion を入れない。
- Consumer-facing で dashboard pattern だけを当て、brand の温度を消さない。
- card in card、意味のない gradient、頭文字 badge、均一な card grid の連続を避ける。

---

## 7. 実装への翻訳

### 7-1. 設計と実装を対応させる

| 設計決定 | 実装で確認すること |
|---|---|
| 情報階層 | DOM の意味順、heading、responsive 時の順序 |
| 操作階層 | native link/button、共通 component、focus order |
| feedback | 画面内表示、aria live/status、失敗時の復帰 |
| 開示 | focus management、Escape、戻る操作、状態保持 |
| responsive | breakpoint、overflow、touch target、固定要素 |
| role | UI 表示と API 認可の両方 |
| 状態 | loading/empty/error/success の component と test |

### 7-2. プロジェクト規約へ委譲する

1. プロジェクトの AGENTS.md/CLAUDE.md と frontend skill を読む。
2. 外部 component API に不確実性があれば現行の公式ドキュメントを確認する。
3. 既存 token、layout primitive、button、link、form、feedback component を再利用する。
4. native element の semantics と keyboard behavior を保つ。
5. 状態と権限を UI の条件分岐だけに閉じ込めない。
6. 変更範囲に対応する unit/integration test を追加する。
7. loading、empty、error、success を後付けにせず同時に実装する。

framework 固有の prop、Server/Client 境界、画像、motion の詳細はプロジェクト skill へ委譲する。本 skill に一時的な workaround を蓄積しない。

### 7-3. 自動検証

プロジェクトの標準コマンドを優先し、少なくとも次を確認する。

- format/lint
- type-check
- 関連 unit/integration test
- production build
- docs と実装契約の整合性

cache を疑う前にエラーログと import trace を読む。cache 削除は原因を隠す常用手順にしない。

---

## 8. 証拠付き検証とレビュー

### 8-1. 実ブラウザ検証

UI 変更は dev server を起動し、実際の操作で確認する。type-check と screenshot だけでは完了にしない。

| 軸 | 必須証拠 |
|---|---|
| persona/role | 主要ユーザー、権限外ユーザー、必要なら未認証 |
| viewport | 実運用 desktop、375px 前後の mobile、必要なら tablet |
| input | mouse、keyboard、touch 相当 |
| task | 起点から完了まで、戻る、再試行 |
| state | loading、empty、error、success、disabled、permission denied |
| feedback | focus、validation、submit、failure recovery |
| runtime | console error、network status/response、hydration、保存結果 |
| visual | overflow、target size、contrast、主要情報と操作の優先順位 |

スクリーンショットには viewport、persona/role、state、実行した task を紐付ける。手動確認できない項目は「未確認」と理由を明記し、成功扱いにしない。

### 8-2. セルフレビュー

- KGI と変更が直接つながっているか
- 一次情報の観測と自分の推論を混同していないか
- 不採用案の方が単純で安全ではないか
- nested interactive、権限漏れ、mobile 破綻がないか
- visual novelty のためだけの変更が混ざっていないか
- 関連 docs と実装が同期しているか

material な Business SaaS 変更では、現場担当と運用担当が同じ業務を完了できるか確認する。外部へ依頼や連絡を行う場合は、ユーザーの許可範囲に従う。

### 8-3. 失敗パターン

- 有名 product 名を並べただけで調査を終える
- screenshot の印象を観測事実として扱う
- 3 案が色、角丸、余白だけ異なる
- desktop screenshot だけで responsive 対応済みとする
- success path だけ実装して empty/error/permission を後回しにする
- hover でしか主要操作を発見できない
- card 全体の click と内部の button/link を競合させる
- visual novelty のために既存の学習コストを増やす
- project skill にある framework 固有ルールを重複記載する

---

## 9. アウトプット定型

```markdown
## リデザイン記録: <機能名> (YYYY-MM-DD)

### 成功条件
- ユーザージョブ:
- KGI/評価指標:
- UIジャンル/変更レベル:

### リサーチ
| 情報源 | 観測事実 | 抽出した原則 | 適用条件 |
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
- ✅ console/network/navigation/form feedback
- ⚠️ 未確認項目と理由:
```

## 関連スキル

- プロジェクト固有 frontend skill — token、共通 component、framework 規約
- `frontend-design` — visual direction と仕上げ
- `react-chakra-ui` — Chakra UI v3 の component API
- `chrome-devtools-mcp` — 実ブラウザ検証
- `figma-to-code` — Figma が正典の場合の実装
- `principle-of-programming-reviewer` — PR 前の構造レビュー
