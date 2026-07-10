"""
星期一晶技(3042)低點進場狙擊系統
包含自動排程 + 即時監控 + 低點預警

用法：
  盤中執行: python -X utf8 -m src.sj_trading.crystal_attack
  自動模式: python -X utf8 -m src.sj_trading.crystal_attack --auto
"""
import os, sys, json, time, argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

STOCK_SID = "3042"
STOCK_NAME = "晶技"
# 最佳參數 (從 7/3 記憶: K=5, 買不限, 賣>70)
KD_K = 5
BUY_TH = None    # 買不限，只要金叉就買
SELL_TH = 70     # K>70死叉賣

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def compute_kd(k_vals, d_vals, close, low, high, kp):
    n = len(k_vals)
    low_min = pd.Series(low).rolling(kp).min().values
    high_max = pd.Series(high).rolling(kp).max().values
    denom = high_max - low_min
    rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50)
    for i in range(kp, n):
        k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
        d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
        k_vals[i] = k_new
        d_vals[i] = d_new
    return k_vals, d_vals

def load_hist_and_kd(api, sid=STOCK_SID, days=200):
    """抓歷史30分K + KD計算，回傳完整資料"""
    end = datetime.now()
    start = end - timedelta(days=days)
    
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        print(f"  ❌ {sid} 找不到合約")
        return None
    
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        try:
            kbars = api.kbars(contract=contract,
                start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts) == 0:
                seg_end = seg_start - timedelta(seconds=1)
                continue
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except:
            break
    
    if not all_dfs:
        return None
    
    raw = pd.concat(all_dfs)
    raw.drop_duplicates(subset=["datetime"], inplace=True)
    raw.sort_values("datetime", inplace=True)
    raw.set_index("datetime", inplace=True)
    _30 = raw.resample("30min").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    _30 = _30.between_time("09:00", "13:30")
    
    if len(_30) < KD_K + 5:
        return None
    
    # 算KD
    close = _30["close"].values
    low_vals = _30["low"].values
    high_vals = _30["high"].values
    n = len(close)
    k_arr = np.full(n, 50.0)
    d_arr = np.full(n, 50.0)
    k_arr, d_arr = compute_kd(k_arr, d_arr, close, low_vals, high_vals, KD_K)
    
    _30 = _30.copy()
    _30["K"] = k_arr
    _30["D"] = d_arr
    
    return _30

def check_entry(df_30):
    """檢查進場訊號"""
    if df_30 is None or len(df_30) < KD_K + 2:
        return None
    
    k_now = df_30["K"].iloc[-1]
    d_now = df_30["D"].iloc[-1]
    k_prev = df_30["K"].iloc[-2]
    d_prev = df_30["D"].iloc[-2]
    close_now = df_30["close"].iloc[-1]
    time_now = df_30.index[-1]
    
    # 黃金交叉判斷
    is_golden = k_prev <= d_prev and k_now > d_now
    already_golden = k_now > d_now
    
    # 檢查是「剛剛金叉」還是「早就在金叉」
    if is_golden:
        # 檢查前幾根K的K走勢
        if len(df_30) >= 5:
            k_5 = df_30["K"].iloc[-5]
            # K從低點爬上來
            if k_now > 30 and k_prev <= d_prev:
                return {
                    "signal": "BUY",
                    "type": "黃金交叉初現",
                    "k": round(k_now, 2),
                    "d": round(d_now, 2),
                    "close": round(close_now, 2),
                    "time": time_now.strftime("%H:%M"),
                    "reason": f"K={k_now:.1f}剛突破D={d_now:.1f}，金叉初現"
                }
    
    if already_golden and k_now < 50 and k_now > d_now:
        return {
            "signal": "WATCH",
            "type": "低檔金叉中",
            "k": round(k_now, 2),
            "d": round(d_now, 2),
            "close": round(close_now, 2),
            "time": time_now.strftime("%H:%M"),
            "reason": f"K={k_now:.1f}低檔金叉延續，拉回不破D可接"
        }
    
    return {
        "signal": "WAIT",
        "type": "等待訊號",
        "k": round(k_now, 2),
        "d": round(d_now, 2),
        "close": round(close_now, 2),
        "time": time_now.strftime("%H:%M"),
        "reason": f"K={k_now:.1f} D={d_now:.1f} " + ("金叉走勢" if k_now > d_now else "死叉走勢")
    }

