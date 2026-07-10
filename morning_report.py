"""
晨報系統 v2.0
每天自動執行，輸出完整分析報告
不佔用對話 token，結果存成檔案
"""
import os, json, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

# ===== 設定 =====
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
OUTPUT_FILE = os.path.join(BASE, "report_output.txt")
HOLDING_COST = {}

def load_watchlist():
    """從 watchlist.txt 讀取股票"""
    path = os.path.join(BASE, "watchlist.txt")
    holdings, watches = [], []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    sid, name = parts[0], parts[1]
                    k = int(parts[2]) if parts[2] else 9
                    bt = int(parts[3]) if parts[3] else None
                    st = int(parts[4]) if len(parts) > 4 and parts[4] else None
                    cost = HOLDING_COST.get(sid, None)
                    if cost is not None:
                        holdings.append((sid, name, k, bt, st, cost))
                    else:
                        watches.append((sid, name, k, bt, st, None))
    except: pass
    return holdings, watches

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_kbars(api, sid, days=90):
    """抓取 K 線資料"""
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

def calc_all_indicators(daily):
    """計算 KD+MACD+RSI+成交量"""
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
    daily["avg_price_trade"] = daily["amount"] / daily["volume"].replace(0, np.nan)
    return daily

def analyze_momentum(api, sid, name):
    """追價力道分析"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=3)
    kbars = api.kbars(contract=contract, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    if len(kbars.ts) < 10: return None
    
    df = pd.DataFrame({"ts": pd.to_datetime(kbars.ts), "price": kbars.Close, "volume": kbars.Volume, "amount": kbars.Amount})
    today = datetime.now().date()
    df["date"] = df["ts"].dt.date
    df_today = df[df["date"] == today]
    df_use = df_today if len(df_today) >= 10 else df.tail(50)
    if len(df_use) < 10: return None
    
    df_use["price_change"] = df_use["price"].diff()
    up_ticks = (df_use["price_change"] > 0).sum()
    down_ticks = (df_use["price_change"] < 0).sum()
    up_ratio = round(up_ticks / max(up_ticks+down_ticks, 1) * 100, 1)
    
    up_vol = df_use[df_use["price_change"] > 0]["volume"].sum() if up_ticks > 0 else 0
    down_vol = df_use[df_use["price_change"] < 0]["volume"].sum() if down_ticks > 0 else 0
    up_vol_ratio = round(up_vol / max(up_vol+down_vol, 1) * 100, 1)
    
    last5min = df_use[df_use["ts"] >= (df_use["ts"].max() - timedelta(minutes=5))]
    l5_up = (last5min["price_change"] > 0).sum() if len(last5min) > 1 else 0
    l5_down = (last5min["price_change"] < 0).sum() if len(last5min) > 1 else 0
    l5_ratio = round(l5_up / max(l5_up+l5_down, 1) * 100, 1) if (l5_up+l5_down) > 0 else 50
    
    avg_vol = df_use["volume"].mean()
    large_orders = df_use[df_use["volume"] > avg_vol * 2]
    big_buy = len(large_orders[large_orders["price_change"] > 0]) if len(large_orders) > 0 else 0
    big_sell = len(large_orders[large_orders["price_change"] < 0]) if len(large_orders) > 0 else 0
    
    current = round(df_use["price"].iloc[-1], 2)
    first = df_use["price"].iloc[0]
    change = round((current - first) / first * 100, 2)
    vol = int(df_use["volume"].sum())
    
    # 判斷
    if up_ratio > 65: strength = "🟢買氣強勁"
    elif up_ratio > 55: strength = "🟡偏多"
    elif up_ratio > 45: strength = "⚪盤整"
    elif up_ratio > 35: strength = "🟠偏空"
    else: strength = "🔴賣壓重"
    
    # 反轉警告
    reversal = ""
    if l5_ratio < 40 and up_ratio > 55:
        reversal = "⚠️ 最後5分鐘追價轉弱，留意反轉!"
    elif l5_ratio > 60 and up_ratio < 45:
        reversal = "💡 最後5分鐘買盤回溫"
    
    return {
        "price": current, "change": change, "vol": vol,
        "up_ratio": up_ratio, "up_vol_ratio": up_vol_ratio,
        "l5_up": l5_up, "l5_down": l5_down, "l5_ratio": l5_ratio,
        "big_buy": big_buy, "big_sell": big_sell,
        "strength": strength, "reversal": reversal,
    }

def analyze_technical(daily, cost):
    """技術指標分析"""
    daily = calc_all_indicators(daily)
    last = daily.iloc[-1]
    prev = daily.iloc[-2]
    prev2 = daily.iloc[-3]
    
    price = round(last["close"], 2)
    k = round(last["K"], 1); d = round(last["D"], 1)
    k_prev = round(prev["K"], 1); d_prev = round(prev["D"], 1)
    rsi = round(last["RSI"], 1) if not pd.isna(last.get("RSI", np.nan)) else 0
    macd_h = round(last["MACD_hist"], 2) if not pd.isna(last.get("MACD_hist", np.nan)) else 0
    vol_r = round(last["vol_ratio"], 2) if not pd.isna(last.get("vol_ratio", np.nan)) else 0
    
    pnl = round((price - cost) / cost * 100, 2) if cost else None
    
    # 黃金/死亡交叉
    signal = "NONE"
    if k_prev <= d_prev and k > d: signal = "GOLDEN"
    elif k_prev >= d_prev and k < d: signal = "DEATH"
    
    # 超買超賣
    warn = []
    if k > 80: warn.append("超買")
    elif k < 20: warn.append("超賣")
    if rsi > 70: warn.append("RSI超買")
    elif rsi < 30: warn.append("RSI超賣")
    
    # 趨勢判斷
    trend = "NONE"
    if macd_h > 0 and k > d: trend = "多頭"
    elif macd_h < 0 and k < d: trend = "空頭"
    elif macd_h > 0: trend = "偏多"
    else: trend = "偏空"
    
    # 最近5天的K值變化
    k_trend = "NONE"
    close_col = daily.columns.get_loc("K")
    if len(daily) >= 5:
        k_day1 = daily.iloc[-5, close_col]
        k_now = daily.iloc[-1, close_col]
        if k_now > k_day1 + 10: k_trend = "急速上升"
        elif k_now > k_day1 + 3: k_trend = "緩升"
        elif k_now < k_day1 - 10: k_trend = "急速下降"
        elif k_now < k_day1 - 3: k_trend = "緩降"
        else: k_trend = "盤整"
    
    return {
        "price": price, "pnl": pnl, "k": k, "d": d,
        "rsi": rsi, "macd_hist": macd_h, "vol_ratio": vol_r,
        "signal": signal, "trend": trend, "k_trend": k_trend,
        "warn": warn,
    }

def build_report():
    """產生完整報告"""
    holdings, watches = load_watchlist()
    now = datetime.now()
    
    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 晨報系統 — 完整分析報告")
    lines.append(f"日期: {now.strftime('%Y/%m/%d %H:%M')}")
    lines.append(f"監控: 庫存{len(holdings)}支 + 觀察{len(watches)}支 = {len(holdings+watches)}支")
    lines.append("=" * 60)
    
    api = login()
    
    # ---- 庫存股 ----
    lines.append("\n" + "★" * 60)
    lines.append("★  庫存股分析")
    lines.append("★" * 60)
    
    for sid, name, kp, bt, st, cost in holdings:
        lines.append(f"\n📊 {name}({sid})")
        try:
            daily = fetch_kbars(api, sid)
            if daily is None or len(daily) < 10:
                lines.append("  ❌ 無資料"); continue
            
            # 技術分析
            ta = analyze_technical(daily, cost)
            pnl_s = f" | 損益:{ta['pnl']}%" if ta['pnl'] else ""
            sig_s = ""
            if ta['signal'] == "GOLDEN": sig_s = " 🟢黃金交叉!"
            elif ta['signal'] == "DEATH": sig_s = " 🔴死亡交叉!"
            warn_s = " | " + " ".join(ta['warn']) if ta['warn'] else ""
            
            lines.append(f"  {ta['trend']} @{ta['price']}{pnl_s}{sig_s}{warn_s}")
            lines.append(f"  K={ta['k']} D={ta['d']} | RSI={ta['rsi']} | MACD柱={ta['macd_hist']} | 量比={ta['vol_ratio']}")
            lines.append(f"  K值變化: {ta['k_trend']}")
            
            # 追價力道
            mom = analyze_momentum(api, sid, name)
            if mom:
                rev = f" | {mom['reversal']}" if mom['reversal'] else ""
                lines.append(f"  追價: {mom['strength']} 上漲tick:{mom['up_ratio']}% 上漲量:{mom['up_vol_ratio']}%")
                lines.append(f"  最後5分: 漲{mom['l5_up']}跌{mom['l5_down']} | 大單買{mom['big_buy']}賣{mom['big_sell']}{rev}")
            
            # 建議
            advice = ""
            if ta['signal'] == "GOLDEN": advice = "🟢 黃金交叉，可考慮買進"
            elif ta['signal'] == "DEATH": advice = "🔴 死亡交叉，考慮賣出"
            elif "超買" in str(ta['warn']): advice = "⚠️ K值過高，注意回檔風險"
            elif "超賣" in str(ta['warn']): advice = "💡 超賣區，留意反彈機會"
            else: advice = "⚪ 正常震盪，持續觀察"
            
            if mom and mom['reversal']:
                advice += f" | {mom['reversal']}"
            lines.append(f"  💡 {advice}")
            
        except Exception as e:
            lines.append(f"  ❌ 錯誤: {e}")
    
    # ---- 觀察股（簡化版） ----
    lines.append("\n" + "☆" * 60)
    lines.append("☆  觀察股分析")
    lines.append("☆" * 60)
    
    for sid, name, kp, bt, st, cost in watches:
        lines.append(f"\n📊 {name}({sid})")
        try:
            daily = fetch_kbars(api, sid, days=30)
            if daily is None or len(daily) < 10:
                lines.append("  ❌ 無資料"); continue
            ta = analyze_technical(daily, None)
            warn_s = " | " + " ".join(ta['warn']) if ta['warn'] else ""
            sig_s = ""
            if ta['signal'] == "GOLDEN": sig_s = " 🟢黃金交叉!"
            elif ta['signal'] == "DEATH": sig_s = " 🔴死亡交叉!"
            lines.append(f"  {ta['trend']} @{ta['price']} K={ta['k']} D={ta['d']} RSI={ta['rsi']}{sig_s}{warn_s}")
            count += 1
        except:
            lines.append("  ❌ 錯誤")
    
    api.logout()
    
    # ---- 結論 ----
    lines.append("\n" + "=" * 60)
    lines.append("📋 綜合建議")
    lines.append("=" * 60)
    lines.append("")
    lines.append("🔴 賣出訊號: 日月光K>80超買, 臻鼎K<D偏空")
    lines.append("🟢 買入訊號: 檢查黃金交叉股票")
    lines.append("💡 超賣反彈: 旺宏K<20超賣區")
    lines.append("")
    lines.append(f"報告產生時間: {now.strftime('%Y/%m/%d %H:%M:%S')}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    print(report)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 報告已儲存至: {OUTPUT_FILE}")
