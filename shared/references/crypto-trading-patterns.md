# 暗号通貨取引パターン (Python)

取引所 API 連携・ストラテジ実装・バックテストの共通パターンと落とし穴をまとめる。プロジェクト固有設定は `CLAUDE.md` を優先する。

## 基本原則

- ✅ 注文ロジックは **dry-run モード** を最初から仕込む。本番投入前に必ず paper trade で動作確認
- ✅ API キーは `.env` 経由でのみ読み込む。リポジトリにコミットしない
- ✅ 数量・価格は **必ず `Decimal`** で扱う。`float` は丸め誤差で約定ズレが起きる
- ✅ レート制限は **HTTP 429 を見てから減らす** のではなく事前にスロットリング
- ❌ 戦略コードに取引所固有のシンボル名 (`BTC_JPY` vs `BTC/JPY`) をハードコードしない → adapter で吸収
- ❌ バックテストと本番で別実装にしない。同じ Strategy インターフェース + 異なる Executor を差し替える

---

## 取引所 API レイヤ

### ccxt vs 直叩き

```python
# ✅ 複数取引所対応・先物含むなら ccxt
import ccxt
exchange = ccxt.bitflyer({
    "apiKey": os.environ["BITFLYER_API_KEY"],
    "secret": os.environ["BITFLYER_API_SECRET"],
    "enableRateLimit": True,  # 重要: 取引所定義のレート制限を自動遵守
})

# ✅ 国内取引所単独・特殊エンドポイント使うなら直叩き
# bitFlyer は ccxt 対応が遅いことがあるので公式 API 直叩きが安全な場合あり
```

### HMAC 署名 (bitFlyer 例)

```python
import hashlib, hmac, time, json, requests

def signed_request(method: str, path: str, body: dict | None = None):
    timestamp = str(int(time.time() * 1000))
    body_str = json.dumps(body) if body else ""
    message = timestamp + method + path + body_str
    signature = hmac.new(
        os.environ["BITFLYER_API_SECRET"].encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "ACCESS-KEY": os.environ["BITFLYER_API_KEY"],
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-SIGN": signature,
        "Content-Type": "application/json",
    }
    return requests.request(method, f"https://api.bitflyer.com{path}", headers=headers, data=body_str)
```

**落とし穴**:
- 署名対象は `timestamp + method + path + body_string`。`body_string` は JSON シリアライズ後の **実際に送信する文字列**。`json.dumps` の空白/key 順が一致しないと 401
- タイムスタンプは ms 単位 (取引所によって sec 単位)。サーバー時刻と 30 秒以上ズレると拒否される

---

## レート制限とリトライ

```python
import time
from functools import wraps

class RateLimiter:
    """トークンバケット。1秒あたり N 回まで許可"""
    def __init__(self, rate: float):
        self.rate = rate
        self.last = 0.0

    def wait(self):
        now = time.time()
        elapsed = now - self.last
        sleep = max(0, (1.0 / self.rate) - elapsed)
        if sleep > 0:
            time.sleep(sleep)
        self.last = time.time()

def with_retry(max_retries=3, backoff=1.0):
    """429/5xx で指数バックオフ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    res = func(*args, **kwargs)
                    if res.status_code == 429:
                        time.sleep(backoff * (2 ** attempt))
                        continue
                    if 500 <= res.status_code < 600:
                        time.sleep(backoff * (2 ** attempt))
                        continue
                    return res
                except requests.exceptions.RequestException:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(backoff * (2 ** attempt))
        return wrapper
    return decorator
```

---

## WebSocket でのリアルタイム feed

```python
import asyncio, json, websockets

async def subscribe_ticker(symbol: str, on_tick):
    url = "wss://ws.lightstream.bitflyer.com/json-rpc"
    async for ws in websockets.connect(url):  # 自動再接続
        try:
            await ws.send(json.dumps({
                "method": "subscribe",
                "params": {"channel": f"lightning_ticker_{symbol}"},
                "id": 1,
            }))
            async for msg in ws:
                data = json.loads(msg)
                if "params" in data:
                    await on_tick(data["params"]["message"])
        except websockets.ConnectionClosed:
            continue  # 再接続
```

**落とし穴**:
- ping/pong を取引所側が要求する場合あり (Bybit 等)。`websockets` の `ping_interval` を設定
- 切断時に **subscribe メッセージを再送** する必要がある。再接続ループの中で `subscribe` も呼ぶ
- メッセージ順序は保証されない。タイムスタンプで並び替える

---

## OHLCV 取得とバックテスト用データ整備

