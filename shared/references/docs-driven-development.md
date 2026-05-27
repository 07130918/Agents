# 仕様駆動開発 (Docs-Driven Development)

大型機能を多段 PR に分割するときの設計→実装→記録のフロー。Phase Y (1H レジーム判定型ハイブリッド戦略、PR-Y1〜Y8) で確立したパターン。

## いつ使うか

- 1 PR に収まらない大型機能 (5+ PR 想定)
- 戦略・アルゴリズム・データ移行など、設計判断が後で問われる変更
- 複数人レビューで仕様の前提を揃えたいとき
- ロールバック条件を事前合意したいとき

逆に、1〜2 PR で完結する変更には不要 (コミットメッセージと PR description で十分)。

## ディレクトリ構造

```
docs/
├── design/
│   ├── phase-y-hybrid-strategy.md     # 設計仕様 (8 PR の基準)
│   └── phase-z-<feature>.md            # 次の Phase
├── changelog/
│   ├── 2026-04-26-fix-trading-state-bugs.md
│   ├── 2026-04-26-walkforward-baseline-foundation.md
│   └── YYYY-MM-DD-<change>.md
└── research/
    └── deep-research-report.md         # エビデンス収集 (Web 調査結果など)
```

## ワークフロー (5 ステップ)

### Step 1: リサーチ (任意)

`docs/research/` に Web 検索・論文・既存実装の調査結果を残す。後で「なぜこの数値?」と問われたとき出典が辿れる。

### Step 2: 設計仕様の作成

`docs/design/<feature>.md` を作成。以下を含める:

```markdown
# <feature> 設計仕様

## 1. 戦略概要
### 背景 (現状の課題)
### 解決方針 (採用したアプローチ)
### 主要エビデンス (根拠となる数値・出典)

## 2. <コンポーネント1> 仕様
### 実装ファイル
### 入力 / 出力
### 判定ルール / アルゴリズム
### 実装フェーズ (どの PR で何を実装するか)

## 3. <コンポーネント2> 仕様
...

## 4. ストップロス / 安全装置 (該当する場合)

## 5. 実装ロードマップ (N 段階 PR)

| PR | スコープ | 依存 |
|---|---|---|
| PR-X1 | ... | なし |
| PR-X2 | ... | PR-X1 |

## 6. 検証基準 (本番投入条件)

## 7. ロールバック条件

## 8. 設定パラメータ一覧 (新規追加分)
```

設計レビューを `/codex-review` `/popr` に通してから実装着手。

### Step 3: PR-X1 で「設計 doc + scaffold」をマージ

最初の PR (PR-X1) のスコープ:
- `docs/design/<feature>.md` の本体
- 実装の **scaffold のみ** (クラス骨格、`NotImplementedError` を raise するメソッド)
- 後続 PR で必要となる共通基盤 (基底クラス、共通インデックス計算など)
- 既存挙動を変更しない (既存テスト全 pass)

これで以降の PR は「scaffold を埋める」差分だけで済む。

### Step 4: PR-X2 以降で実装を埋める

各 PR は:
- 設計 doc のどのセクションを実装したか PR description に書く (`docs/design/<feature>.md` の「§3-A」に対応、等)
- scaffold の `NotImplementedError` を本実装に置き換える
- 該当部分のテストを追加
- PR description で **設計 doc の前提を変えていない** ことを明記。設計変更が必要な場合は先に `docs/design/` を更新する PR を出す

### Step 5: 完了時に changelog を残す

`docs/changelog/YYYY-MM-DD-<change>.md` を作成 (PR と一緒にマージ):

```markdown
# YYYY-MM-DD: <change のタイトル>

## サマリー
1-2 文で何が変わったか。

## 背景
何の課題を解決したか。`docs/design/<feature>.md` のどのセクションに対応するか。

## 主な変更
- `path/to/file1.py`: ...
- `path/to/file2.py`: ...

## 影響範囲
- 既存挙動の変化: あり/なし (詳細)
- 設定変更: 新規環境変数 X、デフォルト値変更 Y

## 検証
- 単体テスト: pass / pytest 結果
- バックテスト: PF=X.X, Sortino=X.X (該当する場合)
- 本番動作確認: run #XXX で確認

## 既知の制限
- 後続 PR で対応する未実装部分

## 参考
- 設計仕様: `docs/design/<feature>.md`
- 関連 PR: #N
```

## PR description テンプレート

```markdown
## 概要
<1-2 文>

## このPRのスコープ (`docs/design/<feature>.md` §X)
- [x] ...
- [x] ...

## このPRでやらないこと
- §Y (PR-XN で対応)

## 検証
- [ ] 既存テスト全 pass
- [ ] 新規テスト N 件追加
- [ ] バックテスト結果 (該当する場合)

## ロールバック
このPRをrevertしても <既存機能> は動く。
```

## アンチパターン

| ❌ | ✅ |
|---|---|
| 設計 doc なしで PR を 8 個並べる | PR-X1 で先に doc + scaffold をマージ |
| 各 PR で勝手に設計を変更する | 設計変更は別 PR で doc 更新 |
| 仕様 doc が実装と乖離していくのを放置 | PR description で「§X を実装」と明記しレビューで整合確認 |
| changelog なしで何の意図か追えない | PR と同時に `docs/changelog/` を更新 |
| ロールバック条件を事後に決める | 設計 doc の §7 で事前合意 |

## 関連 skill

- PR 作成: `create-pr` skill
- レビュー観点: `codex-review` / `principle-of-programming-reviewer` skill
- プロジェクト固有の Phase 進行 (例: bitcoin-trader Phase Y): プロジェクト内 skill
