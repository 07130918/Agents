# Grill With Docs

リポジトリの計画や設計をgrillingし、解決したdomain用語と長期的な意思決定をその場で記録するstatefulなworkflow。

ユーザが `grill-with-docs` を明示的に選択した場合だけ開始する。

## 必須reference

最初の質問を出す前に `~/.agents/references/grilling.md` を最後まで読み、そのインタビュー規律に従う。

`CONTEXT.md` を更新する直前に `~/.agents/references/grill-with-docs-context-format.md` を読む。ADRを提案する直前に `~/.agents/references/grill-with-docs-adr-format.md` を読む。必要になる前に両方を読み込まない。

## 使う場面

- リポジトリ内の変更を1つのsessionで合意できるscopeに研ぐ。
- 既存コードとdomain languageを照合しながら、曖昧な用語を解決する。
- 特定featureがなくても、既存リポジトリのdomain languageを整備する。

複数sessionにまたがる大規模計画は先にscopeを分割する。ファイルを更新しない軽量なインタビューには `grill-me` を使う。

## 開始時の探索

最初の質問に入る前に短く探索する。これは質問1つ分に数えない。

1. `CONTEXT-MAP.md`、ルート `CONTEXT.md`、該当contextの `CONTEXT.md`、`docs/adr/` を探す。
2. 計画に関係するコード、schema、API、UI、testを軽く読む。最初から深掘りしすぎない。
3. 次の4点を5から8行で宣言し、frontierから最初の質問を1つ出す。

```text
既知の用語:
既存決定:
未確定領域:
最初に解くべき分岐:
```

断定できないことは `未確定領域` に置く。コードやdocsで確認できる事実をユーザへ質問しない。

## contextを分類する

ルートに `CONTEXT-MAP.md` がある場合は、質問や文書更新の前に次を分類する。

- 用語を所有するbounded context
- 同名の用語が別contextで同じ意味か、異なる意味か
- 決定がsystem-wideか、context-specificか
- context間の関係を変える場合、`CONTEXT-MAP.md` の更新が必要か

分類できない時は、推測で `CONTEXT.md` を更新せず、どのcontextの言葉かを質問する。

## domain modelを研ぐ

### glossaryへ挑戦する

ユーザが既存の `CONTEXT.md` と矛盾する言葉を使ったら即座に指摘する。曖昧またはoverloadされた言葉には、精密なcanonical termを推奨する。

domain上の関係を議論する時は具体的なedge caseを作り、概念の境界をstress-testする。ユーザが説明した挙動はコードと照合し、矛盾があればどちらが正しいかを解決する。

### `CONTEXT.md` をインラインで更新する

次のgateをすべて満たした用語だけを、その場で `CONTEXT.md` へ追加する。バッチ更新しない。

1. ユーザがcanonical termと定義へ明示的に同意した。
2. 既存用語との衝突、alias、avoid語が整理された。
3. コード上の呼称や実際の挙動と矛盾していない。
4. そのcontext固有のdomain概念であり、実装詳細ではない。

仮説段階の語は会話内で `未解決の候補語` として扱う。`CONTEXT.md` はglossaryだけに使い、spec、scratch pad、decision ledgerにしない。DB column、API route、UI component、内部helperはdomain expertにとって意味がある場合だけ用語に含める。

### ADRを控えめに提案する

次の3条件をすべて満たす時だけADRを提案する。

1. 元に戻すcostが意味のあるレベルで高い。
2. contextがなければ将来の読み手にとって驚く。
3. 真の代替案を比較したtrade-offの結果である。

1つでも欠けたらADRを作らない。ユーザが作成へ同意したら、その場で記録する。

## 安全に文書を更新する

- 編集直前に対象ファイルを読み直し、既存の未commit変更を保持する。
- 読み取り後に対象ファイルが変わった場合は、自動的に上書きせず競合を解決する。
- 同じglossaryやADRを複数writerが同時更新している場合は、ownerを決めるまで書き込まない。
- 解決済みでもglossaryにもADRにも該当しない決定は会話に残す。無理に文書へ押し込まない。

## 終了時の引き継ぎ

共通referenceの終了条件を満たしたら、次を短くまとめる。

```text
Resolved decisions:
Deferred questions:
Updated docs:
Created ADRs:
Next step:
```

`Deferred questions` は実装前に解くものと、後でよいものを分ける。`Next step` は `docs-driven-development`、実装、prototype、追加調査から1つ推奨する。glossaryやADRに入らない具体的な制約、negative requirement、数値defaultもsummaryに残し、同じtaskのまま次へ進める。

## 関連 skill

- ドキュメントを書かない軽量版: `grill-me`
- アーキテクチャ改善のgrilling: `software-architecture` のworkflow Step 3
- `docs/design/` を正本にして実装へ進む: `docs-driven-development`