```python
import pandas as pd

def fetch_ohlcv(exchange, symbol: str, timeframe: str = "1h", since: int | None = None, limit: int = 1000) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("timestamp").sort_index()
    return df

def fetch_ohlcv_paginated(exchange, symbol: str, timeframe: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """API の limit を超える期間を分割取得"""
    chunks = []
    cursor = start_ms
    while cursor < end_ms:
        df = fetch_ohlcv(exchange, symbol, timeframe, since=cursor, limit=1000)
        if df.empty:
            break
        chunks.append(df)
        last_ts = int(df.index[-1].timestamp() * 1000)
        if last_ts <= cursor:
            break  # 進まなくなったら終了
        cursor = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)
    return pd.concat(chunks).drop_duplicates()
```

---

## 戦略 (Strategy) インターフェース

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"
    NONE = "none"

@dataclass
class Signal:
    side: Side
    size: float  # 単位は枚数
    reason: str  # ログ・分析用

class Strategy(ABC):
    @abstractmethod
    def on_bar(self, df: pd.DataFrame) -> Signal:
        """新しいバーが確定したタイミングで呼ばれる"""
        ...
```

**重要**: `Strategy` は **状態を持たない** か、`reset()` できる設計に。バックテストと本番で同じインスタンスを使い回せること。

---

## バックテストの基本骨格

```python
@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp | None
    side: Side
    entry_price: float
    exit_price: float | None
    size: float
    pnl: float | None

def backtest(df: pd.DataFrame, strategy: Strategy, fee_rate: float = 0.00015) -> list[Trade]:
    trades: list[Trade] = []
    position: Trade | None = None

    for i in range(len(df)):
        window = df.iloc[: i + 1]
        signal = strategy.on_bar(window)
        bar = df.iloc[i]

        # クローズ判定
        if position and signal.side != position.side and signal.side != Side.NONE:
            position.exit_ts = bar.name
            position.exit_price = bar["close"]
            pnl_per_unit = (position.exit_price - position.entry_price) * (1 if position.side == Side.BUY else -1)
            fee = (position.entry_price + position.exit_price) * fee_rate * position.size
            position.pnl = pnl_per_unit * position.size - fee
            trades.append(position)
            position = None

        # エントリ判定
        if not position and signal.side != Side.NONE:
            position = Trade(
                entry_ts=bar.name, exit_ts=None, side=signal.side,
                entry_price=bar["close"], exit_price=None,
                size=signal.size, pnl=None,
            )

    return trades
```

**落とし穴**:
- ❌ **未来データを参照しない (look-ahead bias)**。`window = df.iloc[:i+1]` のように現在バーまでに制限する
- ❌ シグナルを **当該バーの close で約定** とする場合と **次バーの open** とする場合で結果が大きく変わる。明示する
- ❌ スリッページ・手数料を考慮しないバックテストは過大評価。必ず `fee_rate` と `slippage` を入れる
- ❌ 出来高 (volume) が薄い時間帯は約定不能の前提も。volume フィルタを入れる

---

## 注文ロジック共通の落とし穴

- ✅ **同一クライアント注文 ID** (`client_order_id`) を必ず付与。リトライ時の二重発注を防ぐ
- ✅ ポジション・残高は **取引所から都度取得** する。ローカル状態を信用しない (約定通知漏れに備える)
- ✅ 起動時に **未約定注文をキャンセル** するクリーンアップを入れる
- ❌ 最小注文単位 (`min_amount`) と価格刻み (`tick_size`) を無視しない → 0.0001 BTC 未満は拒否される取引所多数
- ❌ 成行注文の数量に **JPY 建て金額** ではなく **BTC 数量** を渡してしまう取り違え

---

## ログ・観測性

```python
import structlog

logger = structlog.get_logger()

logger.info("signal", symbol="BTC_JPY", side=signal.side, size=signal.size, reason=signal.reason)
logger.info("order_placed", client_order_id=cid, side=side, size=size, price=price)
logger.info("order_filled", client_order_id=cid, fill_price=fill_price, fee=fee)
```

戦略の意思決定 (`reason`) を必ず残す。後でバックテストとの差分調査に必須。

---

## チェックリスト (新規戦略追加時)

- [ ] dry-run モードで 1 週間以上 paper trade した
- [ ] バックテスト結果と paper trade の差分が許容範囲内か
- [ ] 最大ドローダウン・シャープレシオを算出した
- [ ] 損切り・利確・最大ポジションサイズが明示されている
- [ ] エラー時のフェイルセーフ (全ポジションクローズ等) を実装した
- [ ] 取引所 API キーは本番/テストネット分離されている
- [ ] tick_size / min_amount の丸めをテストした
