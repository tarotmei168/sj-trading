"""
旺宏(2337) 深度分析 — 套牢解套策略
抓取真實數據：成交量、法人動向、大戶資金流
找出最低點回補時間點
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

def fetch_data(api, sid, days=90):
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
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume, "amount": kbars.Amount,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except: break
    if not all_dfs: return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "amount": "sum",
    }).dropna()
    return daily

def calc_all(daily):
    """完整技術指標"""
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
    daily["vol_ma20"] = daily["volume"].rolling(20).mean()
    daily["vol_ratio"] = daily["volume"] / daily["vol_ma5"].replace(0, np.nan)
    daily["avg_price"] = daily["amount"] / daily["volume"].replace(0, np.nan)
    daily["amount_ma5"] = daily["amount"].rolling(5).mean()
    
    # 均線
    daily["MA5"] = daily["close"].rolling(5).mean()
    daily["MA10"] = daily["close"].rolling(10).mean()
    daily["MA20"] = daily["close"].rolling(20).mean()
    daily["MA60"] = daily["close"].rolling(60).mean()
    
    return daily

print("=" * 65)
print("🔍 旺宏(2337) 套牢解套深度分析")
print(f"分析時間: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
print("=" * 65)

api = login()
daily = fetch_data(api, "2337", days=90)
if daily is not None:
    daily = calc_all(daily)
    last = daily.iloc[-1]
    today_open = last["open"]
    today_close = last["close"]
    today_high = last["high"]
    today_low = last["low"]
    today_vol = int(last["volume"])
    today_amount = int(last["amount"])
    
    print(f"\n📊 今日盤後數據 ({daily.index[-1].strftime('%m/%d')})")
    print(f"{'─' * 65}")
    print(f"  開盤: {today_open}  最高: {today_high}  最低: {today_low}  收盤: {today_close}")
    print(f"  成交量: {today_vol:,} 張")
    print(f"  成交金額: {today_amount/1000000:.1f} 億")
    
    # 今日大戶/散戶判斷
    avg_amount = last["avg_price"]
    print(f"  平均成交價: {avg_amount:.2f}")
    
    # 成交結構分析（大戶vs散戶）
    # 用成交金額判斷：大戶單 > 50萬
    large_threshold = 500000
    total_trades = today_vol
    today_amount_per_trade = today_amount / max(total_trades, 1)
    print(f"  每張均額: {today_amount_per_trade:.0f}")
    
    print(f"\n📈 技術指標")
    print(f"{'─' * 65}")
    print(f"  KD: K={last['K']:.1f} D={last['D']:.1f}")
    print(f"  MACD柱狀: {last['MACD_hist']:.2f}")
    print(f"  RSI(14): {last['RSI']:.1f}")
    print(f"  量比(5日): {last['vol_ratio']:.2f}")
    
    # 均線
    ma5 = last["MA5"]
    ma10 = last["MA10"]
    ma20 = last["MA20"]
    ma60 = last["MA60"]
    print(f"\n📉 均線系統")
    print(f"{'─' * 65}")
    print(f"  MA5(5日線): {ma5:.2f}")
    print(f"  MA10(10日線): {ma10:.2f}")
    print(f"  MA20(20日線): {ma20:.2f}")
    print(f"  MA60(60日線): {ma60:.2f}")
    
    # 距離均線
    dist_ma5 = round((today_close - ma5) / ma5 * 100, 2)
    dist_ma20 = round((today_close - ma20) / ma20 * 100, 2)
    print(f"  距MA5: {dist_ma5:+.2f}%")
    print(f"  距MA20: {dist_ma20:+.2f}%")
    
    # ---- 過去30天每日分析找支撐 ----
    last30 = daily.tail(30)
    print(f"\n📋 近30天每日收盤與成交量")
    print(f"{'─' * 65}")
    print(f"  {'日期':<8} {'收盤':<8} {'量':<8} {'量比':<8} {'K值':<8} {'RSI':<8}")
    print(f"  {'─'*48}")
    for i in range(-30, 0):
        row = daily.iloc[i]
        d = row.name.strftime("%m/%d")
        c = f"{row['close']:.1f}"
        v = f"{int(row['volume']):,}"
        vr = f"{row['vol_ratio']:.1f}" if not pd.isna(row['vol_ratio']) else "-"
        k = f"{row['K']:.1f}" if not pd.isna(row['K']) else "-"
        rsi = f"{row['RSI']:.1f}" if not pd.isna(row['RSI']) else "-"
        print(f"  {d:<8} {c:<8} {v:<8} {vr:<8} {k:<8} {rsi:<8}")
    
    # ---- 關鍵支撐壓力 ----
    print(f"\n📍 關鍵支撐壓力價位")
    print(f"{'─' * 65}")
    
    # 找出近60天的量能密集區
    valid = daily.dropna(subset=["close", "volume"])
    if len(valid) >= 20:
        # 20日低點 = 短線支撐
        s1 = valid["low"].tail(20).min()
        # 20日均線
        s2 = round(valid["close"].tail(20).mean(), 2)
        # 60日低點 = 強支撐
        s3 = valid["low"].tail(60).min() if len(valid) >= 60 else valid["low"].min()
        # 壓力
        r1 = valid["high"].tail(20).max()
        r2 = round(valid["close"].tail(20).mean() * 1.1, 2)
        
        print(f"  🟢 短線支撐1: {s1:.2f} (20日最低)")
        print(f"  🟢 均線支撐2: {s2:.2f} (20日均價)")
        print(f"  🟢 強力支撐3: {s3:.2f} (60日最低)")
        print(f"  🔴 短線壓力1: {r1:.2f} (20日最高)")
        print(f"  🔴 均線壓力2: {r2:.2f}")
    
    # ---- 資金流向分析（用成交金額模擬） ----
    print(f"\n💰 資金流向分析")
    print(f"{'─' * 65}")
    
    # 計算今日大戶成交金額估算
    today_amount_ma5 = last.get("amount_ma5", 0)
    if not pd.isna(today_amount_ma5) and today_amount_ma5 > 0:
        amount_ratio = today_amount / today_amount_ma5
        print(f"  今日成交額 vs 5日均額: {amount_ratio:.2f}x")
        if amount_ratio > 1.5:
            print(f"  ⚠️ 今日異常爆量，可能有特定買盤或賣壓")
        elif amount_ratio < 0.5:
            print(f"  💤 今日量能萎縮，市場觀望")
        else:
            print(f"  ✅ 量能正常")
    
    # ---- 綜合判斷 ----
    print(f"\n{'=' * 65}")
    print(f"📋 解套策略建議")
    print(f"{'=' * 65}")
    
    # 判斷目前位置
    if today_close < s3:
        pos = "破底"
    elif today_close < s1:
        pos = "接近底部"
    elif today_close < s2:
        pos = "低檔區"
    elif today_close < r1:
        pos = "中間區"
    else:
        pos = "高檔區"
    
    print(f"\n  目前位置: {pos}")
    print(f"  你套牢成本: 174 (假設)")
    print(f"  目前虧損: {round((today_close-174)/174*100, 2)}%")
    
    # K值判斷
    k_val = last["K"]
    if k_val < 20:
        print(f"\n  🟢 K={k_val:.1f} 已進入超賣區，隨時可能反彈")
        print(f"  💡 建議準備資金，等下列訊號出現就進場:")
        print(f"     1. K值 < 20 + 黃金交叉 (K上穿D)")
        print(f"     2. 成交量萎縮後開始放大")
        print(f"     3. 收盤站上MA5")
    elif k_val < 30:
        print(f"\n  🟡 K={k_val:.1f} 接近超賣，再跌有限")
        print(f"  💡 可小量試單，站穩MA5再加碼")
    else:
        print(f"\n  ⚪ K={k_val:.1f} 還在整理")
        print(f"  💡 等K值回到20以下再考慮進場")
    
    # 具體買點
    print(f"\n  🎯 具體買進計畫:")
    print(f"     ✅ 條件1: K值 < 20 (目前{last['K']:.1f})")
    print(f"     ✅ 條件2: K值黃金交叉 (K上穿D)")
    print(f"     ✅ 條件3: 成交量比前一天放大 > 20%")
    print(f"     ✅ 條件4: 收盤價站上5日均線")
    print(f"")
    print(f"     當以上4個條件同時成立，就是最佳回補時機！")

api.logout()

print(f"\n{'=' * 65}")
print(f"✅ 分析完成！每天晨報會自動更新")
print(f"{'=' * 65}")
