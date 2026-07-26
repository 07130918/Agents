# アーキテクチャ語彙 (Language)

`software-architecture/SKILL.md` のアーキテクチャ改善ワークフローおよび deep module 設計が依拠する共通語彙。**正確に**この語を使う。`component` / `service` / `API` / `boundary` 等への揺れを避ける。一貫した言葉が要点。

参考: Matt Pocock "improve-codebase-architecture/LANGUAGE.md" を日本語化。

---

## 用語

### Module (モジュール)

interface と implementation を持つもの。**意図的に粒度に依存しない** — 関数・クラス・パッケージ・層をまたぐスライス、すべてに同じく適用する。

- 避ける: unit, component, service

### Interface (インターフェース)

呼び出し元 (caller) が**正しく使う**ために知らねばならない**全て**。型シグネチャだけでなく:

- 不変条件 (invariants)
- 順序制約 (ordering constraints)
- エラーモード
- 必要設定
- 性能特性

を含む。

- 避ける: API, signature (どちらも型表面しか指さない、ここでの interface はもっと広い)

### Implementation (実装)

モジュールの中身、コード本体。

**Adapter との区別**: あるモジュールは「小さい adapter + 大きい implementation」(例: Postgres リポジトリ) にもなれば、「大きい adapter + 小さい implementation」(例: in-memory フェイク) にもなる。`adapter` は seam が話題の時に使い、`implementation` はそれ以外で使う。

### Depth (深さ)

interface での **leverage** (=てこの効き)。caller (またはテスト) が学ばねばならない interface 量に対して、行使できる挙動の量。

- **Deep**: 小さい interface の裏に多くの挙動
- **Shallow**: interface が implementation とほぼ同じ複雑さ

### Seam (継ぎ目) — Michael Feathers より

その場所で挙動を変えられる場所。ある場所をそこで「直接編集せずに」差し替えられる。モジュールの interface が**生息する場所**。**どこに seam を置くか**は「seam の裏に何を置くか」とは別の設計判断。

- 避ける: boundary (DDD bounded context と意味が被る)

### Adapter (アダプタ)

seam で interface を満たす具体物。**役割** (どのスロットを埋めるか) を表し、中身そのものではない。

### Leverage (レバレッジ)

depth から **caller** が得るもの。学ぶ単位 interface 量に対する挙動の量。1 つの implementation が N 個の呼び出しサイトと M 個のテストに対して還元される。

### Locality (局所性)

depth から**保守者**が得るもの。変更・バグ・知識・検証が caller に拡散せず 1 箇所に集中する性質。1 箇所を直せば全部直る。

---

## 原則

### Depth は interface の性質

depth は interface の性質であって implementation の性質ではない。深いモジュールの内部は小さく・モック可能・差し替え可能なパーツで構成されていて構わない — それらが**interface に出ていなければ**良い。

モジュールは**内部 seam** (private — 自分のテストだけが使う) と**外部 seam** (interface) の両方を持って良い。

### Deletion test (削除テスト)

shallow を疑うモジュールを頭の中で削除する:

- 複雑性が**消える** → モジュールは何も隠していなかった (pass-through)
- 複雑性が **N 個の caller に再出現する** → モジュールは機能していた (機能を稼いでいた)

### Interface = test surface

caller とテストは**同じ seam を通る**。interface の**先**をテストしたくなったら、モジュールの形が間違っている可能性が高い。

### 1 adapter = 仮説的 seam、2 adapter で初めて real seam

何かが seam の両側で実際に変わらない限り、port を導入しない。**1 adapter の seam は単なる indirection**。

---

## 関係

- **Module** はちょうど 1 つの **Interface** を持つ (caller とテストに見せる surface)
- **Depth** は **Module** の性質で、**Interface** に対して測られる
- **Seam** は **Module** の **Interface** が生息する場所
- **Adapter** は **Seam** に立ち、**Interface** を満たす
- **Depth** は caller に **Leverage** を、保守者に **Locality** を生む

---

## 拒否された framings

### Depth = implementation 行数 / interface 行数 (比率)

(原書の Ousterhout は実質これに近い) **誤り**。implementation を膨らませると score が上がる、逆方向のインセンティブ。**Leverage で測る**。

### Interface = TypeScript の `interface` キーワード / クラスの public methods

**狭すぎる**。ここでの interface は「caller が知らねばならない全ての事実」を含む。型表面だけではない。

### Boundary

DDD の bounded context と被る。**Seam** または **Interface** を使う。
