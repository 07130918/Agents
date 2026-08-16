# CONTEXT.md Format

`CONTEXT.md` はプロジェクト固有のdomain languageを記録するglossaryであり、spec、scratch pad、実装決定の保管場所ではない。

参考: [Matt Pocock domain-modeling/CONTEXT-FORMAT.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/CONTEXT-FORMAT.md)

## 単一context

大半のリポジトリでは、ルートに1つの `CONTEXT.md` を置く。最初の用語が解決した時だけ遅延作成する。

```md
# {Context Name}

{このcontextが何で、なぜ存在するかを1から2文で説明する}

## Language

**Order**:
{用語が何であるかを1から2文で定義する}
_Avoid_: Purchase, transaction

**Invoice**:
配送後に顧客へ送られる支払い請求。
_Avoid_: Bill, payment request
```

## 用語のルール

- 同じ概念に複数の言葉がある場合はcanonical termを1つ選び、残りを `_Avoid_` に書く。
- 定義は1から2文に収め、何をするかではなく何であるかを書く。
- そのcontext固有のdomain概念だけを含める。timeout、error type、utility patternなどの一般的なprogramming概念は入れない。
- DB column、API route、UI component、内部helperなどの実装詳細を入れない。
- 解決前の候補語、議論の履歴、会話例、spec、受入条件を入れない。
- 自然なclusterができた時だけ `## Language` 配下をsubheadingで分ける。

用語間の関係が定義に不可欠なら短い定義内で説明する。独立した `Relationships`、`Example dialogue`、`Flagged ambiguities` sectionは既定で作らない。

## 複数context

複数のbounded contextがある場合は、ルートに `CONTEXT-MAP.md` を置く。

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md) - 顧客注文の受付と追跡
- [Billing](./src/billing/CONTEXT.md) - 請求書生成と決済処理
- [Fulfillment](./src/fulfillment/CONTEXT.md) - 倉庫作業と出荷管理

## Relationships

- **Ordering -> Fulfillment**: Orderingが`OrderPlaced`を発行し、Fulfillmentが処理を開始する
- **Fulfillment -> Billing**: Fulfillmentが`ShipmentDispatched`を発行し、Billingが請求書を生成する
```

- `CONTEXT-MAP.md` があれば、現在の話題に対応するcontextを見つけて、その `CONTEXT.md` を更新する。
- 同名の用語がcontextごとに違う意味を持つ場合は、各contextのglossaryで個別に定義する。
- context間の関係だけを `CONTEXT-MAP.md` に記録する。context内の詳細な振る舞いはspecやコードへ置く。
- contextを特定できない場合は、推測で更新せずユーザへ確認する。

## 更新gate

次をすべて確認してから書き込む。

1. canonical termと定義にユーザが同意した。
2. aliasとavoid語が整理された。
3. コード上の名称や挙動と矛盾していない。
4. 実装詳細ではなくdomain概念である。
