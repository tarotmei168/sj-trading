"""
🦞 taiwan_lobster_realtime.py — v2
真正的 Tick 驅動即時 30分K KD 極速預警引擎
────────────────────────────────────────────
核心設計：
1. Shioaji Tick 訂閱 → 每筆成交即時 callback
2. 每 tick 進來就更新「當前30分K」的 OHLC
3. 歷史資料載入後，tick 數據即時銜接 KD 計算
4. 智慧配速：第1~24分鐘低頻 / 第25~30分鐘高頻（每筆 tick 都算）
5. 斜率+速度+距離 提前3~5分鐘預警

用法：
   .venv\Scripts\python.exe -X utf8 -m src.sj_trading.taiwan_lobster_realtime
"""
import os, sys, json, time, threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ============================================================
# 設定
# ============================================================
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "watchlist.txt")
SIGNAL_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "lobster_alert_states.json")
APPROACHING_LOG = os.path.join(os.path.dirname(__file__), "..", "..", "lobster_approaching_log.json")
ALERT_QUEUE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "lobster_alert_queue.json")

SLOPE_WINDOW = 3
PREMATURE_DISTANCE = 1.5
UPWARD_SLOPE_MIN = 0.5

# ============================================================
# 讀取自選清單
# ============================================================
def load_watchlist():
    stocks = []
    if not os.path.exists(WATCHLIST_PATH):
        return stocks
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                sid = parts[0]
                name = parts[1]
                kp = int(parts[2]) if len(parts) > 2 and parts[2] else 9
                buy_th = int(parts[3]) if len(parts) > 3 and parts[3] else None
                sell_th = int(parts[4]) if len(parts) > 4 and parts[4] else None
                stocks.append((sid, name, kp, buy_th, sell_th))
    return stocks

ALL_STOCKS = load_watchlist()
STOCK_DICT = {sid: {"name": n, "kp": k, "bt": b, "st": s} for sid, n, k, b, s in ALL_STOCKS}


