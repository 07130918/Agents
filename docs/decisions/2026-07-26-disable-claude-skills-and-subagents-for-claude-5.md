# Claude 5 世代向け再設計まで Claude Code skill と subagent を無効化する

- ステータス: 採用
- 決定日: 2026-07-26
- 対象: Claude Code のユーザーグローバル skill と subagent

## 背景

Opus 5 では、以前のモデル向けに積み重ねた skill や workflow が指示競合、作業の早期終了、既存手順との不整合につながる可能性がある。Dan Shipper 氏の[初期評価](https://x.com/danshipper/status/2080700057892815114)でも、既存 skill を外して一から試した場合に結果が改善したと報告されている。

Anthropic の[Claude 5 世代向け context engineering ガイド](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)では、Opus 5 と Fable 5 向けに Claude Code の system prompt を 80% 以上削減しても、coding evaluation で測定可能な性能低下がなかったと報告されている。同ガイドは system prompt、`CLAUDE.md`、skill 間の重複や競合による過剰制約を避け、必要な context を段階的に読み込む設計を推奨している。

Claude Code のユーザー subagent は全プロジェクトから検出され、description に基づく自動委譲の対象となる。subagent の system prompt や model 指定も以前のモデル向け workflow の一部なので、skill だけを外しても素の挙動との比較に旧設定が混ざる。

この報告だけを一般的な性能評価として確定はしない。一方で、現在の skill と subagent をそのまま Opus 5 へ適用するより、素の挙動を基準に必要な手順だけを再設計する方が、互換性問題を切り分けやすいと判断した。

## 決定

1. `claude/skills/` を `claude/skills.disabled/` へ移し、既存の Claude Code 用 wrapper を Git 履歴に残したまま一時無効化する。
2. `claude/agents/` を `claude/agents.disabled/` へ移し、既存の Claude Code 用 subagent も一時無効化する。
3. ローカル設定も `~/.claude/skills/` と `~/.claude/agents/` から、それぞれ `.disabled` を付けたディレクトリへ移す。
4. 同期スクリプトは `.disabled` ディレクトリを正本として扱い、`scripts/apply-to-local.sh` の実行時に有効な skill と subagent が残らないようにする。
5. Codex の skill と agent、Claude Code の `CLAUDE.md`、共通 reference は今回の対象外とし、変更しない。
6. Claude 5 世代向け skill と subagent は既存セットの一括復元ではなく、素の Opus 5 と Fable 5 との比較で必要性を確認したものから別の変更として再導入する。

## 再設計方針

1. Opus 5 と Fable 5 に共通する軽量な設定を基本とし、モデル別の設定は比較結果で必要性を確認できる場合だけ追加する。
2. `CLAUDE.md` はリポジトリの目的とコードから推測しにくい注意点を中心にし、一般的なコーディング規則を増やしすぎない。
3. skill は特定タスクで必要な知識や判断基準へ到達するための軽量な guide とし、長い手順は progressive disclosure で分割する。
4. 具体例の反復で探索範囲を狭めるより、tool や script の interface、引数、事後条件を明確にする。
5. subagent は context 分離、tool 制限、独立検証など主 thread と異なる実行環境が必要な場合に限定する。model の固定は比較検証で必要性が確認できる場合だけ行う。
6. 旧設定を一括で戻さず、代表タスクによる baseline との比較と回帰確認を追加単位ごとに行う。

## 影響

- Claude Code は `~/.claude/skills/` と `~/.claude/agents/` にあるユーザーグローバル拡張を検出しなくなる。
- 組み込み、plugin 提供、プロジェクトローカルの skill と subagent はこの決定の対象外となる。
- 退避した wrapper、subagent 定義、共通 reference は削除しないため、内容の参照と段階的な再設計ができる。
- `scripts/sync-from-local.sh` は有効な `~/.claude/skills/` または `~/.claude/agents/` が存在する場合に失敗し、意図しない再有効化を防ぐ。

## 検討した代替案

### 既存 skill を削除する

復元と比較が難しくなるため採用しない。ディレクトリ移動なら差分上も意図が明確で、Git から復元できる。

### frontmatter や権限設定で自動呼び出しだけを止める

全定義または名前ごとの編集が必要で、手動呼び出し可能な状態も残り得る。素の Opus 5 を評価する目的には不十分なため採用しない。

### `skillOverrides` で各 skill を `off` にする

skill 名ごとの設定管理が必要で、新規追加時の無効化漏れが起こり得る。今回の一括退避より状態が分散するため採用しない。

## 復帰条件

次の条件を満たす skill または subagent だけを、別の PR で有効な配置へ戻す。

1. Opus 5 と Fable 5 の素の挙動と比較し、設定を追加する必要性が説明できる。
2. 代表タスクで作業の早期終了、指示競合、不要な委譲を増やさないことを確認できる。
3. 低または中 effort を含む想定運用で再現性を確認できる。
4. 定義、共通 reference、同期スクリプト、運用文書の対応が検証されている。

緊急に以前の状態へ戻す場合は、この決定を取り消す PR を作成して `claude/skills.disabled/` と `claude/agents.disabled/` を有効な配置へ戻し、同期先も同時に復元する。
