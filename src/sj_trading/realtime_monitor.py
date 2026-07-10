"""
30分K KD即時監控 + 當日低點進場系統
用在星期一早上，自動抓即時資料判斷進場點
"""
import os, sys, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ===== 要監控的股票 =====
# 從回測結果來的最佳參數 (有3042嗎? 從記憶來: K=5, 買不限, 賣>70)
WATCH_STOCKS = {
    # (代號, 名稱, K值, 買門檻, 賣門檻)
    "3042": {"name": "晶技", "k": 5, "buy_th": None, "sell_th": 70},
    "2330": {"name": "台積電", "k": 3, "buy_th": 35, "sell_th": 75},
    "4958": {"name": "臻鼎-KY", "k": 3, "buy_th": 45, "sell_th": 80},
    "6139": {"name": "亞翔", "k": 12, "buy_th": 50, "sell_th": 70},
}

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_intraday_30min_k(api, sid):
    """抓取當日即時1分K，合併成30分K"""
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        return None, None
    
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    # 抓當日1分K
    try:
        kbars = api.kbars(
            contract=contract,
            start=today_str,
            end=today_str,
        )
    except Exception as e:
        print(f"   抓取錯誤: {e}")
        return None, None
    
    if len(kbars.ts) == 0:
        return None, None
    
    df = pd.DataFrame({
        "datetime": pd.to_datetime(kbars.ts),
        "open": kbars.Open, "high": kbars.High,
        "low": kbars.Low, "close": kbars.Close,
        "volume": kbars.Volume,
    })
    df.set_index("datetime", inplace=True)
    
    # 只保留台股交易時間
    df = df.between_time("09:00", "13:30")
    
    if len(df) == 0:
        return None, None
    
    # 合併成30分K
    df_30 = df.resample("30min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    
    return df, df_30

def fetch_hist_30k_and_rebuild_kd(api, sid, hist_30k):
    """抓歷史30分K補到夠計算KD，再跟即時K合併"""
    days_needed = 200  # 抓200天確保有足夠資料
    end = datetime.now()
    start = end - timedelta(days=days_needed)
    
    try:
        contract = api.Contracts.Stocks[sid]
    except:
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
            dft = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
            })
            all_dfs.append(dft)
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
    
    # 跟即時K合併(避免重複)
    if hist_30k is not None and len(hist_30k) > 0:
        combined = pd.concat([_30, hist_30k])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
        return combined
    return _30

def compute_kd(k_vals, d_vals, close, low, high, kp):
    """計算KD值陣列"""
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

