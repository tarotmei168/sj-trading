#!/usr/bin/env python3
"""
calc_tech.py — 技術指標計算（100% 對齊 TradingView 預設參數）
================================================================
TradingView 預設:
  - Stochastic KD: %K Length=14, %K Smoothing=1, %D Smoothing=3  (SMA)
  - RSI: period=14, Wilder's RMA 平滑
  - MACD: fast=12, slow=26, signal=9, EMA

公式對應 Pine Script v5:
  k_raw = ta.stoch(close, high, low, 14)
  k     = ta.sma(k_raw, 1)   # smoothK=1 → 等同 k_raw
  d     = ta.sma(k, 3)
  rsi   = ta.rsi(close, 14)
  [macd, signal, hist] = ta.macd(close, 12, 26, 9)

資料來源:
  - database/3y_kd/代號_kd.csv (30分K KD預算結果)
  - database/代號_3y.csv (舊日K, legacy)
"""

import os
import csv
import numpy as np

# ─── TradingView 標準參數（勿改，除非 TradingView 改預設）───
TV_STOCH_K_LEN = 14
TV_STOCH_K_SMOOTH = 1
TV_STOCH_D_SMOOTH = 3
TV_RSI_PERIOD = 14
TV_MACD_FAST = 12
TV_MACD_SLOW = 26
TV_MACD_SIGNAL = 9

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_DIR = os.path.join(BASE_DIR, 'database')
KD3_DIR = os.path.join(DB_DIR, '3y_kd')


# ═══════════════════════════════════════════════════════════
#  Pine Script 等價基礎函式
# ═══════════════════════════════════════════════════════════

def _tv_sma(arr: np.ndarray, period: int) -> np.ndarray:
    """TradingView ta.sma — Simple Moving Average."""
    n = len(arr)
    out = np.full(n, np.nan)
    if period < 1:
        return out
    for i in range(period - 1, n):
        window = arr[i - period + 1:i + 1]
        if np.all(np.isfinite(window)):
            out[i] = np.mean(window)
    return out


def _tv_ema(arr: np.ndarray, period: int) -> np.ndarray:
    """TradingView ta.ema — 首值用 SMA 種子，之後 EMA 遞推."""
    n = len(arr)
    out = np.full(n, np.nan)
    if period < 1 or n < period:
        return out
    alpha = 2.0 / (period + 1)
    # 跳過前面的 NaN，從第一個有效值開始取 period 個當 seed
    first_valid = 0
    while first_valid < n and not np.isfinite(arr[first_valid]):
        first_valid += 1
    seed_end = first_valid + period
    if seed_end > n:
        return out
    seed = arr[first_valid:seed_end]
    if not np.all(np.isfinite(seed)):
        return out
    out[seed_end - 1] = np.mean(seed)
    for i in range(seed_end, n):
        if not np.isfinite(arr[i]):
            continue
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def _tv_rma(arr: np.ndarray, period: int) -> np.ndarray:
    """TradingView ta.rma (Wilder's smoothing) — RSI/MFI 用."""
    n = len(arr)
    out = np.full(n, np.nan)
    if period < 1 or n < period:
        return out
    alpha = 1.0 / period
    seed = arr[:period]
    if not np.all(np.isfinite(seed)):
        return out
    out[period - 1] = np.mean(seed)
    for i in range(period, n):
        if not np.isfinite(arr[i]):
            continue
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def _as_f64(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64)


# ═══════════════════════════════════════════════════════════
#  公開 API — KD / RSI / MACD
# ═══════════════════════════════════════════════════════════

def calc_STOCH(
    high, low, close,
    fastk: int = TV_STOCH_K_LEN,
    slowk: int = TV_STOCH_K_SMOOTH,
    slowd: int = TV_STOCH_D_SMOOTH,
):
    """
    Stochastic KD — 100% 對齊 TradingView Stoch(14,1,3).
    回傳 (k_arr, d_arr)，與 TA-Lib STOCH(..., slowk_matype=0, slowd_matype=0) 一致。
    """
    high = _as_f64(high)
    low = _as_f64(low)
    close = _as_f64(close)
    n = len(close)
    raw_k = np.full(n, np.nan)

    for i in range(fastk - 1, n):
        hh = np.max(high[i - fastk + 1:i + 1])
        ll = np.min(low[i - fastk + 1:i + 1])
        if hh - ll == 0:
            raw_k[i] = np.nan
        else:
            raw_k[i] = 100.0 * (close[i] - ll) / (hh - ll)

    if slowk <= 1:
        k = raw_k.copy()
    else:
        k = _tv_sma(raw_k, slowk)

    d = _tv_sma(k, slowd)
    return k, d


