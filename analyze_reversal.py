"""
反轉分析工具：針對旺宏、晶技抓取真實tick資料
分析買賣力道、大單動向、判斷是否反轉
"""
import os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_tick_data(api, sid):
    """抓取今日tick資料"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=3)
    kbars = api.kbars(contract=contract, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    if len(kbars.ts) == 0:
        return None, None
    df = pd.DataFrame({
        "ts": pd.to_datetime(kbars.ts),
        "price": kbars.Close,
        "volume": kbars.Volume,
        "amount": kbars.Amount,
    })
    today = datetime.now().date()
    df["date"] = df["ts"].dt.date
    df_today = df[df["date"] == today].copy()
    df_prev = df[df["date"] < today].copy()
    return df_today if len(df_today) > 0 else None, df_prev

def fetch_daily_30m(api, sid, days=90):
    """抓日K線"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=days)
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        try:
            kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts) == 0: break
            df = pd.DataFrame({"datetime": pd.to_datetime(kbars.ts), "open": kbars.Open, "high": kbars.High, "low": kbars.Low, "close": kbars.Close, "volume": kbars.Volume, "amount": kbars.Amount})
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except: break
    if not all_dfs: return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","amount":"sum"}).dropna()
    return daily

def calc_indicators(daily):
    """計算KD+MACD+RSI"""
    kp = 9
    low_min = daily["low"].rolling(kp).min()
    high_max = daily["high"].rolling(kp).max()
    rsv = ((daily["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)
    k_vals, d_vals = [50]*kp, [50]*kp
    for i in range(kp, len(daily)):
        k_new = (2/3)*k_vals[-1] + (1/3)*rsv.iloc[i]
        d_new = (2/3)*d_vals[-1] + (1/3)*k_new
        k_vals.append(k_new); d_vals.append(d_new)
    daily["K"] = k_vals; daily["D"] = d_vals
    ema12 = daily["close"].ewm(span=12).mean()
    ema26 = daily["close"].ewm(span=26).mean()
    daily["MACD"] = ema12 - ema26
    daily["MACD_signal"] = daily["MACD"].ewm(span=9).mean()
    daily["MACD_hist"] = daily["MACD"] - daily["MACD_signal"]
    delta = daily["close"].diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_g = gain.rolling(14).mean(); avg_l = loss.rolling(14).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    daily["RSI"] = 100 - (100 / (1 + rs))
    daily["vol_ma5"] = daily["volume"].rolling(5).mean()
    daily["vol_ratio"] = daily["volume"] / daily["vol_ma5"].replace(0, np.nan)
    return daily

def analyze_reversal(name, sid):
    """分析反轉訊號"""
    print(f"\n{'='*60}")
    print(f"🔍 {name}({sid}) — 反轉力道深度分析")
    print(f"{'='*60}")
    
    api = login()
    daily = fetch_daily_30m(api, sid, days=90)
    today_tick, prev_tick = fetch_tick_data(api, sid)
    
    if daily is not None:
        daily = calc_indicators(daily)
        last = daily.iloc[-1]; prev = daily.iloc[-2]; prev2 = daily.iloc[-3]
        price = round(last["close"], 2)
        k, d = round(last["K"], 1), round(last["D"], 1)
        k_prev, d_prev = round(prev["K"], 1), round(prev["D"], 1)
        rsi = round(last["RSI"], 1) if not pd.isna(last.get("RSI",np.nan)) else 0
        macd_h = round(last["MACD_hist"], 2) if not pd.isna(last.get("MACD_hist",np.nan)) else 0
        vol_r = round(last["vol_ratio"], 2) if not pd.isna(last.get("vol_ratio",np.nan)) else 0
        vol = int(last["volume"])
        
        print(f"\n📈 技術指標 (日線):")
        print(f"  股價: {price}")
        print(f"  KD: K={k} D={d} (前日K={k_prev} D={d_prev})")
        print(f"  RSI: {rsi}")
        print(f"  MACD柱: {macd_h}")
        print(f"  量比: {vol_r} | 成交量: {vol}")
        
        # KD交叉判斷
        if k_prev <= d_prev and k > d:
            print(f"  🟢 黃金交叉!")
        elif k_prev >= d_prev and k < d:
            print(f"  🔴 死亡交叉!")
        
        # K值變化趨勢
        k_days5 = daily["K"].iloc[-5] if len(daily) >= 5 else None
        if k_days5:
            k_change = k - k_days5
            print(f"  5天K值變化: {k_change:+.1f}")
            if k_change > 20: print(f"  ⚠️ K值急升，可能過熱")
            elif k_change < -15: print(f"  ⚠️ K值急降，可能超賣")
    
    # ---- Tick追價力道分析 ----
    df_use = today_tick if today_tick is not None and len(today_tick) >= 10 else prev_tick
    if df_use is not None and len(df_use) >= 10:
        df_use = df_use.copy()
        df_use["price_change"] = df_use["price"].diff()
        
        up = (df_use["price_change"] > 0).sum()
        down = (df_use["price_change"] < 0).sum()
        flat = len(df_use) - up - down
        up_ratio = round(up / max(up+down, 1) * 100, 1)
        
        up_vol = int(df_use[df_use["price_change"] > 0]["volume"].sum()) if up > 0 else 0
        down_vol = int(df_use[df_use["price_change"] < 0]["volume"].sum()) if down > 0 else 0
        up_vol_ratio = round(up_vol / max(up_vol+down_vol, 1) * 100, 1)
        
        avg_vol = df_use["volume"].mean()
        large = df_use[df_use["volume"] > avg_vol * 2]
        big_up = len(large[large["price_change"] > 0])
        big_down = len(large[large["price_change"] < 0])
        big_vol_up = int(large[large["price_change"] > 0]["volume"].sum())
        big_vol_down = int(large[large["price_change"] < 0]["volume"].sum())
        
        print(f"\n📊 Tick追價力道 (今日{len(df_use)}筆tick):")
        print(f"  上漲tick: {up}({up_ratio}%) | 下跌tick: {down}({100-up_ratio}%) | 平: {flat}")
        print(f"  上漲量: {up_vol}({up_vol_ratio}%) | 下跌量: {down_vol}({100-up_vol_ratio}%)")
        print(f"  大單買: {big_up}筆({big_vol_up}股) | 大單賣: {big_down}筆({big_vol_down}股)")
        
        # 最後10筆分析
        last10 = df_use.tail(10)
        l10_up = (last10["price_change"] > 0).sum()
        l10_down = (last10["price_change"] < 0).sum()
        l10_price_change = round(last10["price"].iloc[-1] - last10["price"].iloc[0], 2)
        print(f"  最後10筆: 漲{l10_up} 跌{l10_down} 價差{l10_price_change}")
        
        # 最後5分鐘
        last5m = df_use[df_use["ts"] >= (df_use["ts"].max() - timedelta(minutes=5))]
        if len(last5m) > 1:
            m5_up = (last5m["price_change"] > 0).sum()
            m5_down = (last5m["price_change"] < 0).sum()
            m5_vol_up = int(last5m[last5m["price_change"] > 0]["volume"].sum())
            m5_vol_down = int(last5m[last5m["price_change"] < 0]["volume"].sum())
            m5_price_c = round(last5m["price"].iloc[-1] - last5m["price"].iloc[0], 2)
            print(f"  最後5分: 漲{m5_up}筆({m5_vol_up}股) 跌{m5_down}筆({m5_vol_down}股) 價差{m5_price_c}")
        
        # 價格區間
        print(f"  今日區間: {df_use['price'].min()} ~ {df_use['price'].max()}")
    
    else:
        print("\n📊 今日無足夠tick資料")
    
    api.logout()
    
    # ---- 綜合判斷 ----
    print(f"\n{'='*60}")
    print(f"📋 綜合判斷與策略")
    print(f"{'='*60}")
    
    # 反轉判斷邏輯
    signals = []
    
    if daily is not None:
        # KD高檔死亡交叉
        if k > 70 and k_prev >= d_prev and k < d:
            signals.append(("🔴 死亡交叉", "高檔死亡交叉，強烈反轉訊號"))
        
        # RSI背離
        if rsi > 70 and (daily["close"].iloc[-5] < daily["close"].iloc[-1] if len(daily) >= 5 else False):
            signals.append(("⚠️ RSI背離", "價格創高但RSI未創高，反轉前兆"))
        
        # 爆量不漲
        if vol_r > 2 and k < d:
            signals.append(("⚠️ 爆量不漲", "成交量放大但價格不漲，出貨嫌疑"))
        
        # 量價背離
        if k_days5 and k_change > 15 and vol_r < 0.8:
            signals.append(("⚡ 量價背離", "K值快速上升但量能萎縮，動能不足"))
    
    if today_tick is not None:
        # 最後5分鐘轉弱
        if len(last5m) > 1 and m5_down > m5_up * 2:
            signals.append(("🔴 尾盤殺", f"最後5分鐘下跌{m5_down}筆遠多於上漲{m5_up}筆"))
        
        # 大單賣壓
        if big_down > 0 and big_vol_down > big_vol_up * 1.5:
            signals.append(("🔴 大戶出貨", f"大單賣{big_vol_down}股 > 大單買{big_vol_up}股"))
            sell_pressure = round(big_vol_down / max(big_vol_up, 1), 1)
            print(f"  ⚡ 大戶賣/買比: {sell_pressure}")
        
        # 上漲量遠小於下跌量
        if up_vol < down_vol and up < down:
            signals.append(("🔴 賣壓沉重", f"上漲tick({up_ratio}%) < 下跌tick, 且上漲量({up_vol_ratio}%) < 下跌量"))
    
    if not signals:
        signals.append(("🟢 無明顯反轉", "目前盤勢正常"))
    
    for icon, desc in signals:
        print(f"  {icon}: {desc}")
    
    # ---- 策略建議 ----
    print(f"\n💡 策略建議:")
    if any("死亡交叉" in s[0] for s in signals) or any("大戶出貨" in s[0] for s in signals):
        print(f"  🔴 建議減碼或出場觀望")
    elif any("背離" in s[0] for s in signals) or any("尾盤殺" in s[0] for s in signals):
        print(f"  ⚠️ 持有可考慮部分獲利了結，暫不加碼")
    elif any("超賣" in str(daily.iloc[-1]) for s in signals):
        print(f"  💡 超賣區可留意反彈機會")
    else:
        print(f"  ⚪ 盤勢正常，續抱觀察")

if __name__ == "__main__":
    analyze_reversal("旺宏", "2337")
    analyze_reversal("晶技", "3042")
