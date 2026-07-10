"""
大型回測腳本 v3 — 30分K KD策略 6個月 (效能優化版)
優化: KD只算一次 per K值，避免重複計算
"""
import os, sys, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ===== 股票清單 =====
STOCK_0050 = [
    ("2330","台積電"),("2454","聯發科"),("2317","鴻海"),("2308","台達電"),
    ("2881","富邦金"),("2882","國泰金"),("2412","中華電"),("1301","台塑"),
    ("1303","南亞"),("1326","台化"),("2002","中鋼"),("2303","聯電"),
    ("2886","兆豐金"),("2891","中信金"),("2884","玉山金"),("2887","台新金"),
    ("2885","元大金"),("2301","光寶科"),("2357","華碩"),("2382","廣達"),
    ("3231","緯創"),("2356","英業達"),("2353","宏碁"),("3008","大立光"),
    ("3034","聯詠"),("3711","日月光"),("4904","遠傳"),("4958","臻鼎-KY"),
    ("5871","中租-KY"),("5880","合庫金"),("8046","南電"),("8454","富邦媒"),
    ("9921","巨大"),("9933","中鼎"),("1101","台泥"),("1216","統一"),
    ("1402","遠東新"),("1476","儒鴻"),("1590","亞德客-KY"),("2049","上銀"),
    ("2105","正新"),("2207","和泰車"),("2395","研華"),("2408","南亞科"),
    ("2474","可成"),("2603","長榮"),("2610","華航"),
]

STOCK_HOT = [
    ("2330","台積電"),("2454","聯發科"),("2317","鴻海"),("2303","聯電"),
    ("2344","華邦電"),("2408","南亞科"),("6770","力積電"),("2603","長榮"),
    ("2609","陽明"),("2618","長榮航"),("2610","華航"),("2888","新光金"),
    ("2892","第一金"),("2881","富邦金"),("2882","國泰金"),("3037","欣興"),
    ("3189","景碩"),("8046","南電"),("3711","日月光"),("2382","廣達"),
]

STOCK_EXTRA = [("6139","亞翔")]

def get_stocks():
    seen = set()
    r = []
    for sid, name in STOCK_0050 + STOCK_HOT + STOCK_EXTRA:
        if sid not in seen:
            seen.add(sid)
            cat = "亞翔" if sid=="6139" else "0050" if (sid,name) in STOCK_0050 else "熱門"
            r.append((sid,name,cat))
    return r

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_30k(api, sid, days=185):
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
            kbars = api.kbars(contract=contract,
                start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts)==0:
                seg_end = seg_start - timedelta(seconds=1)
                continue
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
            })
            all_dfs.append(df)
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
    _30 = _30.between_time("09:00","13:30")
    return _30 if len(_30)>=20 else None

def compute_kd_array(k_vals, d_vals, close, low, high, k_period):
    """使用 numpy 向量化計算 KD"""
    n = len(k_vals)
    # 重新計算 RSV
    low_min = pd.Series(low).rolling(k_period).min().values
    high_max = pd.Series(high).rolling(k_period).max().values
    denom = high_max - low_min
    rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50)
    
    # 遞迴計算 (仍需 loop)
    for i in range(k_period, n):
        k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
        d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
        k_vals[i] = k_new
        d_vals[i] = d_new
    return k_vals, d_vals

