"""
Shioaji 永豐金 API 輔助模組

提供統一的 Shioaji API 封裝，包含：
- ShioajiClient: 登入/登出/快照/取得 kbar
- get_kbars_45d: 下載 45 天分鐘 K 線資料
- get_tick_flow: 取得大戶資金流向（Tick 級 >50張 或 >100萬）
- get_whale_flow: 取鯨魚級別（>500萬 或 >200張）的大戶流向
- 支援模擬模式（無 API Key 時用本機 CSV 替代）
"""

import sys
import os
import csv
import json
from datetime import datetime, timedelta, date
from typing import Optional, Union

import numpy as np
import pandas as pd

# ── 路徑設定 ──────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_BASE, "data")
_TICK_DIR = os.path.join(_BASE, "tick_logs")
_CACHE_DIR = os.path.join(_BASE, "cache")
os.makedirs(_DATA_DIR, exist_ok=True)
os.makedirs(_TICK_DIR, exist_ok=True)
os.makedirs(_CACHE_DIR, exist_ok=True)

# ── 全局 Shioaji API 實例（惰性載入）──────────────
_api_instance = None
_api_logged_in = False


# ═══════════════════════════════════════════════════════
#  環境與設定
# ═══════════════════════════════════════════════════════

def load_config() -> dict:
    """載入 .env 中的 SJ_API_KEY / SJ_SEC_KEY / SJ_CA_PATH / SJ_CA_PASSWD"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return {
        "api_key": os.environ.get("SJ_API_KEY", ""),
        "secret_key": os.environ.get("SJ_SEC_KEY", ""),
        "ca_path": os.environ.get("SJ_CA_PATH", ""),
        "ca_passwd": os.environ.get("SJ_CA_PASSWD", ""),
    }


def is_simulation_mode() -> bool:
    """若無 API Key，回傳 True 表示應使用模擬模式"""
    cfg = load_config()
    return not bool(cfg["api_key"] and cfg["secret_key"])


# ═══════════════════════════════════════════════════════
#  ShioajiClient
# ═══════════════════════════════════════════════════════

class ShioajiClient:
    """封裝 Shioaji 登入 / 登出 / 快照 / kbar 取得

    使用方式:
        with ShioajiClient(simulation=True) as api:
            snap = api.get_snapshots(["2330", "2317"])
            kbar = api.get_kbars("2330", start="2026-06-01", end="2026-07-08")
    """

    def __init__(self, simulation: Optional[bool] = None):
        self._simulation = simulation
        self._api = None
        self._contracts = None

    def _get_sim_flag(self) -> bool:
        if self._simulation is not None:
            return self._simulation
        return is_simulation_mode()

    # ── context manager ──
    def __enter__(self):
        self.login()
        return self

    def __exit__(self, *exc):
        self.logout()

    # ── 登入 ──
    def login(self) -> "ShioajiClient":
        """登入永豐 API，回傳 self"""
        import shioaji as sj

        if self._api is not None:
            return self

        cfg = load_config()
        sim = self._get_sim_flag()

        self._api = sj.Shioaji(simulation=sim)
        accounts = self._api.login(
            api_key=cfg["api_key"],
            secret_key=cfg["secret_key"],
            fetch_contract=True,
        )
        self._contracts = self._api.Contracts.Stocks

        # 若有 CA 憑證則啟用
        if cfg["ca_path"] and not sim:
            try:
                self._api.activate_ca(
                    ca_path=cfg["ca_path"],
                    ca_passwd=cfg["ca_passwd"],
                )
            except Exception as e:
                print(f"[ShioajiClient] 啟動 CA 失敗 (非致命): {e}", file=sys.stderr)

        return self

    # ── 登出 ──
    def logout(self):
        """登出並釋放資源"""
        if self._api is not None:
            try:
                self._api.logout()
            except Exception:
                pass
            self._api = None
            self._contracts = None

    @property
    def api(self):
        if self._api is None:
            raise RuntimeError("尚未登入，請先呼叫 login() 或使用 with ShioajiClient()")
        return self._api

    # ── 取得合約 ──
    def get_contract(self, stock_id: str):
        """依股號取得 Shioaji Contract 物件"""
        try:
            return self._contracts[stock_id]
        except (KeyError, TypeError):
            raise ValueError(f"找不到 {stock_id} 的合約")

    # ── 快照 ──
    def get_snapshots(self, stock_ids: list[str]) -> list:
        """取得多檔股票即時快照

        Args:
            stock_ids: 股號列表，如 ["2330", "2317"]

        Returns:
            list of shioaji.Snapshot 物件
        """
        contracts = [self.get_contract(sid) for sid in stock_ids]
        return self.api.snapshots(contracts)

    # ── K 線 ──
    def get_kbars(self, stock_id: str, start: str, end: str):
        """取得指定股票 K 線資料

        Args:
            stock_id: 股號字串
            start: 起始日期 "YYYY-MM-DD"
            end: 結束日期 "YYYY-MM-DD"

        Returns:
            shioaji.KBars 物件 (有 .Close / .High / .Low / .Open / .Volume / .ts / .Amount)
        """
        contract = self.get_contract(stock_id)
        return self.api.kbars(contract=contract, start=start, end=end)

    # ── Tick ──
    def get_ticks(self, stock_id: str, start: str, end: str):
        """取得指定時間範圍內的 Tick 資料（需盤中訂閱才有，此處留作介面）

        Args:
            stock_id: 股號
            start: "YYYY-MM-DD"
            end: "YYYY-MM-DD"
        """
        contract = self.get_contract(stock_id)
        try:
            return self.api.ticks(contract=contract, start=start, end=end)
        except Exception as e:
            raise RuntimeError(f"取得 {stock_id} Tick 失敗: {e}")


# ═══════════════════════════════════════════════════════
#  45 天分鐘 K 線下載
# ═══════════════════════════════════════════════════════

def get_kbars_45d(stock_ids: list[str],
                  end_date: Optional[str] = None,
                  use_cache: bool = True,
                  force_download: bool = False) -> dict[str, pd.DataFrame]:
    """下載 45 天分鐘 K 線資料 (含盤中 1 分K)

    Args:
        stock_ids: 股號列表，如 ["2330", "2317", "3231"]
        end_date: 結束日期，預設今天
        use_cache: 是否使用本機快取 (CSV)
        force_download: 強制重新下載（忽略快取）

    Returns:
        dict[str, pd.DataFrame]: {stock_id: DataFrame}
        DataFrame columns: [ts, Open, High, Low, Close, Volume, Amount]
    """
    if end_date is None:
        end = datetime.now()
    else:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    start = end - timedelta(days=45)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # ── 先嘗試從本機快取載入 ──
    result = {}
    cached = _load_kbars_csv(stock_ids)
    if not force_download:
        for sid in stock_ids:
            if sid in cached:
                result[sid] = cached[sid]
        # 若全部都有快取，直接回傳
        if set(result.keys()) == set(stock_ids):
            print(f"[get_kbars_45d] 使用本機快取 ({len(stock_ids)} 檔)")
            return result

    # ── 剩下缺少的，嘗試 Shioaji 下載 ──
    missing = [sid for sid in stock_ids if sid not in result or force_download]
    if missing and not is_simulation_mode():
        try:
            with ShioajiClient() as client:
                for sid in missing:
                    try:
                        kbar = client.get_kbars(sid, start=start_str, end=end_str)
                        df = _kbars_to_dataframe(kbar)
                        if df.empty:
                            print(f"  [get_kbars_45d] {sid}: 無資料")
                            continue
                        result[sid] = df
                        _save_kbars_csv(sid, df)
                        print(f"  [get_kbars_45d] {sid}: 下載 {len(df)} 筆")
                    except Exception as e:
                        print(f"  [get_kbars_45d] {sid}: 錯誤 - {e}", file=sys.stderr)
        except Exception as e:
            print(f"[get_kbars_45d] Shioaji 連線失敗: {e}", file=sys.stderr)
    elif missing:
        print(f"[get_kbars_45d] 模擬模式，無 {len(missing)} 檔快取資料", file=sys.stderr)
        # 補回快取中有但 missing 列表中的
        for sid in missing:
            if sid in cached:
                result[sid] = cached[sid]

    return result


# ═══════════════════════════════════════════════════════
#  大戶資金流向 (Tick 級)
# ═══════════════════════════════════════════════════════

def get_tick_flow(stock_id: str,
                  large_volume: int = 50,
                  large_amount: int = 1_000_000,
                  use_snapshot: bool = True) -> dict:
    """取得大戶資金流向（Tick 級 >50 張 或 >100 萬）

    大戶定義規則（可任意調整）:
        - 單筆成交量 > large_volume (張)  預設 50 張
        - 或 單筆成交金額 > large_amount (元) 預設 100 萬

    回傳格式:
        {
            "stock_id": "2330",
            "淨流入%": 12.5,        # 正數 = 買超
            "大戶買超張數": 1234,
            "大戶賣超張數": 876,
            "總大戶交易量": 2110,
            "總外盤量": 5000,       # 所有買單量
            "總內盤量": 4500,       # 所有賣單量
            "大戶均價": 245.0,
            "模擬模式": False,
        }

    Args:
        stock_id: 股號
        large_volume: 大戶定義之最小張數 (預設 50)
        large_amount: 大戶定義之最小金額 (預設 1,000,000)
        use_snapshot: 若無 Tick，回退使用 Snapshot 估算

    Returns:
        dict: 大戶流向分析結果
    """
    import shioaji as sj

    cfg = load_config()
    sim = is_simulation_mode()

    if sim:
        return _simulate_tick_flow(stock_id)

    api = sj.Shioaji(simulation=True)
    try:
        api.login(api_key=cfg["api_key"], secret_key=cfg["secret_key"], fetch_contract=True)
    except Exception as e:
        print(f"[get_tick_flow] 登入失敗: {e}", file=sys.stderr)
        return _simulate_tick_flow(stock_id)

    try:
        contract = api.Contracts.Stocks[stock_id]
    except Exception as e:
        api.logout()
        return _simulate_tick_flow(stock_id)

    # 優先使用 snapshot (即時買賣盤統計)
    if use_snapshot:
        try:
            snaps = api.snapshots([contract])
            if snaps:
                s = snaps[0]
                buy_vol = getattr(s, "buy_volume", 0)
                sell_vol = getattr(s, "sell_volume", 0)
                close = getattr(s, "close", 0)
                total_vol = buy_vol + sell_vol
                if total_vol > 0:
                    net_pct = round((buy_vol - sell_vol) / total_vol * 100, 1)
                    # 用外內盤比例估算大戶流向
                    whale_buy = int(buy_vol * 0.35)  # 估算: 外盤中約 35% 為大戶
                    whale_sell = int(sell_vol * 0.35)
                    result = {
                        "stock_id": stock_id,
                        "淨流入%": net_pct,
                        "大戶買超張數": whale_buy,
                        "大戶賣超張數": whale_sell,
                        "總大戶交易量": whale_buy + whale_sell,
                        "總外盤量": int(buy_vol),
                        "總內盤量": int(sell_vol),
                        "大戶均價": float(close),
                        "模擬模式": False,
                        "資料來源": "snapshot(外內盤估算)",
                    }
                    return result
        except Exception:
            pass

    # 嘗試取得今日 Tick 計算真實大戶流向
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        ticks = api.ticks(contract=contract, start=today_str, end=today_str)
        result = _analyze_ticks(ticks, stock_id, large_volume, large_amount)
        if result:
            return result
    except Exception:
        pass

    api.logout()
    return _simulate_tick_flow(stock_id)


def get_whale_flow(stock_id: str,
                   large_volume: int = 200,
                   large_amount: int = 5_000_000,
                   use_snapshot: bool = True) -> dict:
    """取鯨魚級別（>500 萬 或 >200 張）的大戶流向

    參數與回傳格式同 get_tick_flow，但門檻更高。
    """
    return get_tick_flow(
        stock_id=stock_id,
        large_volume=large_volume,
        large_amount=large_amount,
        use_snapshot=use_snapshot,
    )


# ═══════════════════════════════════════════════════════
#  內部工具函式
# ═══════════════════════════════════════════════════════

def _kbars_to_dataframe(kbar) -> pd.DataFrame:
    """將 shioaji.KBars 轉為 pandas DataFrame"""
    records = []
    for i in range(len(kbar.ts)):
        records.append({
            "ts": datetime.fromtimestamp(kbar.ts[i] / 1e9),
            "Open": float(kbar.Open[i]),
            "High": float(kbar.High[i]),
            "Low": float(kbar.Low[i]),
            "Close": float(kbar.Close[i]),
            "Volume": float(kbar.Volume[i]),
            "Amount": float(kbar.Amount[i]),
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.set_index("ts")
    return df


def _save_kbars_csv(stock_id: str, df: pd.DataFrame):
    """將 kbar DataFrame 寫入本機快取"""
    path = os.path.join(_DATA_DIR, f"{stock_id}_kbars.csv")
    df.to_csv(path)


def _load_kbars_csv(stock_ids: list[str]) -> dict[str, pd.DataFrame]:
    """從本機快取讀取 kbar CSV，回傳 {sid: DataFrame}"""
    result = {}
    for sid in stock_ids:
        path = os.path.join(_DATA_DIR, f"{sid}_kbars.csv")
        if os.path.isfile(path):
            try:
                df = pd.read_csv(path, index_col=0, parse_dates=True)
                if not df.empty:
                    result[sid] = df
            except Exception:
                pass
    return result


def _analyze_ticks(ticks, stock_id: str, large_vol: int, large_amt: int) -> Optional[dict]:
    """分析 Tick 資料，計算大戶/鯨魚流向"""
    try:
        if ticks is None or len(ticks) == 0:
            return None

        tick_list = list(ticks)
        whale_buy_vol = 0  # 大戶買入張數
        whale_sell_vol = 0  # 大戶賣出張數
        buy_vol = 0
        sell_vol = 0
        total_amt = 0

        for t in tick_list:
            vol = getattr(t, "volume", 0)
            price = getattr(t, "close", 0)
            tick_vol = float(vol) if vol else 0
            tick_price = float(price) if price else 0
            tick_amt = tick_vol * tick_price
            total_amt += tick_amt

            # 判斷買賣方向 (簡化: 用 tick_type 或 price vs bid/ask)
            tick_type = getattr(t, "tick_type", None)
            is_buy = False
            if tick_type is not None:
                is_buy = (str(tick_type) in ("1", "Buy"))
            else:
                # 當無 tick_type 時假設一半一半
                is_buy = True  # 容錯

            if tick_vol >= large_vol or tick_amt >= large_amt:
                if is_buy:
                    whale_buy_vol += tick_vol
                    buy_vol += tick_vol
                else:
                    whale_sell_vol += tick_vol
                    sell_vol += tick_vol
            else:
                if is_buy:
                    buy_vol += tick_vol
                else:
                    sell_vol += tick_vol

        total_whale = whale_buy_vol + whale_sell_vol
        net_whale = whale_buy_vol - whale_sell_vol
        total_all = buy_vol + sell_vol

        net_pct = round((net_whale / total_all * 100), 1) if total_all > 0 else 0.0

        return {
            "stock_id": stock_id,
            "淨流入%": net_pct,
            "大戶買超張數": int(whale_buy_vol),
            "大戶賣超張數": int(whale_sell_vol),
            "總大戶交易量": int(total_whale),
            "總外盤量": int(buy_vol),
            "總內盤量": int(sell_vol),
            "大戶均價": round(total_amt / len(tick_list) / 1000, 2) if tick_list else 0,
            "模擬模式": False,
            "資料來源": "tick",
            "tick筆數": len(tick_list),
        }
    except Exception as e:
        print(f"[_analyze_ticks] 分析失敗: {e}", file=sys.stderr)
        return None


def _simulate_tick_flow(stock_id: str) -> dict:
    """模擬模式：讀取本機 tick 記錄或產生隨機資料"""
    tick_path = os.path.join(_TICK_DIR, f"{stock_id}_ticks.csv")
    cache_path = os.path.join(_CACHE_DIR, f"{stock_id}_flow.json")

    # 嘗試從快取讀取
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["模擬模式"] = True
                data["資料來源"] = "cache"
                return data
        except Exception:
            pass

    # 嘗試從 tick 記錄 CSV 計算
    if os.path.isfile(tick_path):
        try:
            df = pd.read_csv(tick_path)
            if not df.empty and "volume" in df.columns:
                # 估算大戶
                total_buy = df[df["tick_type"] == "Buy"]["volume"].sum() if "tick_type" in df.columns else df["volume"].sum() * 0.52
                total_sell = df[df["tick_type"] == "Sell"]["volume"].sum() if "tick_type" in df.columns else df["volume"].sum() * 0.48
                total_vol = total_buy + total_sell
                net_pct = round((total_buy - total_sell) / total_vol * 100, 1) if total_vol > 0 else 0
                whale_buy = int(total_buy * 0.3)
                whale_sell = int(total_sell * 0.3)
                result = {
                    "stock_id": stock_id,
                    "淨流入%": net_pct,
                    "大戶買超張數": whale_buy,
                    "大戶賣超張數": whale_sell,
                    "總大戶交易量": whale_buy + whale_sell,
                    "總外盤量": int(total_buy),
                    "總內盤量": int(total_sell),
                    "大戶均價": float(df.get("close", df.get("price", [0])).iloc[-1]),
                    "模擬模式": True,
                    "資料來源": "tick_csv",
                    "tick筆數": len(df),
                }
                # 寫入快取
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
        except Exception:
            pass

    # 最後 fallback：回傳空資料
    return {
        "stock_id": stock_id,
        "淨流入%": 0.0,
        "大戶買超張數": 0,
        "大戶賣超張數": 0,
        "總大戶交易量": 0,
        "總外盤量": 0,
        "總內盤量": 0,
        "大戶均價": 0.0,
        "模擬模式": True,
        "資料來源": "模擬(無資料)",
        "tick筆數": 0,
    }


def _get_mock_contract(stock_id: str):
    """模擬模式用的假合約物件"""
    return type("MockContract", (), {"code": stock_id})()


# ═══════════════════════════════════════════════════════
#  Quick Test (python -m sj_trading.shioaji_helper)
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # 簡單測試
    print("=" * 60)
    print("  Shioaji Helper 測試")
    print("=" * 60)
    print(f"  模擬模式: {is_simulation_mode()}")
    print()

    # 1. ShioajiClient
    print("[1] ShioajiClient - 登入 + 快照")
    try:
        with ShioajiClient() as client:
            snaps = client.get_snapshots(["2330", "2317"])
            for s in snaps:
                print(f"  {s.code}: {s.close} ({s.volume}張)")
    except Exception as e:
        print(f"  (skip: {e})")
    print()

    # 2. get_kbars_45d
    print("[2] get_kbars_45d - 試下載 2330, 2317")
    kdata = get_kbars_45d(["2330", "2317"])
    for sid, df in kdata.items():
        print(f"  {sid}: {len(df)} 筆, {df.index[0]} ~ {df.index[-1]}")
    print()

    # 3. get_tick_flow
    print("[3] get_tick_flow - 2330 大戶流向")
    flow = get_tick_flow("2330")
    for k, v in flow.items():
        print(f"  {k}: {v}")
    print()

    # 4. get_whale_flow
    print("[4] get_whale_flow - 2330 鯨魚流向")
    wf = get_whale_flow("2330")
    for k, v in wf.items():
        print(f"  {k}: {v}")
