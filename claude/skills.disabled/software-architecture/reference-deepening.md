# Deepening — shallow なモジュール群を深くする

`software-architecture/SKILL.md` のアーキテクチャ改善ワークフローから参照される、deep module 化の具体手順。`reference-language.md` の語彙 (Module / Interface / Seam / Adapter) を前提とする。

参考: Matt Pocock "improve-codebase-architecture/DEEPENING.md" を日本語化。

---

## 依存カテゴリ

deepening 候補の依存を分類する。**カテゴリが決まると、deepened module を seam 越しにどうテストするかが決まる**。

### 1. In-process

純粋計算、メモリ内状態、I/O 無し。**常に deepenable** — モジュールを統合し、新しい interface を直接テストする。adapter 不要。

### 2. Local-substitutable

ローカルテスト代替が存在する依存 (Postgres → PGLite、ファイルシステム → in-memory FS)。代替が存在すれば deepenable。**deepened module はテスト suite 内で代替を起動してテストする**。seam は内部、外部 interface には port を出さない。

### 3. Remote but owned (Ports & Adapters)

自分のサービスがネットワーク越しにある場合 (マイクロサービス、内部 API)。

- seam に **port (interface)** を定義
- deep module はロジックを所有、トランスポートは **adapter** として注入
- テストは in-memory adapter を使う
- 本番は HTTP / gRPC / queue の adapter を使う

提案の形:

> 「seam に port を定義し、本番用に HTTP adapter、テスト用に in-memory adapter を実装することで、ネットワーク越しでもロジックは 1 つの deep module にまとめる」

### 4. True external (Mock)

自分が制御しない第三者サービス (Stripe、Twilio 等)。deepened module は外部依存を**注入された port** として受け取り、テストは mock adapter を提供する。

---

## Seam 規律

- **1 adapter = 仮説的 seam、2 adapter で初めて real seam**: 何かが seam の両側で実際に変わらない限り port を導入しない。典型的には「本番 + テスト」の 2 adapter が成立してから port を作る。**1 adapter の seam は単なる indirection**
- **内部 seam vs 外部 seam**: deep module は内部 seam (private — 自分のテストだけが使う) と外部 seam (interface) の両方を持って良い。**内部 seam を「テストが使うから」だけの理由で interface に晒さない**

---

## テスト戦略: replace, don't layer

### 1. Shallow テストは削除する

deepened module の interface でテストが書けたら、もとの shallow モジュールへの unit テストは**ゴミ**になる。**残さず削除**。新旧両方を維持してはいけない (どちらが本物の挙動を守っているか分からなくなる)。

### 2. deepened module の interface でテストを書く

**Interface = test surface**。テストは観察可能な結果を interface 経由で assert する。internal state を覗かない。

### 3. 内部リファクタで生き残るテスト

テストは挙動を記述するべきで、実装を記述するべきではない。**実装が変わってテストも変えねばならない**なら、それは interface の先をテストしている。テストの形を見直す。

---

## チェックリスト

deepening 提案を出す前に:

- [ ] 候補モジュール群の依存をカテゴリ分けした
- [ ] 各カテゴリに対応するテスト戦略を選んだ
- [ ] adapter が 2 つ以上必要なケースで初めて port を提案している (1 adapter なら統合)
- [ ] 既存 shallow テストを削除する計画がある
- [ ] 新しい interface でのテストが**観察可能な挙動**を記述する
- [ ] 命名が `CONTEXT.md` のドメイン語彙と整合する (なければ `CONTEXT.md` を更新する提案を併記)
