# pytest 落とし穴リファレンス

## fixture のスコープ

```python
@pytest.fixture(scope="function")  # デフォルト、テストごと
def clean_db():
    db.truncate_all()
    yield db
    db.close()

@pytest.fixture(scope="session")   # セッション全体で 1 回
def test_client():
    return TestClient(app)
```

- `function`: 最も安全だが遅い
- `session`: 共有状態を作るため、状態を変更しないものに限る
- `module` / `class`: 中間。使う前に影響範囲を明確に

## monkeypatch vs mocker

```python
# ✅ 環境変数: monkeypatch
def test_config(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    assert load_config().api_key == "test-key"

# ✅ 関数モック: pytest-mock (mocker)
def test_fetch(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {"id": 1}
    result = fetch_user(1)
    assert result["id"] == 1
```

`monkeypatch` は pytest 標準、`mocker` は `unittest.mock` のラッパーで spy 機能が強力。

## 例外テスト

```python
# ❌ 例外メッセージの確認が緩い
with pytest.raises(ValueError):
    validate(bad_input)

# ✅ match で具体的に検証
with pytest.raises(ValueError, match=r"amount must be positive"):
    validate(bad_input)
```

## pytest でテストが発見されない時

1. ファイル名が `test_*.py` または `*_test.py` か
2. クラス名が `Test*` で始まっているか (ある場合)
3. 関数名が `test_` で始まっているか
4. `__init__.py` の有無で挙動が変わる場合がある
