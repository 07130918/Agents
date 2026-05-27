# asana-workflow

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# Asana MCP ワークフロー

Asanaタスクを起点に実装を進める/実装を起点にAsanaを更新するためのパターン集。

## MCPツールの使い分け

環境に以下のいずれかが存在する:

- `mcp__asana__*` (セルフホスト型)
- `mcp__claude_ai_Asana__*` (Codex.ai連携型)

**どちらを使うかは接続状態に従う**。両方使える場合は `mcp__claude_ai_Asana__*` を優先(認証が統合されている)。
以下は `mcp__asana__*` で記載するが、名前空間を差し替えれば同じ手順で動く。

## 標準ワークフロー

### パターン1: ブランチ名/タスクID → タスク詳細取得
ブランチ名のプレフィックスに Asana の task_id(数字)が入っていることが多い。

```
1. git branch --show-current → ブランチ名からID抽出
2. asana_get_task (task_id) → タスク詳細
3. 必要なら asana_get_stories_for_task で過去コメント確認
4. asana_get_attachments_for_object で添付(仕様書・Figma)確認
```

### パターン2: タスク検索
タスクIDが分からない場合:

```
1. asana_list_workspaces → workspace_gid 取得
2. asana_typeahead_search (workspace_gid, query) → 候補取得
3. asana_search_tasks で条件指定検索 (assignee, 完了状態, プロジェクト)
```

### パターン3: 実装完了後の更新
PR作成やマージのタイミングで:

```
1. asana_create_task_story で進捗コメントを追加
   例: "PR #123 作成: <URL>" / "develop にマージ完了"
2. asana_update_task で completed: true にする (マージ後)
   もしくはcustom_fields でステータス変更
```

### パターン4: 新規タスク作成
バグ発見時・フォローアップ作成時:

```
1. asana_get_projects_for_team で対象プロジェクト確認
2. asana_create_task (name, notes, projects, assignee)
3. 依存関係があれば asana_set_task_dependencies
```

## よく使うパラメータ

### タスク取得時の opt_fields
`asana_get_task` は多くのフィールドを持つが、デフォルト返却は限定的。
必要に応じて opt_fields で指定:
- `name,notes,completed,assignee.name,projects.name,due_on,custom_fields`

### プロジェクト絞り込み
`asana_search_tasks` でプロジェクト指定: `projects.any=<project_gid>`

## 注意点・落とし穴

### ⚠️ task_id は数値
- ブランチ名 `[1234567890]_feat_login` の `1234567890` 部分
- URL `https://app.asana.com/0/<project_gid>/<task_gid>` の最後の数値

### ⚠️ コメントは Markdown 非対応(制限あり)
- `asana_create_task_story` の text は HTML 形式が推奨 (`<body>...<strong>...</strong></body>`)
- 単なる Markdown は太字等が反映されない

### ⚠️ 完了済みタスクへの更新
- 既に `completed: true` のタスクに更新する場合、コメント追加は可能だが完了状態の再オープンには `completed: false` 更新が必要

### ⚠️ workspace_gid / project_gid / task_gid の区別
- 全て数値だが階層が違う。作成・検索時にどちらを渡すべきか確認

### ⚠️ セキュリティ: データ送信の確認
- Asanaタスクのコメントや説明に社内機密(APIキー、個人情報)を含めない
- PR URL や Issue 番号の転記は OK

## 頻出タスク種別

観測された使用パターン:
- `asana_get_task` (122) → タスク起点で実装開始
- `asana_update_task` (117) → 実装完了で状態更新
- `asana_search_tasks` (117) → ID不明時の検索
- `asana_create_task` (117) → 派生タスク・バグ起票

## Claude Code 版

# Asana MCP ワークフロー

Asanaタスクを起点に実装を進める/実装を起点にAsanaを更新するためのパターン集。

## MCPツールの使い分け

環境に以下のいずれかが存在する:

- `mcp__asana__*` (セルフホスト型)
- `mcp__claude_ai_Asana__*` (claude.ai連携型)

**どちらを使うかは接続状態に従う**。両方使える場合は `mcp__claude_ai_Asana__*` を優先(認証が統合されている)。
以下は `mcp__asana__*` で記載するが、名前空間を差し替えれば同じ手順で動く。

## 標準ワークフロー

### パターン1: ブランチ名/タスクID → タスク詳細取得
ブランチ名のプレフィックスに Asana の task_id(数字)が入っていることが多い。

```
1. git branch --show-current → ブランチ名からID抽出
2. asana_get_task (task_id) → タスク詳細
3. 必要なら asana_get_stories_for_task で過去コメント確認
4. asana_get_attachments_for_object で添付(仕様書・Figma)確認
```

### パターン2: タスク検索
タスクIDが分からない場合:

```
1. asana_list_workspaces → workspace_gid 取得
2. asana_typeahead_search (workspace_gid, query) → 候補取得
3. asana_search_tasks で条件指定検索 (assignee, 完了状態, プロジェクト)
```

### パターン3: 実装完了後の更新
PR作成やマージのタイミングで:

```
1. asana_create_task_story で進捗コメントを追加
   例: "PR #123 作成: <URL>" / "develop にマージ完了"
2. asana_update_task で completed: true にする (マージ後)
   もしくはcustom_fields でステータス変更
```

### パターン4: 新規タスク作成
バグ発見時・フォローアップ作成時:

```
1. asana_get_projects_for_team で対象プロジェクト確認
2. asana_create_task (name, notes, projects, assignee)
3. 依存関係があれば asana_set_task_dependencies
```

## よく使うパラメータ

### タスク取得時の opt_fields
`asana_get_task` は多くのフィールドを持つが、デフォルト返却は限定的。
必要に応じて opt_fields で指定:
- `name,notes,completed,assignee.name,projects.name,due_on,custom_fields`

### プロジェクト絞り込み
`asana_search_tasks` でプロジェクト指定: `projects.any=<project_gid>`

## 注意点・落とし穴

### ⚠️ task_id は数値
- ブランチ名 `[1234567890]_feat_login` の `1234567890` 部分
- URL `https://app.asana.com/0/<project_gid>/<task_gid>` の最後の数値

### ⚠️ コメントは Markdown 非対応(制限あり)
- `asana_create_task_story` の text は HTML 形式が推奨 (`<body>...<strong>...</strong></body>`)
- 単なる Markdown は太字等が反映されない

### ⚠️ 完了済みタスクへの更新
- 既に `completed: true` のタスクに更新する場合、コメント追加は可能だが完了状態の再オープンには `completed: false` 更新が必要

### ⚠️ workspace_gid / project_gid / task_gid の区別
- 全て数値だが階層が違う。作成・検索時にどちらを渡すべきか確認

### ⚠️ セキュリティ: データ送信の確認
- Asanaタスクのコメントや説明に社内機密(APIキー、個人情報)を含めない
- PR URL や Issue 番号の転記は OK

## 頻出タスク種別

観測された使用パターン:
- `asana_get_task` (122) → タスク起点で実装開始
- `asana_update_task` (117) → 実装完了で状態更新
- `asana_search_tasks` (117) → ID不明時の検索
- `asana_create_task` (117) → 派生タスク・バグ起票