# ============================================================
# 單一股票即時狀態機
# ============================================================
class StockRealtimeKD:
    """
    管理一支股票的即時KD狀態
    - 啟動時載入歷史30分K並建立KD基準
    - tick 進來時更新當前30分K的即時 OHLC
    - 即時重算 KD
    """
    def __init__(self, sid, name, k_period, buy_th, sell_th):
        self.sid = sid
        self.name = name
        self.kp = k_period
        self.buy_th = buy_th
        self.sell_th = sell_th

        # ── 歷史30分K（完整的連續K棒，含KD） ──
        self.hist_30k = None       # DataFrame, index=datetime, cols=[open,high,low,close,volume,K,D]

        # ── 當前正在形成的30分K（tick 持續更新） ──
        self.current_bar = {
            "open": None, "high": None, "low": None,
            "close": None, "volume": 0,
            "first_tick_time": None, "last_tick_time": None,
        }

        # ── 即時KD值（會隨 tick 更新） ──
        self.K = 50.0
        self.D = 50.0
        self.K_prev = 50.0
        self.D_prev = 50.0
        self.K_slope = 0.0
        self.K_slope_prev = 0.0
        self.D_slope = 0.0
        self.kd_distance = 0.0
        self.kd_distance_prev = 0.0

        # ── 狀態機 ──
        self.signal_state = "NONE"
        self.last_alert_time = 0

        # ── Tick 計數器（統計用） ──
        self.tick_count = 0
        self.last_tick_time = 0
        self.last_tick_price = 0

        # ── 追蹤當日高低 ──
        self.day_high = 0
        self.day_low = 99999

        # ── 🐋 大戶動向統計（金額制：單筆>=100萬=大戶） ──
        self.big_buy_vol = 0       # 大單買進累積張數
        self.big_sell_vol = 0      # 大單賣出累積張數
        self.big_buy_amt = 0       # 大單買進累積金額（元）
        self.big_sell_amt = 0      # 大單賣出累積金額（元）
        self.big_buy_cnt = 0       # 大單買進筆數
        self.big_sell_cnt = 0      # 大單賣出筆數
        self.small_buy_vol = 0     # 散戶買進累積張數
        self.small_sell_vol = 0    # 散戶賣出累積張數
        self.small_buy_amt = 0     # 散戶買進累積金額
        self.small_sell_amt = 0    # 散戶賣出累積金額
        self.trade_avg_size = 0.0  # 平均每筆張數
        self.trade_avg_amt = 0     # 平均每筆金額

        # ── 🐋 大戶累計區間 (每30分K重置) ──
        self.whale_net = 0         # 大戶淨買超張數
        self.whale_net_amt = 0     # 大戶淨買超金額
        self.whale_buy_pct = 0.0   # 大戶流入佔比 (%) — 跟APP那張圖一樣
        self.whale_sell_pct = 0.0  # 大戶流出佔比 (%)
        self.retail_buy_pct = 0.0  # 散戶買入佔比
        self.retail_sell_pct = 0.0 # 散戶賣出佔比

        # ── 歷史是否已載入 ──
        self.ready = False

    # ────────────────────────────────────────
    # 載入歷史
    # ────────────────────────────────────────
    def load_history(self, api):
        """啟動時載入20天歷史，建立KD基準"""
        try:
            contract = api.Contracts.Stocks[self.sid]
        except:
            return False

        end = datetime.now()
        start = end - timedelta(days=20)
        all_dfs = []
        seg_end = end

        while seg_end > start:
            seg_start = max(seg_end - timedelta(days=29), start)
            try:
                kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
                if len(kbars.ts) == 0:
                    seg_end = seg_start - timedelta(seconds=1)
                    continue
                df = pd.DataFrame({
                    "datetime": pd.to_datetime(kbars.ts),
                    "open": kbars.Open, "high": kbars.High,
                    "low": kbars.Low, "close": kbars.Close,
                    "volume": kbars.Volume,
                })
                all_dfs.append(df)
                seg_end = seg_start - timedelta(seconds=1)
            except:
                break

        if not all_dfs:
            return False

        raw = pd.concat(all_dfs)
        raw.drop_duplicates(subset=["datetime"], inplace=True)
        raw.sort_values("datetime", inplace=True)
        raw.set_index("datetime", inplace=True)

        df_30 = raw.resample("30min").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna()
        df_30 = df_30.between_time("09:00", "13:30")

        if len(df_30) < self.kp + 5:
            return False

        # 計算KD
        close = df_30["close"].values
        low = df_30["low"].values
        high = df_30["high"].values
        n = len(close)

        low_min = pd.Series(low).rolling(self.kp).min().values
        high_max = pd.Series(high).rolling(self.kp).max().values
        denom = high_max - low_min
        rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50.0)

        k_vals = np.full(n, 50.0)
        d_vals = np.full(n, 50.0)
        for i in range(self.kp, n):
            k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
            d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
            k_vals[i] = k_new
            d_vals[i] = d_new

        df_30["K"] = k_vals
        df_30["D"] = d_vals
        self.hist_30k = df_30

        # 取最後的KD
        last = df_30.iloc[-1]
        self.K = float(last["K"])
        self.D = float(last["D"])
        if len(df_30) >= 2:
            prev = df_30.iloc[-2]
            self.K_prev = float(prev["K"])
            self.D_prev = float(prev["D"])

        # 載入當日1分K（補上開盤到現在的數據）
        self._load_today_bars(api, contract)

        self.ready = True
        return True

    def _load_today_bars(self, api, contract):
        """載入當日1分K，初始化 current_bar"""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            kbars = api.kbars(contract=contract, start=today, end=today)
            if len(kbars.ts) == 0:
                return
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume,
            })
            df.set_index("datetime", inplace=True)
            df = df.between_time("09:00", "13:30")

            # 找出最後一個1分K的所屬30分K區間
            current_30min = self._get_30min_floor(datetime.now())
            relevant = df[df.index >= current_30min]

            if len(relevant) > 0:
                self.current_bar["open"] = float(relevant.iloc[0]["open"])
                self.current_bar["high"] = float(relevant["high"].max())
                self.current_bar["low"] = float(relevant["low"].min())
                self.current_bar["close"] = float(relevant.iloc[-1]["close"])
                self.current_bar["volume"] = int(relevant["volume"].sum())
                self.current_bar["first_tick_time"] = relevant.index[0]
                self.current_bar["last_tick_time"] = relevant.index[-1]

            # 追蹤當日高低
            self.day_high = float(df["high"].max())
            self.day_low = float(df["low"].min())
        except:
            pass

    def _get_30min_floor(self, dt):
        """回傳 dt 所屬的30分K起始時間"""
        minute = dt.minute // 30 * 30
        return dt.replace(minute=minute, second=0, microsecond=0)

    # ────────────────────────────────────────
    # Tick 驅動
    # ────────────────────────────────────────
    def on_tick(self, tick):
        """
        Shioaji tick callback 進來時呼叫
        tick 物件屬性: code, datetime, close, volume, bid_price, ask_price, ...
        """
        self.tick_count += 1
        self.last_tick_time = time.time()
        self.last_tick_price = tick.close

        # 更新當前30分K
        bar = self.current_bar
        if bar["open"] is None:
            bar["open"] = tick.close
            bar["high"] = tick.close
            bar["low"] = tick.close
            bar["close"] = tick.close
            bar["first_tick_time"] = datetime.now()
        else:
            if tick.close > bar["high"]:
                bar["high"] = tick.close
            if tick.close < bar["low"]:
                bar["low"] = tick.close
            bar["close"] = tick.close

        if hasattr(tick, 'volume') and tick.volume:
            bar["volume"] += tick.volume

        bar["last_tick_time"] = datetime.now()

        # ── 🐋 大戶動向：每筆 tick 分析 ──
        self._analyze_tick_whale(tick)

        # 更新當日高低
        if tick.close > self.day_high:
            self.day_high = tick.close
        if tick.close < self.day_low:
            self.day_low = tick.close

        # 即時重算 KD
        self._recalc_kd()

    def _recalc_kd(self):
        """用歷史30分K + 當前最新tick close，即時重算 KD"""
        if self.hist_30k is None or len(self.hist_30k) < self.kp + 2:
            return

        # 建立計算用的陣列：歷史完整K棒 + 當前未完成K棒（用 current_bar.close）
        hist_close = self.hist_30k["close"].values
        hist_low = self.hist_30k["low"].values
        hist_high = self.hist_30k["high"].values

        tick_close = self.current_bar["close"]
        tick_low = self.current_bar["low"] if self.current_bar["low"] is not None else tick_close
        tick_high = self.current_bar["high"] if self.current_bar["high"] is not None else tick_close

        close_arr = np.append(hist_close, tick_close)
        low_arr = np.append(hist_low, tick_low)
        high_arr = np.append(hist_high, tick_high)

        n = len(close_arr)
        low_min = pd.Series(low_arr).rolling(self.kp).min().values
        high_max = pd.Series(high_arr).rolling(self.kp).max().values
        denom = high_max - low_min
        rsv = np.where(denom != 0, ((close_arr - low_min) / denom) * 100, 50.0)

        k_vals = np.full(n, 50.0)
        d_vals = np.full(n, 50.0)
        for i in range(self.kp, n):
            k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
            d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
            k_vals[i] = k_new
            d_vals[i] = d_new

        # 更新
        self.K_prev = self.K
        self.D_prev = self.D
        self.kd_distance_prev = self.kd_distance
        self.K = float(k_vals[-1])
        self.D = float(d_vals[-1])
        self.kd_distance = round(abs(self.K - self.D), 2)

        # 即時 RSI
        self.RSI_prev = self.RSI
        rsi_arr = self._compute_rsi(close_arr)
        self.RSI = round(float(rsi_arr[-1]), 1) if not pd.isna(rsi_arr[-1]) else self.RSI
        self._update_rsi_status()

        # 斜率（用歷史最近3根不含當前的K值）
        if len(k_vals) >= SLOPE_WINDOW + 2:
            recent_k = k_vals[-(SLOPE_WINDOW+1):-1]
            self.K_slope_prev = self.K_slope
            if np.std(recent_k) > 0:
                self.K_slope = float(np.polyfit(np.arange(SLOPE_WINDOW), recent_k, 1)[0])
            else:
                self.K_slope = 0.0
            recent_d = d_vals[-(SLOPE_WINDOW+1):-1]
            if np.std(recent_d) > 0:
                self.D_slope = float(np.polyfit(np.arange(SLOPE_WINDOW), recent_d, 1)[0])
            else:
                self.D_slope = 0.0

    # ────────────────────────────────────────
    # 30分K換棒（跨週期）
    # ────────────────────────────────────────
    def finalize_bar(self):
        """
        當30分K時間到，把 current_bar 寫入 hist_30k
        """
        if self.current_bar["open"] is None or self.hist_30k is None:
            return

        new_idx = self._get_30min_floor(self.current_bar["last_tick_time"] or datetime.now())
        if new_idx in self.hist_30k.index:
            return  # 已存在

        new_row = pd.DataFrame([{
            "open": self.current_bar["open"],
            "high": self.current_bar["high"],
            "low": self.current_bar["low"],
            "close": self.current_bar["close"],
            "volume": self.current_bar["volume"],
        }], index=[new_idx])
        new_row.index.name = "datetime"

        self.hist_30k = pd.concat([self.hist_30k, new_row])
        self.hist_30k = self.hist_30k[~self.hist_30k.index.duplicated(keep='last')]
        self.hist_30k.sort_index(inplace=True)

        # 重算完整的KD序列（包含新K棒）
        self._recompute_full_kd()

        # 重置 current_bar + 大戶區間統計
        self.reset_whale_stats()
        self.current_bar = {
            "open": None, "high": None, "low": None,
            "close": None, "volume": 0,
            "first_tick_time": None, "last_tick_time": None,
        }

    def _recompute_full_kd(self):
        """完整重算所有K棒的KD（換棒時）"""
        if self.hist_30k is None or len(self.hist_30k) < self.kp + 2:
            return

        close = self.hist_30k["close"].values
        low = self.hist_30k["low"].values
        high = self.hist_30k["high"].values
        n = len(close)

        low_min = pd.Series(low).rolling(self.kp).min().values
        high_max = pd.Series(high).rolling(self.kp).max().values
        denom = high_max - low_min
        rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50.0)

        k_vals = np.full(n, 50.0)
        d_vals = np.full(n, 50.0)
        for i in range(self.kp, n):
            k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
            d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
            k_vals[i] = k_new
            d_vals[i] = d_new

        self.hist_30k["K"] = k_vals
        self.hist_30k["D"] = d_vals

        last = self.hist_30k.iloc[-1]
        self.K = float(last["K"])
        self.D = float(last["D"])
        if len(self.hist_30k) >= 2:
            prev = self.hist_30k.iloc[-2]
            self.K_prev = float(prev["K"])
            self.D_prev = float(prev["D"])

        # 補上 RSI
        rsi_vals = self._compute_rsi(close)
        self.hist_30k["RSI"] = rsi_vals
        self.RSI = float(rsi_vals[-1]) if not pd.isna(rsi_vals[-1]) else self.RSI
        if len(rsi_vals) >= 2:
            self.RSI_prev = float(rsi_vals[-2]) if not pd.isna(rsi_vals[-2]) else self.RSI_prev

    def _compute_rsi(self, close_prices):
        """計算 14 週期 RSI，回傳 array"""
        n = len(close_prices)
        rsi = np.full(n, 50.0)
        if n < self.RSI_period + 1:
            return rsi
        deltas = np.diff(close_prices)
        for i in range(self.RSI_period, n):
            gains = sum(d for d in deltas[i-self.RSI_period:i] if d > 0)
            losses = sum(-d for d in deltas[i-self.RSI_period:i] if d < 0)
            avg_gain = gains / self.RSI_period
            avg_loss = losses / self.RSI_period
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def _update_rsi_status(self):
        """更新 RSI 狀態旗標"""
        rsi = getattr(self, 'RSI', 50.0) or 50.0
        self.rsi_bullish = rsi >= 50
        self.rsi_oversold = rsi <= 38
        self.rsi_overbought = rsi >= 75
        self.rsi_extreme = rsi >= 80

    # ────────────────────────────────────────
    # 🐋 大戶 Tick 分析
    # ────────────────────────────────────────
    def _analyze_tick_whale(self, tick):
        """
        每筆 Tick 拆解：大戶還是散戶？
        
        門檻：單筆成交金額 >= 100 萬 = 大戶
        金額 = tick.close（成交價）× tick.volume（張數）× 1000（股）
        
        從 TickSTKv1 可以拿到:
          - tick.close: 成交價
          - tick.volume: 這筆成交張數
          - tick.tick_type: 買賣別 (0=買, 1=賣, 2=中性)
        """
        vol = getattr(tick, 'volume', 0) or 0
        price = getattr(tick, 'close', 0) or 0
        tick_type = getattr(tick, 'tick_type', None)
        
        if vol <= 0 or price <= 0:
            return
        
        amt = price * vol * 1000  # 成交金額（元）
        is_big = amt >= 1_000_000  # 大戶：單筆 >= 100 萬
        
        # 買賣別判定
        if tick_type == 0:  # 買（外盤）
            if is_big:
                self.big_buy_vol += vol
                self.big_buy_amt += amt
                self.big_buy_cnt += 1
                self.whale_net += vol
                self.whale_net_amt += amt
            else:
                self.small_buy_vol += vol
                self.small_buy_amt += amt
        elif tick_type == 1:  # 賣（內盤）
            if is_big:
                self.big_sell_vol += vol
                self.big_sell_amt += amt
                self.big_sell_cnt += 1
                self.whale_net -= vol
                self.whale_net_amt -= amt
            else:
                self.small_sell_vol += vol
                self.small_sell_amt += amt
        # tick_type=2 或 None 不歸邊
        
    def _update_whale_metrics(self):
        """更新大戶統計指標（在 analyze 前呼叫）— 跟APP那張圓餅圖一樣"""
        total_big = self.big_buy_amt + self.big_sell_amt
        total_small = self.small_buy_amt + self.small_sell_amt
        total_all = total_big + total_small
        
        if total_big > 0:
            self.whale_buy_pct = round(self.big_buy_amt / total_big * 100, 2)
            self.whale_sell_pct = round(self.big_sell_amt / total_big * 100, 2)
        if total_all > 0:
            self.retail_buy_pct = round(self.small_buy_amt / total_all * 100, 2)
            self.retail_sell_pct = round(self.small_sell_amt / total_all * 100, 2)
            self.trade_avg_amt = round(total_all / max(self.tick_count, 1))
        
        total_vol = self.big_buy_vol + self.big_sell_vol + self.small_buy_vol + self.small_sell_vol
        if total_vol > 0 and self.tick_count > 0:
            self.trade_avg_size = round(total_vol / self.tick_count, 1)
    
    def reset_whale_stats(self):
        """每30分K換棒時重置大戶區間統計"""
        self.whale_net = 0
        self.whale_net_amt = 0
        self.whale_buy_pct = 0.0
        self.whale_sell_pct = 0.0
        self.retail_buy_pct = 0.0
        self.retail_sell_pct = 0.0
        self.big_buy_vol = 0
        self.big_sell_vol = 0
        self.big_buy_amt = 0
        self.big_sell_amt = 0
        self.big_buy_cnt = 0
        self.big_sell_cnt = 0
        self.small_buy_vol = 0
        self.small_sell_vol = 0
        self.small_buy_amt = 0
        self.small_sell_amt = 0

    # ────────────────────────────────────────
    # 分析 + 預警判斷
    # ────────────────────────────────────────
    def analyze(self):
        """
        回傳當前KD分析結果（dict 或 None）
        
        預警條件（需雙重確認才亮燈）：
        🟢 買入：KD金叉 + 大戶買超 (whale_net > 0 或 whale_ratio > 0.55)
        🔴 賣出：KD死叉 + 大戶賣超 (whale_net < 0 或 whale_ratio < 0.45)
        """
        self._update_whale_metrics()
        
        k_now = round(self.K, 2)
        d_now = round(self.D, 2)
        k_prev = round(self.K_prev, 2)
        d_prev = round(self.D_prev, 2)

        zone = "NORMAL"
        if k_now <= 30:
            zone = "OVERSOLD_LOW"
        elif k_now >= 85:
            zone = "EXTREME_HIGH"
        elif k_now >= 70:
            zone = "OVERBOUGHT_HIGH"

        golden_now = k_prev <= d_prev and k_now > d_now
        death_now = k_prev >= d_prev and k_now < d_now
        is_golden = k_now > d_now
        is_death = k_now < d_now
        dist_shrinking = (self.kd_distance < self.kd_distance_prev
                          if self.kd_distance_prev > 0 else False)

        # ── RSI 狀態 ──
        rsi_now = round(getattr(self, 'RSI', 50.0), 1)
        self._update_rsi_status()

        # ── 預警判斷 ──
        pre_golden = False
        pre_death = False
        alert_reason = ""

        # ⚡ 預警純 KD 邏輯（大戶資訊僅供顯示，不卡條件）
        # 低檔金叉預警（第25~29分鐘）
        if zone == "OVERSOLD_LOW":
            turning_up = self.K_slope > UPWARD_SLOPE_MIN and self.K_slope_prev <= 0
            close_to_cross = self.kd_distance < PREMATURE_DISTANCE and dist_shrinking
            still_death = k_now <= d_now
            if turning_up and close_to_cross and still_death:
                pre_golden = True
                alert_reason = "動能拐頭預警"

        # 高檔死叉預警（第25~29分鐘）
        if zone in ("OVERBOUGHT_HIGH", "EXTREME_HIGH"):
            fading = self.K_slope < self.K_slope_prev
            close_to_death = self.kd_distance < PREMATURE_DISTANCE and dist_shrinking
            still_golden = k_now >= d_now
            if fading and close_to_death and still_golden:
                pre_death = True
                alert_reason = "動能衰竭預警"

        return {
            "sid": self.sid,
            "name": self.name,
            "kp": self.kp,
            "K": k_now, "D": d_now,
            "K_slope": round(self.K_slope, 2),
            "D_slope": round(self.D_slope, 2),
            "KD_distance": self.kd_distance,
            "zone": zone,
            "is_golden": is_golden, "is_death": is_death,
            "golden_now": golden_now, "death_now": death_now,
            "pre_golden": pre_golden, "pre_death": pre_death,
            "alert_reason": alert_reason,
            "tick_count": self.tick_count,
            "price": self.current_bar["close"],
            # RSI（僅供顯示，不參與盤中決策）
            "RSI": rsi_now,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "rsi_extreme": self.rsi_extreme,
            # 🐋 大戶資訊（從 Tick 直接取 — 跟APP圓餅圖一樣）
            "whale_net": self.whale_net,
            "whale_net_amt": self.whale_net_amt,
            "whale_buy_pct": self.whale_buy_pct,
            "whale_sell_pct": self.whale_sell_pct,
            "retail_buy_pct": self.retail_buy_pct,
            "retail_sell_pct": self.retail_sell_pct,
            "whale_buy_vol": self.big_buy_vol,
            "whale_sell_vol": self.big_sell_vol,
            "whale_buy_amt": self.big_buy_amt,
            "whale_sell_amt": self.big_sell_amt,
            "trade_avg_size": self.trade_avg_size,
            "trade_avg_amt": self.trade_avg_amt,
        }