def calc_RSI(closes, period: int = TV_RSI_PERIOD) -> np.ndarray:
    """
    RSI — 100% 對齊 TradingView ta.rsi(close, 14).
    回傳完整 rsi 陣列；取最後值: calc_RSI_last(closes)
    """
    closes = _as_f64(closes)
    n = len(closes)
    rsi = np.full(n, np.nan)
    if n < period + 1:
        return rsi

    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    avg_gain = _tv_rma(gain, period)
    avg_loss = _tv_rma(loss, period)

    # gain/loss 比 close 少 1 根；RMA[i] 對應 close[i+1]
    for i in range(period, n):
        gi = i - 1
        ag = avg_gain[gi]
        al = avg_loss[gi]
        if not np.isfinite(ag) or not np.isfinite(al):
            continue
        if al == 0:
            rsi[i] = 100.0
        elif ag == 0:
            rsi[i] = 0.0
        else:
            rs = ag / al
            rsi[i] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def calc_RSI_last(closes, period: int = TV_RSI_PERIOD) -> float:
    """回傳最後一根 K 的 RSI 值（TradingView 標準）."""
    arr = calc_RSI(closes, period)
    if len(arr) == 0 or not np.isfinite(arr[-1]):
        return 50.0
    return round(float(arr[-1]), 1)


def calc_MACD(
    closes,
    fast: int = TV_MACD_FAST,
    slow: int = TV_MACD_SLOW,
    signal: int = TV_MACD_SIGNAL,
):
    """
    MACD — 100% 對齊 TradingView ta.macd(close, 12, 26, 9).
    回傳 (macd_line, signal_line, histogram)
    """
    closes = _as_f64(closes)
    ema_fast = _tv_ema(closes, fast)
    ema_slow = _tv_ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _tv_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def apply_indicators(df, prefix: str = ""):
    """
    對 OHLCV DataFrame 附加 K/D/MACD/RSI 欄位（TradingView 標準）。
    需要欄位: open, high, low, close, volume（大小寫不敏感）。
    回傳 copy 後的 DataFrame。
    """
    import pandas as pd

    out = df.copy()
    cols = {c.lower(): c for c in out.columns}
    close = _as_f64(out[cols['close']])
    high = _as_f64(out[cols['high']])
    low = _as_f64(out[cols['low']])

    k, d = calc_STOCH(high, low, close)
    macd, sig, hist = calc_MACD(close)
    rsi = calc_RSI(close)

    p = prefix
    out[f'{p}K'] = np.round(k, 2)
    out[f'{p}D'] = np.round(d, 2)
    out[f'{p}MACD'] = macd
    out[f'{p}MACD_signal'] = sig
    out[f'{p}MACD_hist'] = hist
    out[f'{p}RSI'] = np.round(rsi, 2)
    return out


def calc_all_last(close, high, low, volume=None) -> dict:
    """一次算出最新一根 K 的全部指標（供引擎/監控使用）."""
    close = _as_f64(close)
    high = _as_f64(high)
    low = _as_f64(low)

    k_arr, d_arr = calc_STOCH(high, low, close)
    macd_arr, sig_arr, hist_arr = calc_MACD(close)
    rsi_arr = calc_RSI(close)

    def _last(arr, default=0.0):
        if len(arr) == 0 or not np.isfinite(arr[-1]):
            return default
        return float(arr[-1])

    def _prev(arr, default=0.0):
        if len(arr) < 2 or not np.isfinite(arr[-2]):
            return default
        return float(arr[-2])

    return {
        'k': round(_last(k_arr, 50.0), 1),
        'd': round(_last(d_arr, 50.0), 1),
        'k_prev': round(_prev(k_arr, _last(k_arr, 50.0)), 1),
        'rsi': round(_last(rsi_arr, 50.0), 1),
        'macd': round(_last(macd_arr, 0.0), 2),
        'macd_signal': round(_last(sig_arr, 0.0), 2),
        'macd_hist': round(_last(hist_arr, 0.0), 2),
        'macd_hist_prev': round(_prev(hist_arr, _last(hist_arr, 0.0)), 2),
        'k_arr': k_arr,
        'd_arr': d_arr,
        'macd_hist_arr': hist_arr,
        'rsi_arr': rsi_arr,
    }


# 向後相容別名（舊程式 import compute_kd 時自動走 TradingView 標準）
compute_kd = calc_STOCH


# ═══════════════════════════════════════════════════════════
#  資料讀取（legacy）
# ═══════════════════════════════════════════════════════════

def read_local_csv(stock_id):
    """優先 3y_kd，回退 3y 日K."""
    rows = read_3ykd_csv(stock_id)
    if rows:
        return rows
    path = os.path.join(DB_DIR, f'{stock_id}_3y.csv')
    return _read_csv(path)


def _read_csv(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        for r in rows:
            for k in ['open', 'high', 'low', 'close', 'volume']:
                if k in r:
                    r[k] = float(r[k]) if r[k] else 0.0
        return rows
    except Exception as e:
        print(f'  [calc_tech] 讀取 {path} 失敗: {e}')
        return None


def read_3ykd_csv(stock_id):
    path = os.path.join(KD3_DIR, f'{stock_id}_kd.csv')
    return _read_csv(path)


def read_local_csv_deprecated(stock_id):
    rows = read_3ykd_csv(stock_id)
    if rows:
        return rows
    return read_local_csv(stock_id)


def get_latest_3ykd(stock_id):
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


def get_daily_ohlcv_from_3ykd(stock_id):
    rows = read_3ykd_csv(stock_id)
    if not rows:
        return None
    daily = {}
    for r in rows:
        dt_part = r['datetime'][:10]
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
            d['close'] = c
            d['volume'] += v
    sorted_dates = sorted(daily.keys())
    result = []
    for dt in sorted_dates:
        d = daily[dt]
        d['date'] = dt
        result.append(d)
    return result
