# Migration From Claude Repository

既存の `07130918/Claude` は Claude Code 専用の管理リポジトリでした。

今後は `Agents` を Codex / Claude Code 共通の管理リポジトリとし、`Claude` は archive します。

## 移行方針

1. `Agents` に `shared/`、`codex/`、`claude/`、`scripts/`、`docs/` を置く。
2. Claude Code の既存 `CLAUDE.md`、skill、subagent は `claude/` 配下へ移す。移行時点のskillとsubagentは Claude 5 世代向け再設計まで `skills.disabled/` と `agents.disabled/` に退避する。移行後の新規skillはユーザーの明示確認がある場合だけ `skills/` で有効管理する。
3. Codex の `AGENTS.md`、skill wrapper、agent 定義、hooks は `codex/` 配下へ置く。
4. 共通 reference は `shared/references/` へ置く。
5. 認証情報、履歴、cache、SQLite は移行しない。

## Archive Timing

`Agents` の初回 push とローカル同期確認が完了してから、`07130918/Claude` を archive します。
