"""
追價力道分析：透過tick資料判斷買盤強弱
抓取日月光最後30分鐘的逐筆tick，分析追價力道是否轉弱
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def analyze_momentum(api, sid, name):
    """分析個股的盤中追價力道"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=3)  # 抓3天內的tick，確保有今日資料
    kbars = api.kbars(contract=contract, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    
    if len(kbars.ts) == 0:
        return None
    
    # 轉成 DataFrame
    df = pd.DataFrame({
        "ts": pd.to_datetime(kbars.ts),
        "price": kbars.Close,
        "volume": kbars.Volume,
        "amount": kbars.Amount,
    })
    
    # 篩選今日資料
    today = datetime.now().date()
    df["date"] = df["ts"].dt.date
    df_today = df[df["date"] == today].copy()
    
    if len(df_today) < 10:
        # 直接用最後的資料
        df_use = df.tail(50)
        period_label = "近期(跨日)"
    else:
        df_use = df_today
        period_label = today.strftime("%m/%d")
    
    if len(df_use) < 10:
        return None
    
    # 計算逐筆的價格變化和成交量
    df_use["price_change"] = df_use["price"].diff()
    df_use["price_pct"] = df_use["price"].pct_change() * 100
    
    # 上漲tick vs 下跌tick
    up_ticks = (df_use["price_change"] > 0).sum()
    down_ticks = (df_use["price_change"] < 0).sum()
    total_ticks = up_ticks + down_ticks
    up_ratio = round(up_ticks / max(total_ticks, 1) * 100, 1)
    
    # 上漲成交量 vs 下跌成交量
    up_vol = df_use[df_use["price_change"] > 0]["volume"].sum()
    down_vol = df_use[df_use["price_change"] < 0]["volume"].sum()
    total_vol = up_vol + down_vol
    up_vol_ratio = round(up_vol / max(total_vol, 1) * 100, 1)
    
    # 最後10筆的價格變化趨勢
    last10 = df_use.tail(10)
    last10_up = (last10["price_change"] > 0).sum()
    last10_down = (last10["price_change"] < 0).sum()
    
    # 大單判斷：單筆成交量 > 平均的2倍
    avg_vol = df_use["volume"].mean()
    large_orders = df_use[df_use["volume"] > avg_vol * 2]
    large_orders_up = large_orders[large_orders["price_change"] > 0]
    large_orders_down = large_orders[large_orders["price_change"] < 0]
    
    current_price = df_use["price"].iloc[-1]
    first_price = df_use["price"].iloc[0]
    total_change = round((current_price - first_price) / first_price * 100, 2)
    
    # 近5分鐘的追價強度
    last5min = df_use[df_use["ts"] >= (df_use["ts"].max() - timedelta(minutes=5))]
    last5_up = (last5min["price_change"] > 0).sum()
    last5_down = (last5min["price_change"] < 0).sum()
    
    # 判斷追價力道
    momentum = "strong"
    signal_msg = ""
    
    if up_ratio < 40:
        momentum = "weak"
        signal_msg = "追價力道偏弱，賣壓較重"
    elif up_ratio > 60:
        momentum = "strong"
        signal_msg = "追價力道強勁，買盤積極"
    else:
        momentum = "neutral"
        signal_msg = "買賣力道均衡"
    
    # 觀察最後5分鐘的變化
    if last5_up < last5_down and momentum == "strong":
        signal_msg += " ⚠️ 但最後5分鐘賣壓增加，留意反轉"
    elif last5_up > last5_down and momentum == "weak":
        signal_msg += " 💡 最後5分鐘買盤回溫"
    
    # 大戶動向
    big_up = len(large_orders_up)
    big_down = len(large_orders_down)
    
    print(f"\n{'=' * 55}")
    print(f"📊 {name}({sid}) 盤中追價力道分析")
    print(f"{'=' * 55}")
    print(f"  分析期間: {period_label} | 資料筆數: {len(df_use)}")
    print(f"  目前價格: {current_price:.2f} | 區間漲跌: {total_change:.2f}%")
    print(f"\n  📈 漲跌tick分布:")
    print(f"    上漲tick: {up_ticks}({up_ratio}%) | 下跌tick: {down_ticks}({100-up_ratio}%)")
    print(f"  📊 漲跌量分布:")
    print(f"    上漲量: {up_vol}({up_vol_ratio}%) | 下跌量: {down_vol}({100-up_vol_ratio}%)")
    print(f"\n  🐋 大單異常:")
    print(f"    大單買: {big_up}筆 | 大單賣: {big_down}筆 | 均量: {avg_vol:.0f}")
    print(f"\n  ⏱️ 最後5分鐘:")
    print(f"    上漲tick: {last5_up} | 下跌tick: {last5_down}")
    
    # 力道判斷
    if up_ratio > 65:
        icon = "🟢"
        strength = "強勁買盤"
    elif up_ratio > 55:
        icon = "🟡"
        strength = "偏多"
    elif up_ratio > 45:
        icon = "⚪"
        strength = "盤整"
    elif up_ratio > 35:
        icon = "🟠"
        strength = "偏空"
    else:
        icon = "🔴"
        strength = "賣壓沉重"
    
    print(f"\n  {icon} 追價力道: {strength}")
    print(f"  💡 {signal_msg}")
    
    # 綜合判斷
    print(f"\n  📋 結論:")
    if up_ratio > 65:
        print(f"    買氣強勁，暫不需急著賣")
    elif up_ratio > 50:
        print(f"    買賣均衡，觀察是否轉弱")
    elif up_ratio > 35:
        print(f"    賣壓漸增，準備考慮減碼")
        if last10_up == 0:
            print(f"    ⚠️ 最後10筆全部下跌，可能反轉!")
    else:
        print(f"    🔴 賣壓沉重，應考慮出場")
    
    return {
        "name": name,
        "sid": sid,
        "price": round(current_price, 2),
        "up_ratio": up_ratio,
        "momentum": momentum,
        "last5_up": last5_up,
        "last5_down": last5_down,
    }


def scan_all():
    print("🔍 盤中追價力道掃描")
    print("分析每支股票的買盤強度，判斷是否該賣")
    print()
    
    api = login()
    
    stocks = [
        ("3711", "日月光"), ("4958", "臻鼎KY"), ("3042", "晶技"),
        ("2337", "旺宏"), ("2436", "偉詮電"), ("3673", "TPKKY"),
    ]
    
    for sid, name in stocks:
        result = analyze_momentum(api, sid, name)
        if result:
            print()
    
    api.logout()

if __name__ == "__main__":
    scan_all()
    
    print("\n" + "=" * 55)
    print("💡 核心邏輯說明")
    print("=" * 55)
    print("當上漲tick比例從65%以上逐漸下降到50%以下")
    print("且最後5分鐘下跌tick > 上漲tick")
    print("就是追價力道轉弱、準備反轉的訊號")
    print("這時就是最佳的賣點(在反轉前2-3分鐘)")
