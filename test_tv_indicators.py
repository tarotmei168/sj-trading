#!/usr/bin/env python3
"""驗證 calc_tech 與 TA-Lib / TradingView 參數一致性"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'sj_trading'))

import numpy as np
import talib
from calc_tech import calc_STOCH, calc_RSI, calc_MACD, TV_STOCH_K_LEN, TV_STOCH_K_SMOOTH, TV_STOCH_D_SMOOTH

np.random.seed(42)
n = 100
close = 100 + np.cumsum(np.random.randn(n) * 0.5)
high = close + np.abs(np.random.randn(n) * 0.3)
low = close - np.abs(np.random.randn(n) * 0.3)

# ── STOCH(14,1,3) ──
k_tv, d_tv = calc_STOCH(high, low, close)
k_tl, d_tl = talib.STOCH(high, low, close,
    fastk_period=TV_STOCH_K_LEN, slowk_period=TV_STOCH_K_SMOOTH, slowd_period=TV_STOCH_D_SMOOTH,
    slowk_matype=0, slowd_matype=0)

mask_k = np.isfinite(k_tv) & np.isfinite(k_tl)
mask_d = np.isfinite(d_tv) & np.isfinite(d_tl)
diff_k = np.max(np.abs(k_tv[mask_k] - k_tl[mask_k])) if mask_k.any() else 0
diff_d = np.max(np.abs(d_tv[mask_d] - d_tl[mask_d])) if mask_d.any() else 0
print(f"STOCH K max diff vs TA-Lib: {diff_k:.8f}  {'PASS' if diff_k < 1e-6 else 'FAIL'}")
print(f"STOCH D max diff vs TA-Lib: {diff_d:.8f}  {'PASS' if diff_d < 1e-6 else 'FAIL'}")
print(f"  Last K: TV={k_tv[-1]:.4f}  TL={k_tl[-1]:.4f}")
print(f"  Last D: TV={d_tv[-1]:.4f}  TL={d_tl[-1]:.4f}")

# ── RSI(14) ──
rsi_tv = calc_RSI(close)
rsi_tl = talib.RSI(close, timeperiod=14)
mask_r = np.isfinite(rsi_tv) & np.isfinite(rsi_tl)
diff_r = np.max(np.abs(rsi_tv[mask_r] - rsi_tl[mask_r])) if mask_r.any() else 0
print(f"RSI max diff vs TA-Lib:     {diff_r:.8f}  {'PASS' if diff_r < 0.01 else 'FAIL'}")
print(f"  Last RSI: TV={rsi_tv[-1]:.4f}  TL={rsi_tl[-1]:.4f}")

# ── MACD(12,26,9) ──
m_tv, s_tv, h_tv = calc_MACD(close)
m_tl, s_tl, h_tl = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
mask_m = np.isfinite(h_tv) & np.isfinite(h_tl)
diff_m = np.max(np.abs(h_tv[mask_m] - h_tl[mask_m])) if mask_m.any() else 0
print(f"MACD hist max diff vs TA-Lib: {diff_m:.8f}  {'PASS' if diff_m < 0.01 else 'FAIL'}")
print(f"  Last Hist: TV={h_tv[-1]:.4f}  TL={h_tl[-1]:.4f}")

# ── 已知 Binance 驗證資料 (GitHub TA-Lib issue #469) ──
close_b = np.array([3461.89,3459.25,3463.76,3466.51,3465.32,3466.79,3466.57,3467.98,
    3465.83,3468.68,3465.65,3469.43,3463.93,3469.35,3466.82,3467.95])
high_b = close_b + 2
low_b = close_b - 2
k_b, d_b = calc_STOCH(high_b, low_b, close_b)
print(f"\nBinance reference STOCH last K: {k_b[-1]:.7f} (expect ~68.0822827)")
print(f"Binance reference STOCH last D: {d_b[-1]:.7f} (expect ~68.6794957)")
