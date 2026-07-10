"""
大型回測腳本 v2 — 30分K KD策略 6個月
更穩定的版本：增加超時處理、更快的分批抓取
"""
import os, sys, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

# Fix Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# ============================================================
# 股票清單
# ============================================================
STOCK_0050 = [
    ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"),
    ("2308", "台達電"), ("2881", "富邦金"), ("2882", "國泰金"),
    ("2412", "中華電"), ("1301", "台塑"), ("1303", "南亞"),
    ("1326", "台化"), ("2002", "中鋼"), ("2303", "聯電"),
    ("2886", "兆豐金"), ("2891", "中信金"), ("2884", "玉山金"),
    ("2887", "台新金"), ("2885", "元大金"), ("2301", "光寶科"),
    ("2357", "華碩"), ("2382", "廣達"), ("3231", "緯創"),
    ("2356", "英業達"), ("2353", "宏碁"), ("3008", "大立光"),
    ("3034", "聯詠"), ("3711", "日月光"), ("4904", "遠傳"),
    ("4958", "臻鼎-KY"), ("5871", "中租-KY"),
    ("5880", "合庫金"), ("8046", "南電"),
    ("8454", "富邦媒"), ("9921", "巨大"), ("9933", "中鼎"),
    ("1101", "台泥"), ("1216", "統一"), ("1402", "遠東新"),
    ("1476", "儒鴻"), ("1590", "亞德客-KY"), ("2049", "上銀"),
    ("2105", "正新"), ("2207", "和泰車"),
    ("2395", "研華"), ("2408", "南亞科"), ("2474", "可成"),
    ("2603", "長榮"), ("2610", "華航"),
]

STOCK_HOT = [
    ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"),
    ("2303", "聯電"), ("2344", "華邦電"), ("2408", "南亞科"),
    ("6770", "力積電"), ("2603", "長榮"), ("2609", "陽明"),
    ("2618", "長榮航"), ("2610", "華航"), ("2888", "新光金"),
    ("2892", "第一金"), ("2881", "富邦金"), ("2882", "國泰金"),
    ("3037", "欣興"), ("3189", "景碩"), ("8046", "南電"),
    ("3711", "日月光"), ("2382", "廣達"),
]

STOCK_EXTRA = [("6139", "亞翔")]

def get_full_stock_list():
    seen = set()
    result = []
    for sid, name in STOCK_0050 + STOCK_HOT + STOCK_EXTRA:
        if sid not in seen:
            seen.add(sid)
            cat = "亞翔" if sid == "6139" else ("0050" if (sid, name) in STOCK_0050 else "熱門")
            result.append((sid, name, cat))
    return result

# ============================================================
# Shioaji 資料下載 (使用日K直接抓，更快)
# ============================================================

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_min_kbars(api, sid, days=185):
    """抓取1分K (分批29天)"""
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        return None
    
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
                seg_end = seg_start - timedelta(seconds=1)
                continue
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except Exception as e:
            print(f"       fetch error: {e}", flush=True)
            break
    
    if not all_dfs:
        return None
    
    raw = pd.concat(all_dfs)
    raw.drop_duplicates(subset=["datetime"], inplace=True)
    raw.sort_values("datetime", inplace=True)
    raw.set_index("datetime", inplace=True)
    
    # 30分K
    _30min = raw.resample("30min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()
    _30min = _30min.between_time("09:00", "13:30")
    
    if len(_30min) < 20:
        return None
    return _30min

# ============================================================
# KD 計算 + 回測
# ============================================================

def compute_kd(df, k_period):
    df = df.copy()
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)
    
    k_vals = [50] * k_period
    d_vals = [50] * k_period
    for i in range(k_period, len(df)):
        r = rsv.iloc[i]
        k_new = (2/3) * k_vals[-1] + (1/3) * r
        d_new = (2/3) * d_vals[-1] + (1/3) * k_new
        k_vals.append(k_new)
        d_vals.append(d_new)
    
    df["K"] = k_vals[:len(df)]
    df["D"] = d_vals[:len(df)]
    return df

