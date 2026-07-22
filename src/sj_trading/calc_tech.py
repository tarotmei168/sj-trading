#!/usr/bin/env python3
"""
calc_tech.py — 技術指標離線計算
================================
資料來源:
  - database/3y_kd/代號_kd.csv (30分K KD預算結果)
  - FinMind (盤後日K, 補 RSI 等指標)

依賴: read_local_csv → 讀本機 database/代號_3y.csv (舊日K模式, 可退場)
       read_3ykd_csv  → 讀 database/3y_kd/代號_kd.csv (新的30分K KD)
"""

import os, csv, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_DIR = os.path.join(BASE_DIR, 'database')
KD3_DIR = os.path.join(DB_DIR, '3y_kd')

# ─── 舊日K讀取（database/代號_3y.csv, legacy）───
def read_local_csv(stock_id):
    """
    優先從 database/3y_kd/代號_kd.csv 讀取（30分K KD）
    無則回退 database/代號_3y.csv（舊日K）
    """
    # 先試新的 30分K KD
    rows = read_3ykd_csv(stock_id)
    if rows:
        return rows
    # 回退舊日K
    path = os.path.join(DB_DIR, f'{stock_id}_3y.csv')
    return _read_csv(path)

def _read_csv(path):
    """通用 CSV DictReader 封裝"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        # 確保數值欄位轉 float
        for r in rows:
            for k in ['open','high','low','close','volume']:
                if k in r:
                    r[k] = float(r[k]) if r[k] else 0.0
        return rows
    except Exception as e:
        print(f'  [calc_tech] 讀取 {path} 失敗: {e}')
        return None

# ─── 新30分K KD讀取（database/3y_kd/代號_kd.csv）───
def read_3ykd_csv(stock_id):
    """從 database/3y_kd/代號_kd.csv 讀取30分K KD資料"""
    path = os.path.join(KD3_DIR, f'{stock_id}_kd.csv')
    return _read_csv(path)

def read_local_csv_deprecated(stock_id):
    """⚠️ 舊日K模式: 如果 3y_kd 有資料就讀新的, 否則回退舊的"""
    rows = read_3ykd_csv(stock_id)
    if rows:
        return rows
    return read_local_csv(stock_id)

# ─── TA-Lib 統一技術指標計算（TradingView 標準參數）───
# KD: Stoch(14,1,3) → K/D 線
# RSI: RSI(14)
# MACD: MACD(12,26,9) → MACD線/信號線/柱狀圖

def calc_STOCH(closes, lows, highs, fastk=14, slowk=1, slowd=3):
    """KD: TradingView Stoch(14,1,3)，回傳 (k_vals, d_vals)"""
    import numpy as np
    import talib
    closes = np.array(closes, dtype=float)
    highs = np.array(highs, dtype=float)
    lows = np.array(lows, dtype=float)
    k_vals, d_vals = talib.STOCH(highs, lows, closes,
                                  fastk_period=fastk,
                                  slowk_period=slowk,
                                  slowk_matype=0,  # SMA
                                  slowd_period=slowd,
                                  slowd_matype=0)  # SMA
    return k_vals, d_vals

def calc_RSI(closes, period=14):
    """RSI: talib.RSI(close, timeperiod=14)"""
    import numpy as np
    import talib
    closes = np.array(closes, dtype=float)
    rsi = talib.RSI(closes, timeperiod=period)
    if len(rsi) == 0:
        return 50.0
    return round(float(rsi[-1]), 1)

def calc_MACD(closes, fast=12, slow=26, signal=9):
    """MACD: talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    回傳 (macd_line, signal_line, histogram)"""
    import numpy as np
    import talib
    closes = np.array(closes, dtype=float)
    macd, signal, hist = talib.MACD(closes,
                                     fastperiod=fast,
                                     slowperiod=slow,
                                     signalperiod=signal)
    return macd, signal, hist

# ─── 從30分K KD取得最新技術指標 ───
def get_latest_3ykd(stock_id):
    """回傳 {k, d, price, close, high, low, volume} 或 None"""
    rows = read_3ykd_csv(stock_id)
    if not rows:
        return None
    last = rows[-1]
    return {
        'k': float(last['K']),
        'd': float(last['D']),
        'price': float(last['close']),
        'close': float(last['close']),
        'high': float(last.get('high', 0)),
        'low': float(last.get('low', 0)),
        'volume': int(float(last.get('volume', 0))),
    }

# ─── 每日 K 線 OHLCV 載入（備用）───
def get_daily_ohlcv_from_3ykd(stock_id):
    """從30分K KD資料夾還原每日OHLCV（取最後一根13:30當收盤價）"""
    rows = read_3ykd_csv(stock_id)
    if not rows:
        return None
    # 只要當天最後一根（13:30）當作日K
    daily = {}
    for r in rows:
        dt_part = r['datetime'][:10]  # YYYY-MM-DD
        c = float(r['close'])
        h = float(r['high'])
        l = float(r['low'])
        v = int(float(r['volume']))
        if dt_part not in daily:
            daily[dt_part] = {'open': float(r['open']), 'high': h, 'low': l,
                             'close': c, 'volume': v}
        else:
            d = daily[dt_part]
            d['high'] = max(d['high'], h)
            d['low'] = min(d['low'], l)
            d['close'] = c  # 用最後一根13:30收盤
            d['volume'] += v
    
    # 排序並轉成 list
    sorted_dates = sorted(daily.keys())
    result = []
    for dt in sorted_dates:
        d = daily[dt]
        d['date'] = dt
        result.append(d)
    return result