def optimize_fast(df_30min):
    """快速最佳化: KD只算一次 per K 值"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_vals = [20, 25, 30, 35, 40, 45, 50]
    sell_vals = [50, 55, 60, 65, 70, 75, 80]
    
    close = df_30min["close"].values
    low = df_30min["low"].values
    high = df_30min["high"].values
    n = len(close)
    
    best = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "trades": 0, "wins": 0}
    all_r = []
    
    for kp in k_range:
        # KD 一次計算
        k_arr = np.full(n, 50.0) if kp <= n else np.full(n, 50.0)
        d_arr = np.full(n, 50.0)
        k_arr, d_arr = compute_kd_array(k_arr, d_arr, close, low, high, kp)
        
        # 試所有買賣門檻組合
        for bt in buy_vals + [None]:
            for st in sell_vals + [None]:
                position = 0
                bp = 0
                total_pnl = 0.0
                trades = 0
                wins = 0
                
                for i in range(kp + 1, n):
                    k_n = k_arr[i]
                    d_n = d_arr[i]
                    k_p = k_arr[i-1]
                    d_p = d_arr[i-1]
                    c = close[i]
                    
                    if position == 0 and k_p <= d_p and k_n > d_n:
                        if bt is None or k_n < bt:
                            position = 1
                            bp = c
                            trades += 1
                    elif position == 1 and k_p >= d_p and k_n < d_n:
                        if st is None or k_n > st:
                            position = 0
                            pnl = ((c - bp) / bp) * 100
                            total_pnl += pnl
                            if pnl > 0: wins += 1
                
                if position == 1:
                    pnl = ((close[-1] - bp) / bp) * 100
                    total_pnl += pnl
                    if pnl > 0: wins += 1
                    trades += 1
                
                total_pnl = round(total_pnl, 2)
                sr = round(wins / max(trades,1)*100, 1)
                all_r.append({"k":kp, "buy":bt, "sell":st, "pnl":total_pnl, "trades":trades, "sr":sr})
                if total_pnl > best["pnl"] and trades >= 2:
                    best = {"pnl":total_pnl, "k":kp, "buy":bt, "sell":st, "trades":trades, "wins":wins}
    
    top5 = sorted([r for r in all_r if r["trades"] >= 2], key=lambda x: x["pnl"], reverse=True)[:5]
    return best, top5

def main():
    stocks = get_stocks()
    
    print("="*70)
    print("  30分K KD策略 6個月回測 v3 (效能版)")
    print(f"  股票: {len(stocks)} 檔")
    print("="*70)
    
    api = login()
    results = {}
    errors = []
    
    for idx, (sid, name, cat) in enumerate(stocks, 1):
        print(f"\n[{idx}/{len(stocks)}] {name}({sid}) [{cat}]", end="", flush=True)
        
        try:
            df30 = fetch_30k(api, sid, 185)
        except Exception as e:
            print(f" .. fetch err: {e}", flush=True)
            errors.append((sid, name, str(e)))
            continue
        
        if df30 is None or len(df30) < 20:
            print(" .. 資料不足", flush=True)
            errors.append((sid, name, "資料不足"))
            continue
        
        bar_cnt = len(df30)
        lprice = df30["close"].iloc[-1]
        print(f" ({bar_cnt}K/{lprice:.0f})", end="", flush=True)
        
        t0 = time.time()
        best, top5 = optimize_fast(df30)
        elapsed = time.time() - t0
        print(f" {elapsed:.1f}s", flush=True)
        
        results[sid] = {
            "name":name, "category":cat, "bars":bar_cnt,
            "latest_price": round(lprice, 2),
            "best": {k:int(v) if isinstance(v, (np.integer,)) else v for k,v in best.items()},
            "top5": [{k:int(x[k]) if isinstance(x[k],(np.integer,)) else x[k] for k in x} for x in top5],
        }
        
        if best["trades"] >= 1:
            bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
            st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
            sr = round(best["wins"]/max(best["trades"],1)*100,1)
            print(f"  => K={best['k']} {bt_s} {st_s} +{best['pnl']:.1f}% {best['trades']}筆 {sr}%", flush=True)
        else:
            print(f"  => 無訊號", flush=True)
    
    api.logout()
    
    # 輸出
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base, "backtest_6m_v3.json")
    report_path = os.path.join(base, "backtest_6m_v3.txt")
    
    # 清理 numpy types for JSON
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        return obj
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean(results), f, ensure_ascii=False, indent=2)
    
    lines = []
    lines.append("="*75)
    lines.append(f"  30分K KD策略 6個月回測報告")
    lines.append(f"  日期: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    lines.append(f"  成功: {len(results)}檔 / 失敗: {len(errors)}檔")
    
    win_n = sum(1 for v in results.values() if v["best"]["pnl"] > 0)
    loss_n = sum(1 for v in results.values() if v["best"]["pnl"] <= 0)
    avg_pnl = round(sum(v["best"]["pnl"] for v in results.values()) / max(len(results),1), 2)
    
    lines.append(f"  正報酬: {win_n}檔 / 負報酬: {loss_n}檔")
    lines.append(f"  平均最佳報酬: +{avg_pnl:.2f}%")
    lines.append("="*75)
    
    for cat_name, key in [("0050", "0050"), ("永豐金熱門池", "熱門"), ("亞翔", "亞翔")]:
        items = [(k,v) for k,v in results.items() if v["category"]==key]
        if not items: continue
        cavg = round(sum(v["best"]["pnl"] for _,v in items)/len(items), 2)
        cwin = sum(1 for _,v in items if v["best"]["pnl"]>0)
        lines.append(f"\n--- {cat_name}: {len(items)}檔 | 正{cwin}檔 | 均+{cavg:.2f}% ---")
        for sid, v in sorted(items, key=lambda x: x[1]["best"]["pnl"], reverse=True):
            b = v["best"]
            bt = f"<{b['buy']}" if b['buy'] else "不限"
            st = f">{b['sell']}" if b['sell'] else "不限"
            sr = round(b["wins"]/max(b["trades"],1)*100,1)
            sgn = "+" if b["pnl"]>0 else ""
            lines.append(f"  {sid:<6} {v['name']:<8} K={b['k']:<2} {bt:<8} {st:<8} {sgn}{b['pnl']:.2f}%  {b['trades']}筆 {sr}%")
    
    all_s = sorted(results.items(), key=lambda x: x[1]["best"]["pnl"], reverse=True)
    lines.append(f"\n--- Top 10 ---")
    for rk,(sid,v) in enumerate(all_s[:10], 1):
        b = v["best"]
        bt = f"買<{b['buy']}" if b['buy'] else "買不限"
        st = f"賣>{b['sell']}" if b['sell'] else "賣不限"
        sr = round(b["wins"]/max(b["trades"],1)*100,1)
        lines.append(f"  #{rk} {v['name']}({sid}) K={b['k']} {bt} {st} +{b['pnl']:.2f}% {b['trades']}筆 {sr}%")
    
    lines.append(f"\n--- Bottom 5 ---")
    for rk,(sid,v) in enumerate(all_s[-5:], 1):
        b = v["best"]
        lines.append(f"  #{rk} {v['name']}({sid}) K={b['k']} {b['pnl']:.2f}% {b['trades']}筆")
    
    if errors:
        lines.append(f"\n--- 失敗: {len(errors)}檔 ---")
        for sid, name, reason in errors:
            lines.append(f"  {name}({sid}): {reason}")
    
    report = "\n".join(lines)
    print(f"\n\n{report}")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n  {report_path}")
    print(f"  {json_path}")

if __name__ == "__main__":
    main()