def generate_buy_plan(df_30, entry_info):
    """根據當日1分K產生具體的進場計劃"""
    print(f"\n{'='*60}")
    print(f"  🎯 {STOCK_NAME}({STOCK_SID}) 晶技 進場作戰計劃")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    if df_30 is None or entry_info is None:
        print("  ❌ 無資料")
        return
    
    # 最新狀態
    last_bar = df_30.iloc[-1]
    print(f"\n  📊 30分K狀態:")
    print(f"  時間: {df_30.index[-1].strftime('%m/%d %H:%M')}")
    print(f"  收盤價: {last_bar['close']:.2f}")
    print(f"  K={last_bar['K']:.2f} | D={last_bar['D']:.2f}")
    
    # KD走勢圖 (文字版)
    k_vals = df_30["K"].values[-10:]
    d_vals = df_30["D"].values[-10:]
    print(f"\n  📈 近10根K線KD走勢:")
    print(f"  {'K線':<6} {'收盤':<8} {'K':<8} {'D':<8}")
    for i in range(len(k_vals)):
        idx = df_30.index[-10+i]
        print(f"  {idx.strftime('%m/%d %H:%M'):<6} {df_30['close'].values[-10+i]:<8.2f} {k_vals[i]:<8.2f} {d_vals[i]:<8.2f}")
    
    # 進場訊號
    print(f"\n  🚦 訊號: {entry_info['signal']}")
    print(f"  類型: {entry_info['type']}")
    print(f"  原因: {entry_info['reason']}")
    
    # 當日價格區間
    print(f"\n  💰 近期價格區間:")
    recent_high = df_30["high"].tail(20).max()
    recent_low = df_30["low"].tail(20).min()
    print(f"  近20根K: {recent_low:.2f} ~ {recent_high:.2f}")
    print(f"  目前價位: {last_bar['close']:.2f} ({(last_bar['close']-recent_low)/(recent_high-recent_low)*100:.0f}%)")
    
    # 進場計劃
    current = last_bar["close"]
    print(f"\n  📋 分批進場計畫:")
    
    if entry_info["signal"] == "BUY":
        # 剛金叉，立即進場
        buy1 = current
        buy2 = round(current * 0.98, 2)  # 掛低2%
        buy3 = round(current * 0.96, 2)  # 掛低4%
        stop_loss = round(current * 0.93, 2)  # 停損-7%
        target1 = round(current * 1.05, 2)    # 目標+5%
        target2 = round(current * 1.10, 2)    # 目標+10%
        
        print(f"  ✅ 黃金交叉確認! 建議進場")
        print(f"  {'批次':<10} {'方式':<12} {'價格':<10} {'金額佔比':<10}")
        print(f"  {'─'*42}")
        print(f"  {'第1批':<10} {'市價即買':<12} {buy1:<10.2f} {'50%':<10}")
        print(f"  {'第2批':<10} {'掛低2%買':<12} {buy2:<10.2f} {'30%':<10}")
        print(f"  {'第3批':<10} {'掛低4%買':<12} {buy3:<10.2f} {'20%':<10}")
        print(f"")
        print(f"  🛑 停損: {stop_loss:.2f} (-7%)")
        print(f"  🎯 目標1: {target1:.2f} (+5%)")
        print(f"  🎯 目標2: {target2:.2f} (+10%)")
        print(f"  賣出條件: K>70的死叉或K>80高檔反轉")
        
    elif entry_info["signal"] == "WATCH":
        # 已在金叉但還沒到
        if current > 0:
            buy1 = round(current * 0.97, 2)
            buy2 = round(current * 0.95, 2)
            print(f"  🟡 已處於金叉，等拉回再進:")
            print(f"  掛{buy1:.2f} (-3%) 先買40%")
            print(f"  掛{buy2:.2f} (-5%) 再加60%")
            print(f"  若K跌破D線死叉，取消所有掛單")
    
    else:
        print(f"  🔴 等待訊號中，還未到進場時機")
        if entry_info["k"] > entry_info["d"]:
            print(f"  策略: K往下彎觸D線反彈時 = 進場點")
        else:
            print(f"  策略: 等K值從下往上突破D線黃金交叉")
    
    # 除權息提醒
    print(f"\n  📅 注意:")
    print(f"  - 晶技除權息日: 尚未過除權息")
    print(f"  - 策略賣出: K>{SELL_TH}的死亡交叉或K>80")
    print(f"  - 每次下單前確認實際成交價與計劃差異")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="自動循環監控")
    parser.add_argument("--interval", type=int, default=60, help="監控間隔秒數")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  🦞 晶技(3042) 低點進場狙擊系統")
    print(f"  策略: K={KD_K} 買不限 賣>{SELL_TH}")
    print(f"  時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    api = login()
    
    if args.auto:
        # 自動循環監控模式
        print(f"\n  🔄 自動監控模式 (每{args.interval}秒掃一次)")
        print(f"  {'='*50}")
        
        last_signal = None
        while True:
            now = datetime.now()
            if now.hour < 9 or (now.hour >= 13 and now.minute > 30):
                print(f"\n  ⏰ 盤後時間 {now.strftime('%H:%M')}，暫停監控")
                print(f"  下次開盤前會自動恢復")
                time.sleep(300)  # 5分再檢查
                continue
            
            print(f"\n  [{now.strftime('%H:%M:%S')}] 掃描中...", end=" ", flush=True)
            
            df_30 = load_hist_and_kd(api)
            if df_30 is None:
                print("📭 無資料")
                time.sleep(args.interval)
                continue
            
            entry = check_entry(df_30)
            
            if entry:
                sig = entry["signal"]
                print(f"{sig} K={entry['k']} D={entry['d']} @{entry['close']}")
                
                if sig == "BUY" and last_signal != "BUY":
                    print(f"\n  🚨🚨🚨 黃金交叉!!! 可以進場了!!")
                    print(f"  📊 {entry['reason']}")
                    print(f"  快執行: 晶技 {entry['close']} 買進")
                    generate_buy_plan(df_30, entry)
                    last_signal = "BUY"
                elif sig in ("WATCH", "WAIT"):
                    last_signal = sig
            
            time.sleep(args.interval)
        
    else:
        # 單次分析
        df_30 = load_hist_and_kd(api)
        if df_30 is None:
            print("  ❌ 無法載入歷史資料")
            api.logout()
            return
        
        entry = check_entry(df_30)
        generate_buy_plan(df_30, entry)
    
    api.logout()


if __name__ == "__main__":
    main()
