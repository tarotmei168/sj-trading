"""
進階回測：KD + 成交量分析 + 法人動向
針對庫存股找出最佳策略
"""
import os, json, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

HOLDINGS = [
    ("3711", "日月光", 481),
    ("4958", "臻鼎KY", 461),
    ("3042", "晶技", 196),
    ("2337", "旺宏", 174),
    ("2436", "偉詮電", 76),
    ("3673", "TPKKY", 51.69),
]

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_stock_data(api, sid, days=90):
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=days)
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
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
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume, "amount": kbars.Amount,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except:
            break
    if not all_dfs:
        return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum", "amount": "sum",
    }).dropna()
    
    # 技術指標
    daily["volume_ma5"] = daily["volume"].rolling(5).mean()
    daily["volume_ma20"] = daily["volume"].rolling(20).mean()
    daily["volume_ratio"] = daily["volume"] / daily["volume_ma5"].replace(0, np.nan)
    daily["avg_price"] = daily["amount"] / daily["volume"]  # 成交均價
    
    # KD
    for kp in [3, 5, 7, 9, 12, 14]:
        low_min = daily["low"].rolling(kp).min()
        high_max = daily["high"].rolling(kp).max()
        rsv = ((daily["close"] - low_min) / (high_max - low_min)) * 100
        rsv = rsv.fillna(50)
        k_vals = [50] * kp
        d_vals = [50] * kp
        for i in range(kp, len(daily)):
            k_new = (2/3) * k_vals[-1] + (1/3) * rsv.iloc[i]
            d_new = (2/3) * d_vals[-1] + (1/3) * k_new
            k_vals.append(k_new)
            d_vals.append(d_new)
        daily[f"K{kp}"] = k_vals
        daily[f"D{kp}"] = d_vals
    
    return daily

def backtest_strategy(daily, k_period, buy_th, sell_th, use_volume=False, vol_min=1.0):
    """回測單一策略，可選擇是否加入成交量條件"""
    k_col = f"K{k_period}"
    d_col = f"D{k_period}"
    
    if k_col not in daily.columns:
        return -99999, 0, 0
    
    valid = daily.dropna(subset=[k_col, d_col, "volume_ratio"])
    if len(valid) < k_period + 10:
        return -99999, 0, 0
    
    position = 0
    buy_price = 0
    total_pnl = 0
    trades = 0
    wins = 0
    
    for i in range(k_period + 1, len(valid)):
        k_now = valid[k_col].iloc[i]
        d_now = valid[d_col].iloc[i]
        k_prev = valid[k_col].iloc[i-1]
        d_prev = valid[d_col].iloc[i-1]
        close = valid["close"].iloc[i]
        vol_ratio = valid["volume_ratio"].iloc[i] if "volume_ratio" in valid.columns else 1.0
        
        # 黃金交叉
        if position == 0 and k_prev <= d_prev and k_now > d_now:
            if buy_th is None or k_now < buy_th:
                if not use_volume or vol_ratio >= vol_min:
                    position = 1
                    buy_price = close
                    trades += 1
        
        # 死亡交叉
        elif position == 1 and k_prev >= d_prev and k_now < d_now:
            if sell_th is None or k_now > sell_th:
                position = 0
                pnl = close - buy_price
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
    
    if position == 1:
        pnl = valid["close"].iloc[-1] - buy_price
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        trades += 1
    
    return total_pnl, trades, wins