def analyze_stock(api, sid, info):
    """分析一檔股票，找出當日最佳進場點"""
    name = info["name"]
    kp = info["k"]
    buy_th = info["buy_th"]
    sell_th = info["sell_th"]
    
    print(f"\n{'='*60}")
    print(f"  📊 {name}({sid}) 即時分析")
    print(f"  策略: K={kp}" + (f" 買<{buy_th}" if buy_th else "買不限") + (f" 賣>{sell_th}" if sell_th else "賣不限"))
    print(f"{'='*60}")
    
    # 步驟1: 抓當日即時1分K
    print("  📥 抓取即時資料...", end="", flush=True)
    df_1min, df_30min_now = fetch_intraday_30min_k(api, sid)
    
    if df_1min is None or len(df_1min) == 0:
        print(" 無當日資料（可能是盤前或已收盤）")
        return None
    
    print(f" {len(df_1min)}根1分K, {len(df_30min_now)}根30分K")
    
    # 步驟2: 抓歷史資料合併
    print("  📥 下載歷史資料...", end="", flush=True)
    full_30 = fetch_hist_30k_and_rebuild_kd(api, sid, df_30min_now)
    if full_30 is None or len(full_30) < kp + 5:
        print(" 歷史資料不足")
        return None
    print(f" {len(full_30)}根30分K")
    
    # 步驟3: 計算KD
    close = full_30["close"].values
    low = full_30["low"].values
    high = full_30["high"].values
    n = len(close)
    
    k_arr = np.full(n, 50.0)
    d_arr = np.full(n, 50.0)
    k_arr, d_arr = compute_kd(k_arr, d_arr, close, low, high, kp)
    
    # 步驟4: 檢查最後的KD狀態
    last_k = k_arr[-1]
    last_d = d_arr[-1]
    second_k = k_arr[-2]
    second_d = d_arr[-2]
    last_close = close[-1]
    last_idx = full_30.index[-1]
    
    print(f"\n  最新30分K: {last_idx.strftime('%H:%M')} 收盤價={last_close:.2f}")
    print(f"  K={last_k:.2f}  D={last_d:.2f}")
    
    # 判斷狀態
    is_golden_cross = second_k <= second_d and last_k > last_d  # 本根金叉
    already_golden = last_k > last_d  # 已處於金叉狀態
    is_death_cross = second_k >= second_d and last_k < last_d  # 本根死叉
    
    buy_ok = False
    if is_golden_cross:
        if buy_th is None or last_k < buy_th:
            buy_ok = True
    
    signals = []
    
    if buy_ok:
        signals.append("🟢 黃金交叉! 符合買進條件!")
    elif is_golden_cross:
        signals.append(f"🟡 黃金交叉! 但K={last_k:.1f}" + (f" > 門檻{buy_th}, 等拉回" if buy_th else ""))
    elif is_death_cross:
        signals.append("🔴 死亡交叉! 先不要進場")
    elif last_k > last_d:
        signals.append(f"🟢 金叉狀態中(K>{last_k:.1f})，回檔不破D線可進場")
    else:
        signals.append(f"🟡 K={last_k:.1f} D={last_d:.1f} K<D, 等待黃金交叉")
    
    # 步驟5: 找當日最低點進場策略
    # 看當日1分K的走勢
    today_min = df_1min["low"].min()
    today_max = df_1min["high"].max()
    today_now = df_1min["close"].iloc[-1]
    today_range = today_max - today_min
    
    if today_range > 0:
        pos = (today_now - today_min) / today_range * 100  # 目前價格在當日位置%
    else:
        pos = 50
    
    print(f"\n  當日走勢:")
    print(f"  最低: {today_min:.2f} | 目前: {today_now:.2f} | 最高: {today_max:.2f}")
    print(f"  位置: {pos:.0f}% (0%=最低, 100%=最高)")
    
    if pos < 30:
        signals.append(f"💡 目前接近當日低點! 價格位置{pos:.0f}%")
        signals.append(f"   → 可在{today_min:.2f}~{today_now:.2f}區間分批進場")
    elif pos < 60:
        signals.append(f"📈 價格在當日中間偏下({pos:.0f}%)，算合理進場點")
    else:
        signals.append(f"⚠️ 價格已在當日高位({pos:.0f}%)，建議等拉回")
    
    # 步驟6: 找出預估的買進價格區間
    suggest_buy = []
    
    # 用1分K的支撐來找
    closes_1m = df_1min["close"].values
    if len(closes_1m) >= 10:
        ma5 = np.mean(closes_1m[-5:])
        ma10 = np.mean(closes_1m[-10:])
        lowest_10 = np.min(closes_1m[-10:])
        
        support = min(ma5, ma10)
        strong_support = lowest_10
        
        suggest_buy.append(f"  建議買進區間: {strong_support:.2f} ~ {support:.2f}")
        suggest_buy.append(f"  分批法: 先買50%在{support:.2f}附近, 再掛{today_min:.2f}附近買30%")
        suggest_buy.append(f"  最後20%等30分K確實金叉確認加碼")
    
    # 步驟7: 風險提醒
    if last_k > 80:
        suggest_buy.append(f"  ⚠️ K={last_k:.1f}超高檔! 風險很大，現在追高很危險")
    elif last_k > 70:
        suggest_buy.append(f"  ⚠️ K={last_k:.1f}偏高檔，謹慎進場")
    
    # 輸出完整報告
    for s in signals:
        print(f"  {s}")
    
    if suggest_buy:
        print(f"\n  🎯 進場策略:")
        for s in suggest_buy:
            print(f"  {s}")
    
    return {
        "sid": sid, "name": name,
        "k": last_k, "d": last_d,
        "golden_cross": is_golden_cross,
        "in_golden": last_k > last_d,
        "buy_ok": buy_ok,
        "today_min": round(today_min, 2),
        "today_now": round(today_now, 2),
        "today_max": round(today_max, 2),
        "today_pos": round(pos, 0),
        "support": round(suggest_buy[0].split(":")[1].strip().split("~")[0], 2) if suggest_buy else 0,
        "latest_close": last_close,
    }


def main():
    print(f"\n{'='*60}")
    print(f"  🦞 小龍蝦 30分K KD即時監控系統")
    print(f"  啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    api = login()
    
    results = {}
    for sid, info in WATCH_STOCKS.items():
        try:
            result = analyze_stock(api, sid, info)
            if result:
                results[sid] = result
            time.sleep(1)
        except Exception as e:
            print(f"  ❌ {info['name']} 分析錯誤: {e}")
    
    api.logout()
    
    # 最終建議
    print(f"\n{'='*60}")
    print(f"  📋 最終操作建議")
    print(f"{'='*60}")
    
    for sid, r in results.items():
        print(f"\n  {r['name']}({sid}):")
        if r["buy_ok"]:
            print(f"  ✅ 符合買進條件! K={r['k']:.1f}")
            print(f"  建議買進區間: {r['support']:.2f} ~ {r['today_min']:.2f}")
            print(f"  低點狙擊法: 分批掛{min(r['support'], r['today_min']):.2f}~{r['today_now']:.2f}")
        else:
            if r["in_golden"]:
                print(f"  🟡 金叉狀態但K={r['k']:.1f}不在買進門檻內")
            else:
                print(f"  🔴 K<D死叉中, 等待黃金交叉")
                print(f"  現況: K={r['k']:.1f} D={r['d']:.1f}")
    
    print(f"\n{'='*60}")
    print(f"  ✅ 監控完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
