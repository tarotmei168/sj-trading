"""
KD 參數最佳化回測系統
針對每支股票自動掃描 K值、買入門檻、賣出門檻的所有組合
找出在過去3個月能產生最佳報酬率的策略
"""
import os, sys, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

# ===== 股票列表 =====
HOLDINGS = [
    ("3711", "日月光", 481),
    ("4958", "臻鼎KY", 461),
    ("3042", "晶技", 196),
    ("2337", "旺宏", 174),
    ("2436", "偉詮電", 76),
    ("3673", "TPKKY", 51.69),
]

WATCHES = [
    ("2330", "台積電", None), ("2454", "聯發科", None),
    ("6139", "亞翔", None), ("2303", "聯電", None),
    ("2317", "鴻海", None), ("8150", "南茂", None),
    ("6284", "佳邦", None), ("6213", "聯茂", None),
    ("1303", "南亞", None), ("1802", "台玻", None),
    ("6271", "同欣電", None), ("6451", "訊芯KY", None),
    ("2327", "國巨", None), ("6173", "信昌電", None),
    ("5425", "台半", None), ("3131", "弘塑", None),
    ("3583", "辛耘", None), ("6239", "力成", None),
    ("2344", "華邦電", None), ("2408", "南亞科", None),
    ("6770", "力積電", None),
]

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_all_daily(api, days=90):
    """一次登入，抓取所有股票的日K線"""
    results = {}
    for sid, name, _ in HOLDINGS + WATCHES:
        try:
            contract = api.Contracts.Stocks[sid]
            end = datetime.now()
            start = end - timedelta(days=days)
            
            all_dfs = []
            seg_end = end
            while seg_end > start:
                seg_start = max(seg_end - timedelta(days=29), start)
                kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
                if len(kbars.ts) == 0:
                    break
                df = pd.DataFrame({
                    "datetime": pd.to_datetime(kbars.ts),
                    "open": kbars.Open, "high": kbars.High,
                    "low": kbars.Low, "close": kbars.Close,
                })
                all_dfs.append(df)
                seg_end = seg_start - timedelta(seconds=1)
            
            if all_dfs:
                min_df = pd.concat(all_dfs)
                min_df.drop_duplicates(subset=["datetime"], inplace=True)
                min_df.sort_values("datetime", inplace=True)
                min_df.set_index("datetime", inplace=True)
                daily = min_df.resample("D").agg({
                    "open": "first", "high": "max", "low": "min", "close": "last",
                }).dropna()
                results[sid] = (name, daily)
                print(f"  ✅ {name}({sid}) {len(daily)}天", flush=True)
            else:
                print(f"  ❌ {name}({sid}) 無資料", flush=True)
        except Exception as e:
            print(f"  ❌ {name}({sid}) 錯誤: {e}", flush=True)
    return results

def compute_kd(df, k_period):
    """計算KD"""
    df = df.copy()
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)
    
    k_vals = [50] * k_period
    d_vals = [50] * k_period
    for i in range(k_period, len(df)):
        r = rsv.iloc[i] if isinstance(rsv, pd.Series) else rsv[i]
        k_new = (2/3) * k_vals[-1] + (1/3) * r
        d_new = (2/3) * d_vals[-1] + (1/3) * k_new
        k_vals.append(k_new)
        d_vals.append(d_new)
    
    df["K"] = k_vals
    df["D"] = d_vals
    return df

def backtest(df, k_period, buy_threshold, sell_threshold):
    """回測單一參數組合，返回總損益"""
    df = compute_kd(df, k_period)
    valid = df.dropna(subset=["K", "D"])
    
    if len(valid) < k_period + 5:
        return 0, 0, 0
    
    position = 0
    buy_price = 0
    total_pnl = 0
    trades = 0
    wins = 0
    
    for i in range(k_period + 1, len(valid)):
        k_now = valid["K"].iloc[i]
        d_now = valid["D"].iloc[i]
        k_prev = valid["K"].iloc[i-1]
        d_prev = valid["D"].iloc[i-1]
        close = valid["close"].iloc[i]
        
        # 黃金交叉
        if position == 0 and k_prev <= d_prev and k_now > d_now:
            if buy_threshold is None or k_now < buy_threshold:
                position = 1
                buy_price = close
                trades += 1
        
        # 死亡交叉
        elif position == 1 and k_prev >= d_prev and k_now < d_now:
            if sell_threshold is None or k_now > sell_threshold:
                position = 0
                pnl = close - buy_price
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
    
    # 最後持有未賣：以最新價格結算
    if position == 1:
        pnl = valid["close"].iloc[-1] - buy_price
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        trades += 1
    
    return total_pnl, trades, wins