def optimize_stock(name, sid, cost, daily):
    """對單一股票找最佳策略（KD+成交量）"""
    print(f"\n📊 {name}({sid}) 進階最佳化中...", flush=True)
    
    k_range = [3, 5, 7, 9]
    buy_range = [None, 20, 30, 40, 50]
    sell_range = [None, 50, 60, 70, 80]
    vol_options = [(False, 0), (True, 1.2), (True, 1.5), (True, 2.0)]
    
    best = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "use_vol": False, "vol_min": 0, "trades": 0, "wins": 0}
    best_no_vol = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "trades": 0, "wins": 0}
    all_results = []
    
    for k in k_range:
        for bt in buy_range:
            for st in sell_range:
                # 純KD
                pnl, trades, wins = backtest_strategy(daily, k, bt, st, use_volume=False)
                if pnl > best_no_vol["pnl"] and trades >= 2:
                    best_no_vol = {"pnl": pnl, "k": k, "buy": bt, "sell": st, "trades": trades, "wins": wins}
                
                # KD + 成交量
                for use_vol, vol_min in vol_options:
                    pnl, trades, wins = backtest_strategy(daily, k, bt, st, use_vol, vol_min)
                    if pnl > best["pnl"] and trades >= 2:
                        best = {"pnl": round(pnl, 2), "k": k, "buy": bt, "sell": st, "use_vol": use_vol, "vol_min": vol_min, "trades": trades, "wins": wins}
                    all_results.append({"k": k, "buy": bt, "sell": st, "use_vol": use_vol, "vol_min": vol_min, "pnl": round(pnl, 2), "trades": trades, "wins": wins})
    
    current_price = daily["close"].iloc[-1]
    current_pnl = round((current_price - cost) / cost * 100, 2)
    
    print(f"  目前: {current_price:.2f} ({current_pnl}%)", flush=True)
    
    if best["pnl"] > -99999:
        bt_s = f"買<{best['buy']}" if best["buy"] else "買不限"
        st_s = f"賣>{best['sell']}" if best["sell"] else "賣不限"
        vol_s = f" +量比>{best['vol_min']}" if best["use_vol"] else ""
        wr = round(best["wins"] / max(best["trades"], 1) * 100, 1)
        print(f"  🏆 KD+量: K={best['k']} {bt_s} {st_s}{vol_s} → 賺{best['pnl']}點 | {best['trades']}筆 | 勝率{wr}%", flush=True)
    
    if best_no_vol["pnl"] > -99999:
        bt_s = f"買<{best_no_vol['buy']}" if best_no_vol["buy"] else "買不限"
        st_s = f"賣>{best_no_vol['sell']}" if best_no_vol["sell"] else "賣不限"
        wr = round(best_no_vol["wins"] / max(best_no_vol["trades"], 1) * 100, 1)
        print(f"  📊 純KD: K={best_no_vol['k']} {bt_s} {st_s} → 賺{best_no_vol['pnl']}點 | {best_no_vol['trades']}筆 | 勝率{wr}%", flush=True)
    
    return best, best_no_vol, all_results


def run():
    print("=" * 55, flush=True)
    print("🏆 庫存股進階最佳化：KD + 成交量", flush=True)
    print("=" * 55, flush=True)
    
    print("\n📥 下載所有庫存股資料...", flush=True)
    api = login()
    all_data = {}
    for sid, name, cost in HOLDINGS:
        daily = fetch_stock_data(api, sid, days=90)
        if daily is not None:
            all_data[sid] = {"name": name, "cost": cost, "daily": daily}
            print(f"  ✅ {name}({sid}) {len(daily)}天", flush=True)
        else:
            print(f"  ❌ {name}({sid}) 無資料", flush=True)
    api.logout()
    
    print("\n" + "=" * 55, flush=True)
    print("📋 最佳化結果", flush=True)
    print("=" * 55, flush=True)
    
    summary = {}
    for sid, info in all_data.items():
        best, best_no_vol, _ = optimize_stock(info["name"], sid, info["cost"], info["daily"])
        summary[sid] = {"name": info["name"], "cost": info["cost"], "best": best, "best_no_vol": best_no_vol}
    
    print("\n" + "★" * 55, flush=True)
    print("★  總結對照表：純KD vs KD+成交量", flush=True)
    print("★" * 55, flush=True)
    
    for sid, s in summary.items():
        b, bn = s["best"], s["best_no_vol"]
        bt_s = f"{b['buy']}" if b["buy"] else "不限"
        st_s = f"{b['sell']}" if b["sell"] else "不限"
        vol_s = f"量>{b['vol_min']}" if b["use_vol"] else "無量"
        wr = f"{round(b['wins']/max(b['trades'],1)*100,1)}%"
        wr_n = f"{round(bn['wins']/max(bn['trades'],1)*100,1)}%"
        print(f"\n  {s['name']}({sid})", flush=True)
        print(f"  KD+量: K={b['k']} 買{bt_s} 賣{st_s} {vol_s} → {b['pnl']}點/率{wr}", flush=True)
        print(f"  純KD:  K={bn['k']} 買{bt_s} 賣{st_s}       → {bn['pnl']}點/率{wr_n}", flush=True)
    
    # 存檔
    out_path = os.path.join(os.path.dirname(__file__), "..", "advanced_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 結果已儲存至 advanced_results.json", flush=True)


if __name__ == "__main__":
    run()