# ============================================================
# 提醒產生器
# ============================================================
def build_alert(r):
    # 🐋 大戶資金流向（盤中核心）
    if r["whale_net_amt"] != 0:
        whale_dir = "🐋大戶買" if r["whale_net_amt"] > 0 else "🐻大戶賣"
        amt_str = f"{abs(r['whale_net_amt'])/10000:.0f}萬"
        whale_line = f"{whale_dir}{amt_str} (流入{r['whale_buy_pct']:.0f}% / 流出{r['whale_sell_pct']:.0f}%)"
    else:
        whale_line = f"均量{r['trade_avg_size']}張/筆 | 均額{r['trade_avg_amt']/1000:.0f}K"
    avg_line = f"tick:{r['tick_count']}筆 RSI{r.get('RSI',50)}"

    if r["golden_now"]:
        return (f"🔴 買入！買入！\n"
                f"━━━━━━━━━━━━━\n"
                f"{r['name']}({r['sid']}) @{r['price']}\n"
                f"30分K KD黃金交叉確認！K={r['K']:.1f} 穿 D={r['D']:.1f}\n"
                f"{whale_line}\n"
                f"{avg_line}\n"
                f"━━━━━━━━━━━━━\n"
                f"小龍蝦即時亮燈：買入訊號！")
    if r["death_now"]:
        return (f"🟢 賣出！賣出！\n"
                f"━━━━━━━━━━━━━\n"
                f"{r['name']}({r['sid']}) @{r['price']}\n"
                f"30分K KD死亡交叉確認！K={r['K']:.1f} 跌破 D={r['D']:.1f}\n"
                f"{whale_line}\n"
                f"{avg_line}\n"
                f"━━━━━━━━━━━━━\n"
                f"小龍蝦即時亮燈：賣出訊號！")
    if r["pre_golden"]:
        return (f"🦞 動能拐頭預警！{r['name']}\n"
                f"━━━━━━━━━━━━━\n"
                f"K={r['K']:.1f} D={r['D']:.1f} 距離{r['KD_distance']:.1f}\n"
                f"斜率+{r['K_slope']:.2f} 往上拐了！\n"
                f"{whale_line}\n"
                f"{avg_line}\n"
                f"━━━━━━━━━━━━━\n"
                f"小龍蝦提醒：準備低接！")
    if r["pre_death"]:
        return (f"🦞 動能衰竭預警！{r['name']}\n"
                f"━━━━━━━━━━━━━\n"
                f"K={r['K']:.1f} D={r['D']:.1f} 距離{r['KD_distance']:.1f}\n"
                f"斜率{r['K_slope']:.2f} 動能減弱了\n"
                f"{whale_line}\n"
                f"{avg_line}\n"
                f"━━━━━━━━━━━━━\n"
                f"小龍蝦提醒：準備賣出！")
    return None


