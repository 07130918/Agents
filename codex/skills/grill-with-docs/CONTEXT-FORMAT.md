# CONTEXT.md フォーマット

`grill-with-docs` の grilling セッション中に、用語が解決した瞬間に**インラインで** `CONTEXT.md` を更新するための形式。

参考: Matt Pocock "grill-with-docs/CONTEXT-FORMAT.md" を日本語化 + karte-web/uka-route 例を追加。

---

## 構造

```md
# {コンテキスト名}

{このコンテキストが何でなぜ存在するかを 1-2 文で説明}

## Language

**Order**:
{用語の簡潔な定義}
_Avoid_: Purchase, transaction

**Invoice**:
配送後に顧客に送られる支払い請求。
_Avoid_: Bill, payment request

**Customer**:
注文を行う個人または組織。
_Avoid_: Client, buyer, account

## Relationships

- **Order** は1つ以上の **Invoice** を生む
- **Invoice** はちょうど1つの **Customer** に属する

## Example dialogue

> **Dev:** 「**Customer** が **Order** を行った時、すぐに **Invoice** を作成しますか?」
> **Domain expert:** 「いいえ、**Invoice** は **Fulfillment** が確認された後にのみ生成されます」

## Flagged ambiguities

- 「アカウント」が **Customer** と **User** の両方を指して使われていた — 解決: これらは別の概念
```

---

## ルール

- **Be opinionated**: 同じ概念を表す複数の語があるなら、ベストを選び、それ以外は alias として avoid に列挙する
- **矛盾を明示的にフラグ**: 用語が曖昧に使われていたら、"Flagged ambiguities" でコールアウトし、明確な解決を書く
- **定義はタイトに**: 1 文で。「これは何か」を定義し、「これは何をするか」は書かない
- **関係を示す**: bold の用語名を使い、明らかな場合は cardinality (1 対 N 等) を表現する
- **コンテキスト固有の用語のみ**: 一般的なプログラミング概念 (タイムアウト、エラー型、ユーティリティパターン) はプロジェクトで多用されていても入れない。追加前に問う: 「これはこのコンテキストに固有の概念か、それとも一般的なプログラミング概念か?」前者だけが入る
- **自然なクラスタができたら subheading でグループ化**: 1 つのまとまりに全用語が属するなら flat list で OK
- **Example dialogue を書く**: 開発者とドメイン専門家の対話を書き、用語が自然にどう絡むか・関連概念の境界がどう線引かれるかを示す

---

## 単一 vs 複数コンテキスト

### 単一コンテキスト (大半のリポジトリ)

ルートに 1 つの `CONTEXT.md`。

### 複数コンテキスト

ルートに `CONTEXT-MAP.md` を置き、コンテキスト一覧と所在・関係を書く:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md) — 顧客注文の受付と追跡
- [Billing](./src/billing/CONTEXT.md) — 請求書生成と決済処理
- [Fulfillment](./src/fulfillment/CONTEXT.md) — 倉庫ピッキングと出荷管理

## Relationships

- **Ordering → Fulfillment**: Ordering が `OrderPlaced` イベントを発行、Fulfillment がそれを消費してピッキング開始
- **Fulfillment → Billing**: Fulfillment が `ShipmentDispatched` イベントを発行、Billing がそれを消費して請求書生成
- **Ordering ↔ Billing**: `CustomerId` と `Money` の型を共有
```

スキルは構造を推論する:

- `CONTEXT-MAP.md` があればそれを読んでコンテキスト所在を見つける
- ルート `CONTEXT.md` のみがあれば単一コンテキスト
- どちらも無ければ、最初の用語が解決した時にルート `CONTEXT.md` を遅延作成

複数コンテキストがある時は、現在の話題がどのコンテキストに属するかを推論する。不明なら問う。

---

## karte-web / uka-route 向け例 (日本語ドメイン)

`uka-route` (大学合格体験記プラットフォーム) の単一コンテキスト例:

```md
# Uka Route

合格体験記を学生が投稿し、未来の受験生が参照するためのコンテキスト。

## Language

**Story**:
合格者が「どの大学に・どう合格したか」を記録した投稿。
_Avoid_: Article, Post (どちらも汎用すぎる — Story は受験ストーリー固有の意味を持つ)

**Author**:
Story を書いた合格者本人。
_Avoid_: User, Writer (User は閲覧者と区別したい)

**Reader**:
Story を読む未来の受験生。
_Avoid_: User (Author と区別する)

**Strategy**:
Author が Story の中で記述する「合格戦略」 (どの教材・どのスケジュールで合格したか)。
_Avoid_: Plan (Plan は学習計画を指す別概念)

## Relationships

- 1 人の **Author** は複数の **Story** を持ちうる
- 1 つの **Story** は 1 つ以上の **Strategy** を含む
- **Reader** は **Story** を購読 (subscribe) できる

## Example dialogue

> **Dev:** 「Author が複数大学に合格したら、Story はどう分けますか?」
> **Domain expert:** 「大学ごとに別 Story にします。Strategy は大学ごとに違うので」

## Flagged ambiguities

- 「ユーザ」が Author と Reader の両方を指して曖昧に使われていた — 解決: 別概念として Author / Reader を使い分ける
```
