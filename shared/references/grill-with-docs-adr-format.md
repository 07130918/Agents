# ADR Format

ADRは `docs/adr/` に置き、`0001-slug.md`、`0002-slug.md` のように連番で命名する。最初のADRが必要になった時だけdirectoryを遅延作成する。

参考: [Matt Pocock domain-modeling/ADR-FORMAT.md](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/ADR-FORMAT.md)

## Template

```md
# {決定の短いタイトル}

{1から3文でcontext、決定、理由を書く}
```

ADRは1段落でよい。価値はsectionを埋めることではなく、決定と理由を残すことにある。

## 任意section

真に価値を加える場合だけ含める。大半のADRには不要。

- `Status` frontmatter: `proposed | accepted | deprecated | superseded by ADR-NNNN`
- `Considered Options`: 却下した代替案を将来も覚えておく価値がある場合
- `Consequences`: 自明でない下流効果を明示する必要がある場合

## 採番

対象contextの `docs/adr/` をscanし、最大の既存番号に1を足す。system-wide decisionはルートの `docs/adr/`、context-specific decisionは該当contextの `docs/adr/` に置く。

## ADRを提案するgate

次の3条件をすべて満たす時だけ提案する。

1. 元に戻すcostが意味のあるレベルで高い。
2. contextがなければ将来の読み手にとって驚く。
3. 真の代替案を比較したtrade-offの結果である。

簡単に戻せる、理由が自明、真の代替案がない場合は作らない。

## 該当する例

- monorepo、event sourcingなどarchitectureの形
- context間のintegration pattern
- database、auth provider、deployment targetなどlock-inを伴う技術選択
- data ownership、context境界、明示的に行わないscope
- ORMを使わないなど、当然に見える選択肢から意図的に外れた決定
- complianceや外部契約などコードから見えない制約
- 却下理由を将来もう一度議論しそうな代替案

## 該当しない例

- 差し替えcostが低いlibraryの採用
- formatterや命名規則などのcode style
- 実装中に簡単に変更できる局所的な選択

迷ったら作らない。冗長なADRで重要な決定を埋もれさせない。
