"""
核心監控：30分K KD黃金/死亡交叉
這才是TradingView上真正看的買賣點
"""
import os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

from calc_tech import apply_indicators

load_dotenv()

WATCHLIST = [
    "3711","4958","3042","2337","2436","3673",  # 庫存
    "2330","2454","6139","2303","2317","8150",  # 觀察
    "6284","6213","1303","1802","6271","6451",
    "2327","6173","5425","3131","3583","6239",
    "2344","2408","6770","5351","2369","8016",
    "2464","3588","00947","3545","3003","6693",
    "6147","2316","8358","4961","6187","2458",
    "3234","6155","8121","6257","3026","6435",
    "2493","5493","8086","2492","8028","3455",
    "2481","6944","3532","2308",
]

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def get_30min_kd(api, sid):
    """抓15天1分K -> 合併30分K -> 算KD，確保有足夠歷史"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=15)  # 抓15天確保有足夠歷史
    
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=14), start)
        try:
            kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts) == 0: break
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except: break
    
    if not all_dfs:
        return None
    
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    
    # 合併30分K
    df_30m = min_df.resample("30min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum",
    }).dropna()
    
    if len(df_30m) < 17:
        return None

    df_30m = apply_indicators(df_30m.reset_index())
    if 'datetime' in df_30m.columns:
        df_30m.set_index('datetime', inplace=True)

    return df_30m


def scan_golden_cross():
    """掃描所有自選股，找出30分K黃金交叉"""
    print(f"\n{'='*60}")
    print(f"🟢 30分K KD黃金交叉掃描")
    print(f"時間: {datetime.now().strftime('%m/%d %H:%M')}")
    print(f"{'='*60}")
    
    results = {"golden": [], "death": [], "approaching": []}
    count = 0
    api = login()
    
    for sid in WATCHLIST:
        count += 1
        try:
            df = get_30min_kd(api, sid)
            if df is None or len(df) < 12:
                continue
            
            # 取最後3根30分K
            last3 = df.tail(3)
            last = last3.iloc[-1]
            prev = last3.iloc[-2]
            
            k_now = round(last["K"], 1)
            d_now = round(last["D"], 1)
            k_prev = round(prev["K"], 1)
            d_prev = round(prev["D"], 1)
            close = round(last["close"], 2)
            ts = last.name.strftime("%H:%M")
            
            # 黃金交叉
            if k_prev <= d_prev and k_now > d_now:
                results["golden"].append({
                    "sid": sid, "price": close, "k": k_now, "d": d_now,
                    "time": ts, "prev_k": k_prev, "prev_d": d_prev
                })
                print(f"  🟢 {sid} @{close} K={k_now}穿D={d_now} ({ts})")
            
            # 死亡交叉
            elif k_prev >= d_prev and k_now < d_now:
                results["death"].append({
                    "sid": sid, "price": close, "k": k_now, "d": d_now, "time": ts
                })
                print(f"  🔴 {sid} @{close} K={k_now}跌破D={d_now} ({ts})")
            
            # 接近黃金交叉（K<D 但差距縮到 3 以內 + K 正在往上追）
            elif k_now < d_now and (d_now - k_now) <= 3.0 and k_prev < k_now:
                gap = round(d_now - k_now, 1)
                results["approaching"].append({
                    "sid": sid, "price": close, "k": k_now, "d": d_now, "gap": gap, "time": ts
                })
                print(f"  💡 {sid} @{close} K={k_now}追上D={d_now} (差距{gap}) ({ts})")
        
        except Exception as e:
            continue
    
    api.logout()
    
    print(f"\n{'='*60}")
    print(f"📋 掃描完成 ({count}支)")
    print(f"  黃金交叉: {len(results['golden'])}支")
    print(f"  死亡交叉: {len(results['death'])}支")
    print(f"  即將金叉: {len(results['approaching'])}支")
    print(f"{'='*60}")
    
    return results


if __name__ == "__main__":
    scan_golden_cross()
