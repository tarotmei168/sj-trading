#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
60天30分K KD/MACD/RSI 資料庫（FinMind 60天日K + Shioaji 即時漲跌）
Shioaji 歷史 kbar 只給盤後資料，所以用 FinMind 日K 建立
再用 Shioaji snapshot 更新最新即時價格
"""
import sys, os, requests, numpy as np, pandas as pd, talib
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_DIR = os.path.join(BASE_DIR, 'database', '30min_60d')
os.makedirs(DB_DIR, exist_ok=True)
sys.path.insert(0, SCRIPT_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

import shioaji as sj

KD_PARAMS = {
    "2436":5,"2337":21,"5351":14,"3673":14,"3711":21,"4958":21,
    "3042":14,"2454":21,"2317":14,"8150":21,"2330":9,"0050":9,
}

def fetch_finmind(sid, days=90):
    url = "https://api.finmindtrade.com/api/v4/data"
    try:
        r = requests.get(url, params={"dataset":"TaiwanStockPrice","data_id":sid,
            "start_date":(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d"),
            "end_date":datetime.now().strftime("%Y-%m-%d")}, timeout=10)
        d = r.json()
        if d.get("status")!=200 or not d.get("data"): return None
        items = d["data"]
        records = [{
            "close": float(r2["close"]), "high": float(r2["max"]),
            "low": float(r2["min"]), "volume": float(r2.get("Trading_Volume",0))
        } for r2 in items]
        return pd.DataFrame(records)
    except: return None

def update_snapshot(sid, df):
    """用 Shioaji 即時 snapshot 更新 df 最後一筆的 close，算漲跌"""
    api_key = os.environ.get("SJ_API_KEY",""); sec_key = os.environ.get("SJ_SEC_KEY","")
    if not api_key or not sec_key: return df
    try:
        api = sj.Shioaji(simulation=False)
        api.login(api_key=api_key, secret_key=sec_key)
        contract = api.Contracts.Stocks[sid]
        snaps = api.snapshots([contract])
        api.logout()
        if snaps and len(snaps) > 0 and snaps[0].close:
            s = snaps[0]
            live_px = round(float(s.close), 1)
            prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else float(df["close"].iloc[-1])
            chg = round(live_px - prev_close, 2)
            chg_pct = round((live_px/prev_close - 1)*100, 2)
            df.loc[df.index[-1], "close"] = live_px
            df["chg"] = 0.0
            df["chg_pct"] = 0.0
            df.loc[df.index[-1], "chg"] = chg
            df.loc[df.index[-1], "chg_pct"] = chg_pct
            print(f"  snapshot: {live_px} ({chg:+g} / {chg_pct:+.2f}%)")
    except: pass
    return df

def calc_and_save(sid, df):
    if df is None or len(df) < 25: return False
    c = np.array(df["close"], dtype=float)
    h = np.array(df["high"], dtype=float)
    l = np.array(df["low"], dtype=float)
    v = np.array(df["volume"], dtype=float)
    kp = KD_PARAMS.get(sid, 9)
    k,d_ = talib.STOCH(h,l,c,fastk_period=kp,slowk_period=3,slowd_period=3)
    macd,sig,hist = talib.MACD(c,fastperiod=12,slowperiod=26,signalperiod=9)
    rsi = talib.RSI(c,timeperiod=14)
    df["K"] = k; df["D"] = d_
    df["MACD"] = macd; df["MACD_signal"] = sig; df["MACD_hist"] = hist
    df["RSI"] = rsi
    out = os.path.join(DB_DIR, f"{sid}_60d.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    kl = round(float(k[-1]),1) if not np.isnan(k[-1]) else 0
    dl = round(float(d_[-1]),1) if not np.isnan(d_[-1]) else 0
    rl = round(float(rsi[-1]),1) if not np.isnan(rsi[-1]) else 0
    hl = round(float(hist[-1]),2) if not np.isnan(hist[-1]) else 0
    px = round(float(c[-1]),1)
    print(f"  {sid} {px} | K={kl} D={dl} | MACD_hist={hl} | RSI={rl} | {len(df)}天")
    return True

def build(stock_ids):
    ids = [s[0] if isinstance(s,(list,tuple)) else s for s in stock_ids]
    ok = []
    for sid in ids:
        print(f"\n{sid} FinMind 60天日K...", end=" ", flush=True)
        df = fetch_finmind(sid)
        if df is None: print("fail"); continue
        print(f"({len(df)}天)")
        df = update_snapshot(sid, df)
        if calc_and_save(sid, df):
            ok.append(sid)
    print(f"\n{len(ok)}/{len(ids)} done -> database/30min_60d/")
    return ok

if __name__=="__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("codes", nargs="*")
    p.add_argument("--all-core", action="store_true")
    args = p.parse_args()
    ids = []
    if args.all_core: ids = ["2436","2337","5351","3673","3711","4958","3042","2454","2317","8150","2330","0050"]
    if args.codes: ids.extend(args.codes)
    if not ids: ids = ["2436","2337","5351","3673","3711","4958","3042","2454","2317","8150","2330","0050"]
    ids = list(dict.fromkeys(ids))
    build(ids)
