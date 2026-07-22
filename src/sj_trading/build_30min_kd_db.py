#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📦 30分K KD/MACD/RSI 資料庫維護工具
====================================
用途：為指定股票下載 60天 1分K → 合併 30分K → 計算 KD/MACD/RSI → 存入 database/3y_kd/
支援：核心持股新增 / 潛力股新增 / 任何股票代號

流程:
  1. Shioaji 下載 60天 1分K（分段14天/段）
  2. 合併為 30分K，過濾台股交易時段 09:00~13:30
  3. TA-Lib 計算 KD (STOCH), MACD, RSI
  4. 存入 database/3y_kd/{sid}_kd.csv
"""
import sys, os, time
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import talib
from dotenv import load_dotenv

# ─── 路徑 ─────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_DIR = os.path.join(BASE_DIR, 'database', '3y_kd')
os.makedirs(DB_DIR, exist_ok=True)

sys.path.insert(0, SCRIPT_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

import shioaji as sj

# ─── KD 參數表（可擴充）─────────────────────
KD_PARAMS = {
    "2436": 5,  "2337": 21, "5351": 14,
    "3673": 14, "3711": 21, "4958": 21,
    "3042": 14, "2454": 21, "2317": 14,
    "8150": 21, "2330": 9,  "0050": 9,
}

# ═══════════════════════════════════════════════
#  Shioaji 登入（重複使用）
# ═══════════════════════════════════════════════
def login_shioaji():
    api_key = os.environ.get("SJ_API_KEY", "")
    sec_key = os.environ.get("SJ_SEC_KEY", "")
    if not api_key or not sec_key:
        print("❌ 無 SJ_API_KEY / SJ_SEC_KEY 在 .env")
        return None
    api = sj.Shioaji(simulation=False)
    try:
        api.login(api_key=api_key, secret_key=sec_key, fetch_contract=True)
        print("✅ Shioaji 登入成功")
        return api
    except Exception as e:
        print(f"❌ Shioaji 登入失敗: {e}")
        return None


# ═══════════════════════════════════════════════
#  下載 60 天 1分K（分段，支援重試）
# ═══════════════════════════════════════════════
def download_60d_1min(api, sid):
    """下載 60 天 1分K，分段 14天/段，回傳 DataFrame 或 None"""
    end = datetime.now()
    start = end - timedelta(days=60)
    
    segs = []
    s = start
    while s < end:
        e = min(s + timedelta(days=14), end)
        segs.append((s, e))
        s = e
    
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        print(f"  ⚠️ {sid}: 找不到合約")
        return None
    
    all_rows = []
    for ss, se in segs:
        for attempt in range(3):
            try:
                kb = api.kbars(contract=contract,
                              start=ss.strftime("%Y-%m-%d"),
                              end=se.strftime("%Y-%m-%d"),
                              timeout=15000)
                if kb is None or len(kb.ts) == 0:
                    break
                for i in range(len(kb.ts)):
                    utc_ts = datetime.fromtimestamp(kb.ts[i] / 1e9)
                    local_ts = utc_ts + timedelta(hours=8)
                    all_rows.append({
                        "ts": local_ts,
                        "Open": float(kb.Open[i]),
                        "High": float(kb.High[i]),
                        "Low": float(kb.Low[i]),
                        "Close": float(kb.Close[i]),
                        "Volume": float(kb.Volume[i]),
                    })
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                print(f"  ⚠️ {sid} {ss.date()}~{se.date()} 失敗: {e}")
                break
    
    if not all_rows:
        return None
    
    df = pd.DataFrame(all_rows).sort_values("ts").drop_duplicates(subset="ts").reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════
#  合併 30分K
# ═══════════════════════════════════════════════
def merge_30min(df_1min):
    """1分K → 30分K，過濾台股交易時段"""
    if df_1min is None or df_1min.empty:
        return None
    
    df = df_1min.set_index("ts")
    
    ohlc = pd.DataFrame({"open": df["Open"].resample("30min").first()})
    ohlc["high"] = df["High"].resample("30min").max()
    ohlc["low"] = df["Low"].resample("30min").min()
    ohlc["close"] = df["Close"].resample("30min").last()
    ohlc["volume"] = df["Volume"].resample("30min").sum()
    ohlc = ohlc.dropna().reset_index()
    
    # 過濾台股交易時段 09:00~13:30
    ohlc["hour"] = ohlc["ts"].dt.hour
    ohlc["minute"] = ohlc["ts"].dt.minute
    ohlc = ohlc[
        ((ohlc["hour"] == 9) & (ohlc["minute"] >= 0)) |
        ((ohlc["hour"] >= 10) & (ohlc["hour"] <= 12)) |
        ((ohlc["hour"] == 13) & (ohlc["minute"] <= 30))
    ].drop(columns=["hour", "minute"]).reset_index(drop=True)
    
    if len(ohlc) < 30:
        return None
    
    return ohlc


# ═══════════════════════════════════════════════
#  TA-Lib 計算並存檔
# ═══════════════════════════════════════════════
def calc_and_save(sid, df_30min):
    """用 TA-Lib 算 KD/MACD/RSI，存入 database/3y_kd/"""
    close = np.array(df_30min["close"], dtype=float)
    high = np.array(df_30min["high"], dtype=float)
    low = np.array(df_30min["low"], dtype=float)
    vol = np.array(df_30min["volume"], dtype=float)
    
    kp = KD_PARAMS.get(sid, 9)
    
    # KD
    k_arr, d_arr = talib.STOCH(high, low, close, fastk_period=kp, slowk_period=3, slowd_period=3)
    df_30min["K"] = k_arr
    df_30min["D"] = d_arr
    
    # MACD
    macd, macd_sig, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df_30min["MACD"] = macd
    df_30min["MACD_signal"] = macd_sig
    df_30min["MACD_hist"] = macd_hist
    
    # RSI
    rsi = talib.RSI(close, timeperiod=14)
    df_30min["RSI"] = rsi
    
    # Volume MA
    df_30min["vol_ma5"] = talib.SMA(vol, timeperiod=5)
    df_30min["vol_ma20"] = talib.SMA(vol, timeperiod=20)
    
    # 時間轉字串
    df_30min["datetime"] = df_30min["ts"].astype(str)
    df_30min = df_30min.drop(columns=["ts"])
    
    # 存檔（欄位: datetime, open, high, low, close, volume, K, D, MACD, MACD_signal, MACD_hist, RSI, vol_ma5, vol_ma20）
    out_path = os.path.join(DB_DIR, f"{sid}_kd.csv")
    df_30min.to_csv(out_path, index=False, encoding="utf-8-sig")
    
    k_last = round(float(k_arr[-1]), 1) if not np.isnan(k_arr[-1]) else 0
    d_last = round(float(d_arr[-1]), 1) if not np.isnan(d_arr[-1]) else 0
    rsi_last = round(float(rsi[-1]), 1) if not np.isnan(rsi[-1]) else 0
    hist_last = round(float(macd_hist[-1]), 2) if not np.isnan(macd_hist[-1]) else 0
    px_last = round(float(close[-1]), 1)
    
    print(f"  ✅ {sid}: {len(df_30min)}根30分K | 最新 {px_last} | K={k_last} D={d_last} | MACD_hist={hist_last} | RSI={rsi_last}")
    return True


# ═══════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════
def build_db(stock_ids, api=None):
    """
    為指定股票建立/更新 30分K KD 資料庫
    
    stock_ids: [(sid, name), ...] 或 [sid, ...]
    api: 可選，傳入已登入的 Shioaji API，None 則自動登入
    
    回傳 success_list: [sid, ...]
    """
    # 統一格式
    ids = []
    for s in stock_ids:
        if isinstance(s, (list, tuple)):
            ids.append(s[0])
        else:
            ids.append(s)
    
    need_logout = False
    if api is None:
        api = login_shioaji()
        if api is None:
            return []
        need_logout = True
    
    success = []
    for sid in ids:
        print(f"\n📥 {sid} 下載 60天 1分K...")
        df_1min = download_60d_1min(api, sid)
        if df_1min is None:
            print(f"  ❌ {sid}: 下載失敗")
            continue
        
        print(f"  📊 合併 30分K...")
        df_30min = merge_30min(df_1min)
        if df_30min is None:
            print(f"  ❌ {sid}: 合併後資料不足 (需要≥30根)")
            continue
        
        calc_and_save(sid, df_30min)
        success.append(sid)
    
    if need_logout:
        try:
            api.logout()
            print("🔌 Shioaji 已登出")
        except:
            pass
    
    return success


# ═══════════════════════════════════════════════
#  CLI 使用
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="30分K KD/MACD/RSI 資料庫建立工具")
    parser.add_argument("codes", nargs="*", help="股票代號，如 2330 2454 2317")
    parser.add_argument("--all-core", action="store_true", help="更新全部核心持股")
    parser.add_argument("--all-db", action="store_true", help="更新 database 中已有的全部股票")
    
    args = parser.parse_args()
    
    stock_ids = []
    
    if args.all_core:
        core_ids = ["2436","2337","5351","3673","3711","4958","3042","2454","2317","8150","2330","0050"]
        stock_ids.extend(core_ids)
        print(f"📋 更新全部核心持股 ({len(core_ids)}檔)")
    
    if args.all_db:
        files = os.listdir(DB_DIR)
        for f in sorted(files):
            if f.endswith("_kd.csv"):
                sid = f.replace("_kd.csv", "")
                stock_ids.append(sid)
        print(f"📋 更新全部資料庫 ({len(stock_ids)}檔)")
    
    if args.codes:
        stock_ids.extend(args.codes)
    
    if not stock_ids:
        # 預設：更新核心持股
        stock_ids = ["2436","2337","5351","3673","3711","4958","3042","2454","2317","8150","2330","0050"]
        print(f"📋 預設更新核心持股 ({len(stock_ids)}檔)")
    
    # 去重
    stock_ids = list(dict.fromkeys(stock_ids))
    
    print(f"\n{'='*50}")
    print(f"  30分K KD 資料庫建置")
    print(f"  股票: {', '.join(stock_ids)}")
    print(f"{'='*50}")
    
    success = build_db(stock_ids)
    
    print(f"\n{'='*50}")
    print(f"  ✅ 成功: {len(success)}/{len(stock_ids)} 檔")
    print(f"  ❌ 失敗: {len(stock_ids) - len(success)} 檔")
    print(f"{'='*50}")
