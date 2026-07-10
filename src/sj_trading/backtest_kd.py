"""
KD 黃金/死亡交叉回測系統
使用 Shioaji API 抓取歷史1分K，合併成日K後回測 KD 買賣訊號
"""
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import shioaji as sj

load_dotenv()


def login():
    """登入 Shioaji"""
    api = sj.Shioaji(simulation=True)
    api.login(
        api_key=os.environ["SJ_API_KEY"],
        secret_key=os.environ["SJ_SEC_KEY"],
    )
    return api


def fetch_kbars_daily(api, stock_id, days=90):
    """抓取過去 N 天的日 K 線（由1分K合併）"""
    end = datetime.now()
    start = end - timedelta(days=days)
    
    contract = api.Contracts.Stocks[stock_id]
    
    # 分批抓取1分K (限制最多 29 天/批)
    max_days = 29
    all_min_dfs = []
    seg_end = end
    
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=max_days), start)
        try:
            kbars = api.kbars(
                contract=contract,
                start=seg_start.strftime("%Y-%m-%d"),
                end=seg_end.strftime("%Y-%m-%d"),
            )
            if len(kbars.ts) == 0:
                break
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open,
                "high": kbars.High,
                "low": kbars.Low,
                "close": kbars.Close,
                "volume": kbars.Volume,
            })
            all_min_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except Exception as e:
            print(f"      分批抓取失敗: {e}")
            break
    
    if not all_min_dfs:
        return pd.DataFrame()
    
    min_df = pd.concat(all_min_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    
    # 合併成日K
    daily = min_df.resample("D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    
    daily.index.name = "date"
    return daily


def compute_kd(df, k_period=9):
    """計算 KD 值"""
    k = df["close"].rolling(k_period)
    df["RSV"] = ((df["close"] - df["low"].rolling(k_period).min()) / 
                 (df["high"].rolling(k_period).max() - df["low"].rolling(k_period).min())) * 100
    df["RSV"] = df["RSV"].fillna(50)
    
    # 使用遞迴計算
    df["K"] = 50.0
    df["D"] = 50.0
    
    for i in range(k_period, len(df)):
        df.iloc[i, df.columns.get_loc("K")] = (2/3) * df.iloc[i-1]["K"] + (1/3) * df.iloc[i]["RSV"]
        df.iloc[i, df.columns.get_loc("D")] = (2/3) * df.iloc[i-1]["D"] + (1/3) * df.iloc[i]["K"]
    
    return df


def find_signals(df, k_period=9, buy_threshold=None, sell_threshold=None):
    """找出黃金交叉(買)和死亡交叉(賣)"""
    valid = df.dropna(subset=["K", "D"]).copy()
    valid["prev_K"] = valid["K"].shift(1)
    valid["prev_D"] = valid["D"].shift(1)
    
    # 黃金交叉
    buy = (valid["prev_K"] <= valid["prev_D"]) & (valid["K"] > valid["D"])
    if buy_threshold:
        buy = buy & (valid["K"] < buy_threshold)
    
    # 死亡交叉
    sell = (valid["prev_K"] >= valid["prev_D"]) & (valid["K"] < valid["D"])
    if sell_threshold:
        sell = sell & (valid["K"] > sell_threshold)
    
    valid["signal"] = 0
    valid.loc[buy, "signal"] = 1
    valid.loc[sell, "signal"] = -1
    
    return valid


def backtest(df):
    """回測 KD 交叉策略"""
    trades = []
    position = 0
    buy_price = 0
    buy_date = None
    total_pnl = 0
    wins = 0
    losses = 0
    
    for idx, row in df.iterrows():
        if row["signal"] == 1 and position == 0:
            position = 1
            buy_price = row["close"]
            buy_date = idx
        elif row["signal"] == -1 and position == 1:
            position = 0
            pnl_pts = row["close"] - buy_price
            pnl_pct = (row["close"] - buy_price) / buy_price * 100
            total_pnl += pnl_pts
            if pnl_pts > 0:
                wins += 1
            else:
                losses += 1
            trades.append({
                "買入": buy_date.strftime("%m/%d"),
                "賣出": idx.strftime("%m/%d"),
                "買價": round(buy_price, 2),
                "賣價": round(row["close"], 2),
                "獲利%": round(pnl_pct, 2),
                "賺賠": round(pnl_pts, 2),
            })
    
    # 最後持有未賣
    if position == 1:
        trades.append({
            "買入": buy_date.strftime("%m/%d"),
            "賣出": "持有中",
            "買價": round(buy_price, 2),
            "賣價": "-",
            "獲利%": "-",
            "賺賠": "-",
        })
    
    return trades, total_pnl, wins, losses


def run_backtest(stock_id, stock_name, k_period=9, buy_threshold=None, sell_threshold=None, days=90):
    """對單一股票執行完整回測"""
    sep = "=" * 55
    print(f"\n{sep}")
    print(f"📊 {stock_name} ({stock_id}) — K={k_period}" +
          (f" 買<{buy_threshold}" if buy_threshold else "") +
          (f" 賣>{sell_threshold}" if sell_threshold else ""))
    print(sep)
    
    try:
        api = login()
        daily = fetch_kbars_daily(api, stock_id, days=days)
        api.logout()
        
        if daily.empty:
            print("   ❌ 無資料")
            return [], 0
        
        print(f"   區間: {daily.index[0].strftime('%m/%d')} ~ {daily.index[-1].strftime('%m/%d')}")
        print(f"   交易日: {len(daily)} 天")
        print(f"   最新價: {daily['close'][-1]:.2f}")
        
        daily = compute_kd(daily, k_period)
        daily = find_signals(daily, k_period, buy_threshold, sell_threshold)
        trades, total_pnl, wins, losses = backtest(daily)
        
        print(f"\n   📋 回測結果:")
        print(f"   交易次數: {len([t for t in trades if t['賣出'] != '持有中'])}")
        if trades:
            closed = [t for t in trades if t["賣出"] != "持有中"]
            if closed:
                print(f"   獲利: {wins}次  虧損: {losses}次")
                sr = wins / max(wins + losses, 1) * 100
                print(f"   總損益: {total_pnl:.2f} 點  勝率: {sr:.1f}%")
                
                print(f"\n   📅 交易明細:")
                print(f"   {'買入':<8} {'買價':<8} {'賣出':<8} {'賣價':<8} {'獲利%':<8} {'賺賠':<8}")
                print(f"   {'-'*48}")
                for t in trades:
                    bp = f"{t['買價']:<8}"
                    sp = f"{t['賣價']:<8}" if t['賣出'] != "持有中" else "持有中   "
                    pp = f"{t['獲利%']}%" if t['獲利%'] != "-" else "-       "
                    pp2 = f"{t['賺賠']}" if t['賺賠'] != "-" else "-      "
                    print(f"   {t['買入']:<8} {bp} {t['賣出']:<8} {sp} {pp:<8} {pp2}")
            else:
                print("   持有中，無已完成交易")
        
        return trades, total_pnl
    
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return [], 0


# ===== 庫存股 (依晨報清單 2026/07/01) =====
HOLDING_STOCKS = [
    ("3711", "日月光", 3, 40, 65),
    ("4958", "臻鼎KY", 3, 40, 65),
    ("3042", "晶技", 5, None, 70),
    ("2337", "旺宏", 5, None, 70),
    ("2436", "偉詮電", 5, None, 70),
    ("3673", "TPKKY", 5, None, 70),
]

# ===== 觀察股 =====
WATCH_STOCKS = [
    ("2330", "台積電", 5, 50, 60),
    ("2454", "聯發科", 5, 50, 60),
    ("6139", "亞翔", 9, None, None),
    ("2303", "聯電", 9, None, None),
    ("2317", "鴻海", 9, None, None),
    ("8150", "南茂", 3, 45, 70),
    ("6284", "佳邦", 9, None, None),
    ("6213", "聯茂", 9, None, None),
    ("1303", "南亞", 9, None, None),
    ("1802", "台玻", 9, None, None),
    ("6271", "同欣電", 9, None, None),
    ("6451", "訊芯KY", 9, None, None),
    ("2327", "國巨", 9, None, None),
    ("6173", "信昌電", 9, None, None),
    ("5425", "台半", 9, None, None),
    ("3131", "弘塑", 9, None, None),
    ("3583", "辛耘", 9, None, None),
    ("6239", "力成", 9, None, None),
    ("2344", "華邦電", 9, None, None),
    ("2408", "南亞科", 9, None, None),
    ("6770", "力積電", 9, None, None),
]


def run_all_holdings():
    """回測所有庫存股"""
    print("\n" + "★" * 50)
    print("★  庫存股 KD 交叉回測 (近3個月)")
    print("★" * 50)
    for s in HOLDING_STOCKS:
        run_backtest(*s, days=90)


def run_all_watch():
    """回測所有觀察股"""
    print("\n" + "☆" * 50)
    print("☆  觀察股 KD 交叉回測 (近3個月)")
    print("☆" * 50)
    for s in WATCH_STOCKS:
        run_backtest(*s, days=90)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "holdings"
    if mode == "holdings":
        run_all_holdings()
    elif mode == "watch":
        run_all_watch()
    elif mode == "all":
        run_all_holdings()
        run_all_watch()
