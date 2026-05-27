# Interface Design — "Design It Twice"

`software-architecture/SKILL.md` のアーキテクチャ改善ワークフローから、deepened module の interface 候補を**3 案以上並列で**出すための手順。`reference-language.md` の語彙を前提とする。

参考: Matt Pocock "improve-codebase-architecture/INTERFACE-DESIGN.md" を日本語化。原典は John Ousterhout "Design It Twice" — **最初に思いついた interface は最良ではない**。

---

## 手順

### 1. 問題空間を framing する

サブエージェントを spawn する前に、ユーザに見せる「問題空間の説明」を書く:

- 新しい interface が満たすべき制約
- 依存とそのカテゴリ (`reference-deepening.md` の 4 カテゴリ)
- 制約を具体化するためのラフなコードスケッチ — これは提案ではなく**制約を見えるようにするだけ**

ユーザに見せたら、即座に Step 2 へ進む。**ユーザは読み・考えている間にサブエージェントが並列で働く**。

### 2. サブエージェントを並列 spawn

`Agent` ツールで **3 つ以上**のサブエージェントを並列起動。それぞれに**根本的に異なる** interface を設計させる。

各サブエージェントには別個の技術ブリーフを渡す (ファイルパス、結合の詳細、`reference-deepening.md` の依存カテゴリ、seam の裏に何が入るか)。ブリーフは Step 1 のユーザ向け説明とは独立。各エージェントには**異なる設計制約**を与える:

- **Agent 1**: 「interface を最小化せよ — エントリーポイント 1-3 個まで。エントリーポイントあたりの leverage を最大化せよ」
- **Agent 2**: 「柔軟性を最大化せよ — 多様なユースケースと拡張をサポートせよ」
- **Agent 3**: 「最頻 caller を最適化せよ — デフォルトケースを trivial にせよ」
- **Agent 4 (依存があれば)**: 「seam をまたぐ依存に対して Ports & Adapters で設計せよ」

ブリーフには `reference-language.md` 語彙と `CONTEXT.md` 語彙の両方を含める (各エージェントがアーキテクチャ語彙とドメイン語彙の両方で名前を一貫させるため)。

各サブエージェントの出力:

1. **Interface** (型・メソッド・パラメータ — 加えて不変条件・順序制約・エラーモード)
2. **使用例** (caller がどう使うか)
3. **seam の裏に何を隠すか** (implementation の説明)
4. **依存戦略と adapter** (`reference-deepening.md` 参照)
5. **トレードオフ** — leverage が高い場所、薄い場所

### 3. 提示と比較

設計案を順番に提示する (ユーザが各案を吸収できるように)。その後、散文で比較する:

- **Depth** (interface での leverage)
- **Locality** (変更が集中する場所)
- **Seam placement** (seam をどこに置いたか)

最後に**自分の推薦**を提示する。最強の案はどれか・なぜか。要素を組み合わせる hybrid が良いなら hybrid を提案する。**強く意見を述べる**。ユーザはメニューではなく強い読みを求めている。

---

## チェックリスト

interface design セッションを終える前に:

- [ ] 3 つ以上の **根本的に異なる** 案を提示したか (微差の vary でなく)
- [ ] 各案で interface / 使用例 / seam の裏 / 依存戦略 / トレードオフを書いたか
- [ ] 比較は depth / locality / seam placement の 3 軸で行ったか
- [ ] 自分の推薦を強く述べたか (中立的なメニューになっていないか)
- [ ] CONTEXT.md / reference-language.md の語彙を一貫して使ったか