def optimize_stock(sid, name, cost, daily):
    """對單一股票找最佳KD參數"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_range = [20, 25, 30, 35, 40, 45, 50, None]
    sell_range = [50, 55, 60, 65, 70, 75, 80, None]
    
    best = {"pnl": -99999, "k": 0, "buy": 0, "sell": 0, "trades": 0, "wins": 0}
    results = []
    
    print(f"\n📊 {name}({sid}) 參數最佳化中...", flush=True)
    
    total = len(k_range) * len(buy_range) * len(sell_range)
    count = 0
    for k in k_range:
        for bt in buy_range:
            for st in sell_range:
                pnl, trades, wins = backtest(daily, k, bt, st)
                count += 1
                if pnl > best["pnl"]:
                    best = {"pnl": pnl, "k": k, "buy": bt, "sell": st, "trades": trades, "wins": wins}
                results.append({"k": k, "buy": bt, "sell": st, "pnl": pnl, "trades": trades, "wins": wins})
    
    # 找前3名
    sorted_results = sorted([r for r in results if r["trades"] >= 2], key=lambda x: x["pnl"], reverse=True)[:3]
    
    current_price = daily["close"].iloc[-1]
    current_pnl = round((current_price - cost) / cost * 100, 2) if cost else None
    current_pnl_str = f" ({current_pnl}%)" if current_pnl else ""
    
    print(f"\n  {'='*50}", flush=True)
    print(f"  🏆 {name}({sid}) 最佳參數", flush=True)
    print(f"  {'='*50}")
    print(f"  目前股價: {current_price:.2f}{current_pnl_str}", flush=True)
    print(f"  ", flush=True)
    
    for i, r in enumerate(sorted_results, 1):
        bt_str = f"買<{r['buy']}" if r['buy'] else "無門檻"
        st_str = f"賣>{r['sell']}" if r['sell'] else "無門檻"
        win_rate = round(r["wins"] / max(r["trades"], 1) * 100, 1)
        print(f"  #{i} K={r['k']} {bt_str} {st_str} | 損益:{r['pnl']:.2f}點 | {r['trades']}筆 | 勝率{win_rate}%", flush=True)
    
    return best, sorted_results


def run_optimization():
    """執行完整最佳化"""
    print("\n" + "★" * 55, flush=True)
    print("★  KD 參數最佳化回測系統", flush=True)
    print("★  使用 Shioaji 真實歷史資料 (近3個月)", flush=True)
    print("★" * 55, flush=True)
    
    # 步驟1: 登入 + 一次抓完所有資料
    print("\n📥 正在下載股票資料...", flush=True)
    api = login()
    all_data = fetch_all_daily(api, days=90)
    api.logout()
    
    # 步驟2: 逐一最佳化
    print("\n" + "★" * 55, flush=True)
    print("★  🏆 庫存股最佳化結果", flush=True)
    print("★" * 55, flush=True)
    
    all_best = {}
    for sid, name, cost in HOLDINGS:
        if sid in all_data:
            name2, daily = all_data[sid]
            best, top3 = optimize_stock(sid, name, cost, daily)
            all_best[sid] = {"name": name, "cost": cost, "best": best, "top3": top3}
        else:
            print(f"\n  ❌ {name}({sid}) 無資料", flush=True)
    
    # 步驟3: 觀察股
    print("\n" + "☆" * 55, flush=True)
    print("☆  🏆 觀察股最佳化結果", flush=True)
    print("☆" * 55, flush=True)
    
    for sid, name, cost in WATCHES:
        if sid in all_data:
            name2, daily = all_data[sid]
            best, top3 = optimize_stock(sid, name, cost, daily)
            all_best[f"w_{sid}"] = {"name": name, "cost": cost, "best": best, "top3": top3}
    
    # 步驟4: 儲存結果
    result_path = os.path.join(os.path.dirname(__file__), "..", "..", "optimize_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(all_best, f, ensure_ascii=False, indent=2, default=str)
    
    # 步驟5: 摘要
    print("\n" + "★" * 55, flush=True)
    print("★  📋 最佳參數摘要", flush=True)
    print("★" * 55, flush=True)
    
    for sid, info in all_best.items():
        b = info["best"]
        bt_str = f"買<{b['buy']}" if b['buy'] else "買不限"
        st_str = f"賣>{b['sell']}" if b['sell'] else "賣不限"
        win_rate = round(b["wins"] / max(b["trades"], 1) * 100, 1)
        print(f"\n  {info['name']}({sid.replace('w_','')})", flush=True)
        print(f"  K={b['k']} {bt_str} {st_str} → 損益{b['pnl']:.1f}點 | 交易{b['trades']}次 | 勝率{win_rate}%", flush=True)
    
    print(f"\n✅ 最佳化完成！結果已儲存至 optimize_results.json", flush=True)


if __name__ == "__main__":
    run_optimization()