def backtest(df, k_period, buy_threshold, sell_threshold):
    df = compute_kd(df, k_period)
    valid = df.dropna(subset=["K", "D"])
    if len(valid) < k_period + 5:
        return 0, 0, 0, []
    
    position = 0
    buy_price = 0
    buy_date = None
    total_pnl = 0
    trades = 0
    wins = 0
    trade_list = []
    
    for i in range(k_period + 1, len(valid)):
        k_now = valid["K"].iloc[i]
        d_now = valid["D"].iloc[i]
        k_prev = valid["K"].iloc[i-1]
        d_prev = valid["D"].iloc[i-1]
        close = valid["close"].iloc[i]
        idx = valid.index[i]
        
        if position == 0 and k_prev <= d_prev and k_now > d_now:
            if buy_threshold is None or k_now < buy_threshold:
                position = 1
                buy_price = close
                buy_date = idx
                trades += 1
        elif position == 1 and k_prev >= d_prev and k_now < d_now:
            if sell_threshold is None or k_now > sell_threshold:
                position = 0
                pnl = ((close - buy_price) / buy_price) * 100
                total_pnl += pnl
                if pnl > 0: wins += 1
                trade_list.append((buy_date, idx, buy_price, close, round(pnl, 2)))
    
    if position == 1:
        pnl = ((valid["close"].iloc[-1] - buy_price) / buy_price) * 100
        total_pnl += pnl
        if pnl > 0: wins += 1
        trade_list.append((buy_date, valid.index[-1], buy_price, valid["close"].iloc[-1], round(pnl, 2)))
    
    return total_pnl, trades, wins, trade_list

def optimize_params(daily_30min):
    k_range = [3, 5, 7, 9, 12, 14]
    buy_range = [20, 25, 30, 35, 40, 45, 50, None]
    sell_range = [50, 55, 60, 65, 70, 75, 80, None]
    
    best = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "trades": 0, "wins": 0}
    all_r = []
    
    for k in k_range:
        for bt in buy_range:
            for st in sell_range:
                pnl, trades, wins, _ = backtest(daily_30min, k, bt, st)
                sr = round(wins / max(trades,1)*100, 1)
                all_r.append({"k": k, "buy": bt, "sell": st, "pnl": round(pnl,2), "trades": trades, "wins": wins, "sr": sr})
                if pnl > best["pnl"] and trades >= 2:
                    best = {"pnl": pnl, "k": k, "buy": bt, "sell": st, "trades": trades, "wins": wins}
    
    top5 = sorted([r for r in all_r if r["trades"] >= 2], key=lambda x: x["pnl"], reverse=True)[:5]
    return best, top5

# ============================================================
# 主流程
# ============================================================

