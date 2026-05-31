---
name: serena
description: `/serena`、`serena`、`serena-dev`、または「Serena方式」が明示された時に、アプリ開発、バグ調査、設計、実装、リファクタ、レビュー、最適化を構造化して進める。debug/design/implement/review、-q/-d/-c/-s/-r/-t などの深度指定に対応し、Serena MCP tools が未接続でも通常の検索、読解、編集で代替する。単純なバグ調査、PR作成、CI復旧など専用 skill が明らかな依頼では、その専用 skill を優先する。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, mcp__serena__find_symbol, mcp__serena__find_referencing_symbols, mcp__serena__get_symbols_overview, mcp__serena__list_dir, mcp__serena__search_for_pattern, mcp__serena__replace_regex, mcp__serena__replace_symbol_body, mcp__serena__insert_after_symbol, mcp__serena__insert_before_symbol, mcp__serena__think_about_collected_information, mcp__serena__think_about_task_adherence, mcp__serena__think_about_whether_you_are_done
---

# serena

この skill の詳細手順は `~/.agents/references/serena.md` に集約しています。

この skill が発火したら、作業前に必ず上記の参照ファイルを読み、実行中の CLI に対応する手順・チェックリスト・注意事項に従ってください。
