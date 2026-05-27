# uv-python-tooling

この参照は複数 CLI から使う共通本体です。実行中の CLI に対応する節だけを使用してください。

## Codex / .agents 版

# uv Python ツーリング

Python プロジェクトで `uv` を使うときの標準パターン。グローバル AGENTS.md の「Python 実行は常に uv」を実装レベルに展開する。

## ❌ 禁止コマンド

| 禁止 | 理由 | 代替 |
|---|---|---|
| `python3 script.py` | システム Python に依存し再現性が低い | `uv run python script.py` |
| `python -m pytest` | 同上 | `uv run pytest` |
| `pip install <pkg>` | グローバル汚染 / lock ファイル不整合 | `uv add <pkg>` または `uv pip install <pkg>` |
| `python -m venv .venv && source` | uv が自動管理する `.venv` と競合 | `uv sync` (自動で `.venv` を構築) |

## ✅ 標準コマンド

### 依存関係の同期

```bash
uv sync                       # pyproject.toml + uv.lock から .venv を再構築
uv sync --frozen              # lock を変更せず厳密同期 (CI 推奨)
uv sync --extra dev           # extras 含む
```

### 依存追加・削除

```bash
uv add pandas-ta              # pyproject.toml + lock を更新
uv add --dev pytest pytest-cov
uv remove pandas-ta
```

`uv pip install` は legacy 互換用。新規追加は `uv add` を使う (lock を自動更新)。

### スクリプト実行

```bash
uv run python script.py
uv run python -m module
uv run pytest tests/
uv run pytest --cov=src/<package> tests/
uv run ruff check src/
uv run black src/
uv run mypy src/
```

`uv run` は仮想環境を意識せず実行できる (毎回 `uv sync --check` 相当が走る)。

### ツール (one-shot)

```bash
uv tool run ruff check        # 一時的に ruff を実行 (依存に追加しない)
uv tool install pre-commit    # ユーザー全体にインストール
```

## pyproject.toml と uv.lock

- **`pyproject.toml`**: 直接依存と制約 (`pandas-ta>=0.4`)。手で編集 OK。
- **`uv.lock`**: 全依存ツリーの解決結果。**手で編集しない**、必ず `uv add/remove/sync` 経由。
- 両方コミットする (CI で `uv sync --frozen` を使うため)。

## CI での実行 (GitHub Actions 例)

```yaml
- name: Install uv
  run: |
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "$HOME/.cargo/bin" >> $GITHUB_PATH

- name: Install dependencies
  run: uv sync --frozen

- name: Run
  run: uv run python scripts/main.py
```

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `ModuleNotFoundError` なのに pyproject.toml に書いてある | `.venv` が古い | `uv sync` で再構築 |
| `uv run` が遅い | lock チェックが毎回走る | 短時間連続実行は `source .venv/bin/activate` 後に `python` 直接実行 |
| `uv.lock` 競合 | 別ブランチで依存追加 | `uv lock --upgrade` で解決後に `uv sync` |
| Python バージョン警告 | `pyproject.toml` の `requires-python` と `.python-version` 不一致 | どちらかに合わせる |

## .python-version

リポジトリ直下に `.python-version` (例: `3.12`) を置くと `uv` が自動でその系列を使う。`pyproject.toml` の `requires-python = ">=3.12"` と整合させる。

## Claude Code 版

# uv Python ツーリング

Python プロジェクトで `uv` を使うときの標準パターン。グローバル CLAUDE.md の「Python 実行は常に uv」を実装レベルに展開する。

## ❌ 禁止コマンド

| 禁止 | 理由 | 代替 |
|---|---|---|
| `python3 script.py` | システム Python に依存し再現性が低い | `uv run python script.py` |
| `python -m pytest` | 同上 | `uv run pytest` |
| `pip install <pkg>` | グローバル汚染 / lock ファイル不整合 | `uv add <pkg>` または `uv pip install <pkg>` |
| `python -m venv .venv && source` | uv が自動管理する `.venv` と競合 | `uv sync` (自動で `.venv` を構築) |

## ✅ 標準コマンド

### 依存関係の同期

```bash
uv sync                       # pyproject.toml + uv.lock から .venv を再構築
uv sync --frozen              # lock を変更せず厳密同期 (CI 推奨)
uv sync --extra dev           # extras 含む
```

### 依存追加・削除

```bash
uv add pandas-ta              # pyproject.toml + lock を更新
uv add --dev pytest pytest-cov
uv remove pandas-ta
```

`uv pip install` は legacy 互換用。新規追加は `uv add` を使う (lock を自動更新)。

### スクリプト実行

```bash
uv run python script.py
uv run python -m module
uv run pytest tests/
uv run pytest --cov=src/<package> tests/
uv run ruff check src/
uv run black src/
uv run mypy src/
```

`uv run` は仮想環境を意識せず実行できる (毎回 `uv sync --check` 相当が走る)。

### ツール (one-shot)

```bash
uv tool run ruff check        # 一時的に ruff を実行 (依存に追加しない)
uv tool install pre-commit    # ユーザー全体にインストール
```

## pyproject.toml と uv.lock

- **`pyproject.toml`**: 直接依存と制約 (`pandas-ta>=0.4`)。手で編集 OK。
- **`uv.lock`**: 全依存ツリーの解決結果。**手で編集しない**、必ず `uv add/remove/sync` 経由。
- 両方コミットする (CI で `uv sync --frozen` を使うため)。

## CI での実行 (GitHub Actions 例)

```yaml
- name: Install uv
  run: |
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "$HOME/.cargo/bin" >> $GITHUB_PATH

- name: Install dependencies
  run: uv sync --frozen

- name: Run
  run: uv run python scripts/main.py
```

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `ModuleNotFoundError` なのに pyproject.toml に書いてある | `.venv` が古い | `uv sync` で再構築 |
| `uv run` が遅い | lock チェックが毎回走る | 短時間連続実行は `source .venv/bin/activate` 後に `python` 直接実行 |
| `uv.lock` 競合 | 別ブランチで依存追加 | `uv lock --upgrade` で解決後に `uv sync` |
| Python バージョン警告 | `pyproject.toml` の `requires-python` と `.python-version` 不一致 | どちらかに合わせる |

## .python-version

リポジトリ直下に `.python-version` (例: `3.12`) を置くと `uv` が自動でその系列を使う。`pyproject.toml` の `requires-python = ">=3.12"` と整合させる。