def main():
    stocks = get_full_stock_list()
    
    print("=" * 70)
    print("  30分K KD策略 6個月回測 v2")
    print(f"  股票數: {len(stocks)} 檔 (0050+永豐金熱門20+亞翔)")
    print(f"  策略: 30分K KD交叉 + 每支獨立最佳參數")
    print("=" * 70)
    
    api = login()
    
    results = {}
    errors = []
    total = len(stocks)
    
    for idx, (sid, name, cat) in enumerate(stocks, 1):
        print(f"\n[{idx}/{total}] {name}({sid}) [{cat}]", end="", flush=True)
        
        try:
            daily_30min = fetch_min_kbars(api, sid, days=185)
        except Exception as e:
            print(f" .. error: {e}", flush=True)
            errors.append((sid, name, str(e)))
            continue
        
        if daily_30min is None or len(daily_30min) < 20:
            print(" .. 資料不足", flush=True)
            errors.append((sid, name, "資料不足"))
            continue
        
        bar_count = len(daily_30min)
        latest_price = daily_30min["close"].iloc[-1]
        print(f" ({bar_count}根K, 最新={latest_price:.0f})", flush=True)
        
        best, top5 = optimize_params(daily_30min)
        
        results[sid] = {
            "name": name, "category": cat,
            "bars": bar_count, "latest_price": round(latest_price, 2),
            "best": {k: v for k, v in best.items()},
            "top5": [{"k": r["k"], "buy": r["buy"], "sell": r["sell"],
                       "pnl": r["pnl"], "trades": r["trades"], "sr": r["sr"]}
                     for r in top5],
        }
        
        if best["trades"] >= 1:
            bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
            st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
            sr = round(best["wins"] / max(best["trades"],1)*100, 1)
            print(f"  => K={best['k']} {bt_s} {st_s} 報酬+{best['pnl']:.1f}% {best['trades']}筆 勝率{sr}%", flush=True)
        else:
            print(f"  => 無交易訊號", flush=True)
        
        time.sleep(0.2)
    
    api.logout()
    
    # 輸出
    report_path = os.path.join(os.path.dirname(__file__), "..", "..", "backtest_6m_v2.txt")
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "backtest_6m_v2.json")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    lines = []
    lines.append("=" * 75)
    lines.append("  30分K KD 策略 6個月回測報告 (v2)")
    lines.append(f"  日期: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    lines.append(f"  總股票: {len(results)}檔成功 / {len(errors)}檔失敗")
    
    total_ok = len(results)
    win_stocks = sum(1 for v in results.values() if v["best"]["pnl"] > 0)
    loss_stocks = sum(1 for v in results.values() if v["best"]["pnl"] <= 0)
    avg_pnl = round(sum(v["best"]["pnl"] for v in results.values()) / max(total_ok, 1), 2)
    
    lines.append(f"  正報酬: {win_stocks}檔 / 負報酬: {loss_stocks}檔")
    lines.append(f"  平均最佳報酬: +{avg_pnl:.2f}%")
    lines.append("=" * 75)
    
    for cat_name, key in [("0050 成分股", "0050"), ("永豐金熱門池", "熱門"), ("亞翔", "亞翔")]:
        cat_stocks = [(k, v) for k, v in results.items() if v["category"] == key]
        if not cat_stocks:
            continue
        cat_ok = len(cat_stocks)
        cat_win = sum(1 for _, v in cat_stocks if v["best"]["pnl"] > 0)
        cat_avg = round(sum(v["best"]["pnl"] for _, v in cat_stocks) / cat_ok, 2)
        lines.append(f"\n--- {cat_name}: {cat_ok}檔 | 正{cat_win}檔 | 均+{cat_avg:.2f}% ---")
        lines.append(f"  {'代號':<6} {'名稱':<8} {'K':<4} {'買':<8} {'賣':<8} {'報酬%':<10} {'交易':<6} {'勝率':<8}")
        for sid, v in sorted(cat_stocks, key=lambda x: x[1]["best"]["pnl"], reverse=True):
            b = v["best"]
            bt = f"<{b['buy']}" if b['buy'] else "不限"
            st = f">{b['sell']}" if b['sell'] else "不限"
            sr = round(b["wins"] / max(b["trades"], 1)*100, 1)
            sgn = "+" if b["pnl"] > 0 else ""
            lines.append(f"  {sid:<6} {v['name']:<8} K={b['k']:<2} {bt:<8} {st:<8} {sgn}{b['pnl']:.2f}%  {b['trades']:<4}筆 {sr}%")
    
    # Top 10
    all_sorted = sorted(results.items(), key=lambda x: x[1]["best"]["pnl"], reverse=True)
    lines.append(f"\n--- Top 10 ---")
    for rank, (sid, v) in enumerate(all_sorted[:10], 1):
        b = v["best"]
        bt = f"買<{b['buy']}" if b['buy'] else "買不限"
        st = f"賣>{b['sell']}" if b['sell'] else "賣不限"
        sr = round(b["wins"] / max(b["trades"], 1)*100, 1)
        lines.append(f"  #{rank} {v['name']}({sid}) K={b['k']} {bt} {st} 報酬+{b['pnl']:.2f}% {b['trades']}筆 勝率{sr}%")
    
    # Bottom 5
    lines.append(f"\n--- Bottom 5 ---")
    for rank, (sid, v) in enumerate(all_sorted[-5:], 1):
        b = v["best"]
        lines.append(f"  #{rank} {v['name']}({sid}) K={b['k']} 報酬{b['pnl']:.2f}% {b['trades']}筆")
    
    if errors:
        lines.append(f"\n--- 失敗清單 ({len(errors)}檔) ---")
        for sid, name, reason in errors:
            lines.append(f"  {name}({sid}): {reason}")
    
    report = "\n".join(lines)
    print(f"\n\n{report}")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 完成！報告已儲存")
    print(f"  {report_path}")
    print(f"  {json_path}")

if __name__ == "__main__":
    main()
