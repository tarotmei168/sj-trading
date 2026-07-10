"""
多指標綜合分析：KD + MACD + RSI + 成交量
自動判斷每支股票的交易模式（趨勢/區間/混合）
並給出最佳策略
"""
import os, sys, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

STOCKS = [
    ("3711", "日月光"), ("4958", "臻鼎KY"), ("3042", "晶技"),
    ("2337", "旺宏"), ("2436", "偉詮電"), ("3673", "TPKKY"),
    ("8150", "南茂"),
]

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_data(api, sid, days=90):
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=days)
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
        if len(kbars.ts) == 0: break
        df = pd.DataFrame({"datetime": pd.to_datetime(kbars.ts), "open": kbars.Open, "high": kbars.High, "low": kbars.Low, "close": kbars.Close, "volume": kbars.Volume, "amount": kbars.Amount})
        all_dfs.append(df)
        seg_end = seg_start - timedelta(seconds=1)
    if not all_dfs: return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "amount": "sum"}).dropna()
    return daily

def calc_indicators(daily):
    kp = 9
    low_min = daily["low"].rolling(kp).min()
    high_max = daily["high"].rolling(kp).max()
    rsv = ((daily["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)
    k_vals = [50]*kp; d_vals = [50]*kp
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

def detect_pattern(daily):
    valid = daily.dropna(subset=["K","D","RSI","MACD_hist","vol_ratio"])
    if len(valid) < 40: return "mixed"
    days30 = valid.iloc[-30:]
    # 區間判斷：看60天內最高最低點差異
    high60 = valid["close"].rolling(60).max().iloc[-1]
    low60 = valid["close"].rolling(60).min().iloc[-1]
    range_pct = (high60 - low60) / low60 * 100
    # 價格波動率
    price_vol = days30["close"].pct_change().std()
    macd_flips = ((days30["MACD_hist"] > 0).astype(int).diff().abs().sum())
    # 60天波動 < 30% + MACD多次翻轉 => 區間
    if range_pct < 30 and macd_flips >= 3: return "range"
    elif price_vol > 0.025: return "trend"
    elif range_pct < 20: return "range"
    else: return "mixed"

def analyze_stock(name, sid, daily):
    if daily is None or len(daily) < 20: return None
    daily = calc_indicators(daily)
    pattern = detect_pattern(daily)
    last = daily.iloc[-1]
    
    close = round(last["close"], 2)
    k = round(last["K"], 1)
    d = round(last["D"], 1)
    rsi = round(last["RSI"], 1) if not pd.isna(last.get("RSI", np.nan)) else 0
    macd_h = round(last["MACD_hist"], 2) if not pd.isna(last.get("MACD_hist", np.nan)) else 0
    vol_r = round(last["vol_ratio"], 2) if not pd.isna(last.get("vol_ratio", np.nan)) else 0
    
    result = {"name": name, "sid": sid, "price": close, "k": k, "d": d, "rsi": rsi, "macd_hist": macd_h, "vol_ratio": vol_r, "pattern": pattern}
    
    if pattern == "range":
        valid = daily.dropna(subset=["close"])
        sup = round(valid["close"].rolling(20).min().iloc[-1], 2)
        res = round(valid["close"].rolling(20).max().iloc[-1], 2)
        rng = round((res-sup)/sup*100, 2)
        result.update({"support": sup, "resistance": res, "range_pct": rng})
        # 目前在區間哪個位置
        if close - sup < (res - sup) * 0.3: result["position"] = "接近支撐 (可考慮買)"
        elif res - close < (res - sup) * 0.3: result["position"] = "接近壓力 (可考慮賣)"
        else: result["position"] = "區間中間 (觀望)"
    elif pattern == "trend":
        result["position"] = "趨勢股"
    else:
        result["position"] = "混合型"
    
    return result

print("=" * 60)
print("📊 多指標分析：KD + MACD + RSI + 成交量")
print(f"掃描時間: {datetime.now().strftime('%m/%d %H:%M')}")
print("=" * 60)

api = login()
for sid, name in STOCKS:
    daily = fetch_data(api, sid)
    r = analyze_stock(name, sid, daily)
    if r is None: continue
    
    icons = {"range": "🔁 區間", "trend": "📈 趨勢", "mixed": "🔀 混合"}
    pi = icons.get(r["pattern"], "❓")
    macd_s = "🟢" if r["macd_hist"] > 0 else "🔴"
    rsi_s = ""
    if r["rsi"] < 30: rsi_s = " (超賣)"
    elif r["rsi"] > 70: rsi_s = " (超買)"
    
    print(f"\n{pi} {r['name']}({r['sid']}) @{r['price']}")
    print(f"  K={r['k']} D={r['d']} | RSI={r['rsi']}{rsi_s}")
    print(f"  MACD柱={macd_s}{r['macd_hist']} | 量比={r['vol_ratio']}")
    
    if r["pattern"] == "range":
        print(f"  區間: {r['support']} ←→ {r['resistance']} ({r['range_pct']}%)")
    print(f"  💡 {r['position']}")

api.logout()