# ============================================================
# 即時引擎
# ============================================================
class LobsterRealtimeEngine:
    def __init__(self):
        self.stocks = {}        # sid -> StockRealtimeKD
        self.api = None
        self.running = False

        # 換棒監控
        self._last_bar_minute = -1

        # 統計
        self.total_ticks = 0
        self.start_time = None

    def start(self):
        """啟動引擎"""
        print(f"\n{'='*60}")
        print(f"  🦞 小龍蝦即時 Tick 預警引擎 v2")
        print(f"  啟動: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  監控: {len(ALL_STOCKS)} 支")
        print(f"{'='*60}")

        # 登入
        self.api = sj.Shioaji(simulation=True)
        self.api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
        print(f"  ✅ Shioaji 登入成功")
        self.start_time = datetime.now()

        # 載入歷史
        print(f"\n  📥 載入歷史30分K KD...")
        ok_count = 0
        for sid, info in STOCK_DICT.items():
            mgr = StockRealtimeKD(sid, info["name"], info["kp"], info["bt"], info["st"])
            if mgr.load_history(self.api):
                self.stocks[sid] = mgr
                ok_count += 1
        print(f"  ✅ {ok_count}/{len(ALL_STOCKS)} 支歷史載入完成")

        # 設定 Tick 回調
        self.api.set_on_tick_stk_v1_callback(self._on_tick)

        # 訂閱 Tick
        print(f"\n  📡 訂閱 Tick 即時行情...")
        sub_ok = 0
        for sid in self.stocks:
            try:
                contract = self.api.Contracts.Stocks[sid]
                self.api.subscribe(contract, quote_type='tick', version='v1')
                sub_ok += 1
            except:
                pass
        print(f"  ✅ {sub_ok} 支 Tick 訂閱完成")

        # 顯示即時KD起點 + 初始狀態通知
        print(f"\n  📊 初始KD狀態：")
        for sid, mgr in list(self.stocks.items())[:5]:
            print(f"    {mgr.name}({sid}) K={mgr.K:.1f} D={mgr.D:.1f}")
        print(f"    ... 共{len(self.stocks)}支")
        
        # 初始狀態通知：已經在交叉狀態的股票
        initial_alerts = []
        now_ts = time.time()
        for sid, mgr in self.stocks.items():
            rt = mgr.analyze()
            if rt and (rt["is_golden"] or rt["is_death"]):
                cross_type = "金叉🟢" if rt["is_golden"] else "死叉🔴"
                msg = (f"📢 初始狀態通知\n"
                       f"━━━━━━━━━━━━━\n"
                       f"{mgr.name}({sid}) @{rt['price']}\n"
                       f"30分K {cross_type} K={rt['K']:.1f} D={rt['D']:.1f}\n"
                       f"━━━━━━━━━━━━━\n"
                       f"小龍蝦：啟動時已處於交叉狀態！")
                initial_alerts.append(msg)
                if rt["is_golden"]:
                    mgr.signal_state = "GOLDEN"
                else:
                    mgr.signal_state = "DEATH"
                mgr.last_alert_time = now_ts
                print(f"\n{'='*60}")
                print(f"  📢 {rt['name']}({rt['sid']}) 初始狀態：{cross_type}")
                print(f"{'='*60}")
                print(msg)
                print(f"{'='*60}")
                self._enqueue_alert(msg, mgr)
        
        # 主循環
        self.running = True
        print(f"\n  🚀 引擎啟動！等待 Tick 數據中...")
        print(f"  （盤中每筆成交即時更新，第25~30分鐘高頻預警）\n")
        self._main_loop()

    def _on_tick(self, exchange, tick):
        """Shioaji Tick Callback — 每筆成交即時進來"""
        sid = tick.code
        mgr = self.stocks.get(sid)
        if mgr is None:
            return

        self.total_ticks += 1
        mgr.on_tick(tick)

    def _main_loop(self):
        """主循環：管理換棒 + 定時檢查"""
        last_status_time = 0

        while self.running:
            try:
                now = datetime.now()
                now_ts = time.time()

                # 1. 檢查30分K換棒
                current_min = now.minute
                if current_min % 30 == 0 and current_min != self._last_bar_minute:
                    self._finalize_all_bars()
                    self._last_bar_minute = current_min

                # 2. 檢查是否需要高頻分析（第25~30分鐘）
                remainder = now.minute % 30
                if remainder >= 24:
                    self._check_all_alerts(now)

                # 3. 每30秒印一次狀態
                if now_ts - last_status_time >= 30:
                    if self.total_ticks > 0:
                        remaining = 30 - remainder - 1
                        mode = "🦞高頻預警" if remainder >= 24 else "🔍常態監控"
                        whales = sum(1 for m in self.stocks.values() if abs(m.whale_net) > 100)
                        print(f"  [{now.strftime('%H:%M:%S')}] {mode} | tick:{self.total_ticks} | 🐋{whales}支有大戶 | 距收K:{remaining}分")
                    last_status_time = now_ts

                time.sleep(0.3)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"  ❌ 循環錯誤: {e}")
                time.sleep(1)

        self._shutdown()

    def _finalize_all_bars(self):
        """30分K時間到，所有股票換棒"""
        for sid, mgr in self.stocks.items():
            try:
                mgr.finalize_bar()
            except:
                pass
        print(f"\n  🔄 [{datetime.now().strftime('%H:%M')}] 所有股票換棒完成")

    def _check_all_alerts(self, now):
        """檢查所有股票是否需要觸發預警"""
        now_ts = time.time()
        cooldown = 600  # 10分鐘

        for sid, mgr in self.stocks.items():
            try:
                # 跳過還沒有tick進來的
                if mgr.tick_count == 0:
                    continue

                result = mgr.analyze()
                if result is None:
                    continue

                alert_msg = None

                if result["golden_now"] and mgr.signal_state != "GOLDEN":
                    alert_msg = build_alert(result)
                    mgr.signal_state = "GOLDEN"
                    mgr.last_alert_time = now_ts

                elif result["death_now"] and mgr.signal_state != "DEATH":
                    alert_msg = build_alert(result)
                    mgr.signal_state = "DEATH"
                    mgr.last_alert_time = now_ts

                elif result["pre_golden"] and mgr.signal_state not in ("PRE_GOLDEN", "GOLDEN"):
                    if now_ts - mgr.last_alert_time > cooldown:
                        alert_msg = build_alert(result)
                        mgr.signal_state = "PRE_GOLDEN"
                        mgr.last_alert_time = now_ts

                elif result["pre_death"] and mgr.signal_state not in ("PRE_DEATH", "DEATH"):
                    if now_ts - mgr.last_alert_time > cooldown:
                        alert_msg = build_alert(result)
                        mgr.signal_state = "PRE_DEATH"
                        mgr.last_alert_time = now_ts

                if alert_msg:
                    print(f"\n{'='*60}")
                    print(f"  ⚠️ {now.strftime('%H:%M:%S')} {mgr.name}({mgr.sid})")
                    print(f"{'='*60}")
                    print(f"{alert_msg}")
                    print(f"{'='*60}\n")
                    # 同時寫入訊息佇列（供主session輪詢推送）
                    self._enqueue_alert(alert_msg, mgr)

            except:
                pass

    def _enqueue_alert(self, msg, mgr):
        """將預警訊息寫入佇列（含大戶資訊），供主session定時輪詢推送"""
        try:
            queue = []
            if os.path.exists(ALERT_QUEUE_FILE):
                with open(ALERT_QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            queue.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "sid": mgr.sid,
                "name": mgr.name,
                "K": round(mgr.K, 1),
                "D": round(mgr.D, 1),
                "RSI": round(mgr.RSI, 1),
                "rsi_oversold": mgr.rsi_oversold,
                "rsi_overbought": mgr.rsi_overbought,
                "whale_net_amt": mgr.whale_net_amt,
                "whale_buy_pct": mgr.whale_buy_pct,
                "whale_sell_pct": mgr.whale_sell_pct,
                "trade_avg_size": mgr.trade_avg_size,
                "trade_avg_amt": mgr.trade_avg_amt,
                "msg": msg,
            })
            # 保留最近50筆
            if len(queue) > 50:
                queue = queue[-50:]
            with open(ALERT_QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _shutdown(self):
        print(f"\n  🛑 引擎關閉")
        print(f"  運行時間: {datetime.now() - self.start_time}")
        print(f"  總計 Tick: {self.total_ticks}")
        if self.api:
            self.api.logout()
        print(f"  ✅ 安全關閉")


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    engine = LobsterRealtimeEngine()
    engine.start()
