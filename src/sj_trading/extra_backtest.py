"""
補測腳本 — 對晶技(3042)以及用戶庫存股進行6個月30分K KD回測
同時輸出到今天為止的30分K KD現狀，找出哪幾支接近黃金交叉、哪幾支在低檔
"""
import os, sys, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ===== 補充股票清單 (庫存+觀察) =====
EXTRA_STOCKS = [
    ("3042", "晶技", "庫存"),
    ("8150", "南茂", "庫存"),
    ("5351", "鈺創", "庫存"),
    ("3673", "TPK-KY", "庫存"),
    ("2337", "旺宏", "庫存"),
    ("2436", "偉詮電", "庫存"),
    ("6284", "佳邦", "觀察"),
    ("6213", "聯茂", "觀察"),
    ("6271", "同欣電", "觀察"),
    ("6451", "訊芯-KY", "觀察"),
    ("2327", "國巨", "觀察"),
    ("6173", "信昌電", "觀察"),
    ("5425", "台半", "觀察"),
    ("3131", "弘塑", "觀察"),
    ("3583", "辛耘", "觀察"),
    ("6239", "力成", "觀察"),
    ("1802", "台玻", "觀察"),
    ("4906", "正文", "觀察"),
    ("6005", "群益證", "觀察"),
]

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

def compute_kd(k_vals, d_vals, close, low, high, kp):
    n = len(k_vals)
    low_min = pd.Series(low).rolling(kp).min().values
    high_max = pd.Series(high).rolling(kp).max().values
    denom = high_max - low_min
    rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50)
    for i in range(kp, n):
        k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
        d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
        k_vals[i] = k_new
        d_vals[i] = d_new
    return k_vals, d_vals

def optimize_and_analyze(df_30):
    """找最佳參數，同時分析當前KD狀態"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_vals = [20, 25, 30, 35, 40, 45, 50]
    sell_vals = [50, 55, 60, 65, 70, 75, 80]
    
    close = df_30["close"].values
    low_v = df_30["low"].values
    high_v = df_30["high"].values
    n = len(close)
    
    best = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "trades": 0, "wins": 0}
    
    for kp in k_range:
        k_arr = np.full(n, 50.0)
        d_arr = np.full(n, 50.0)
        k_arr, d_arr = compute_kd(k_arr, d_arr, close, low_v, high_v, kp)
        
        for bt in buy_vals + [None]:
            for st in sell_vals + [None]:
                position = 0
                bp = 0
                total = 0.0
                t_cnt = 0
                w_cnt = 0
                
                for i in range(kp + 1, n):
                    k_n = k_arr[i]; d_n = d_arr[i]
                    k_p = k_arr[i-1]; d_p = d_arr[i-1]
                    c = close[i]
                    
                    if position == 0 and k_p <= d_p and k_n > d_n:
                        if bt is None or k_n < bt:
                            position = 1; bp = c; t_cnt += 1
                    elif position == 1 and k_p >= d_p and k_n < d_n:
                        if st is None or k_n > st:
                            position = 0
                            pnl = ((c - bp) / bp) * 100
                            total += pnl
                            if pnl > 0: w_cnt += 1
                
                if position == 1:
                    pnl = ((close[-1] - bp) / bp) * 100
                    total += pnl
                    if pnl > 0: w_cnt += 1
                    t_cnt += 1
                
                if total > best["pnl"] and t_cnt >= 2:
                    best = {"pnl": round(total,2), "k": kp, "buy": bt, "sell": st, "trades": t_cnt, "wins": w_cnt}
    
    return best

def current_kd_status(df_30, best):
    """用最佳參數分析當前KD狀態"""
    kp = best["k"]
    close = df_30["close"].values
    low_v = df_30["low"].values
    high_v = df_30["high"].values
    n = len(close)
    
    k_arr = np.full(n, 50.0)
    d_arr = np.full(n, 50.0)
    k_arr, d_arr = compute_kd(k_arr, d_arr, close, low_v, high_v, kp)
    
    # 最近5根K
    n5 = min(5, n)
    recent = []
    for i in range(n5, 0, -1):
        idx = df_30.index[-i]
        recent.append({
            "time": idx.strftime("%m/%d %H:%M"),
            "close": round(close[-i], 2),
            "k": round(k_arr[-i], 2),
            "d": round(d_arr[-i], 2),
        })
    
    k_n, k_p = k_arr[-1], k_arr[-2]
    d_n, d_p = d_arr[-1], d_arr[-2]
    last_close = close[-1]
    
    # 進場分析
    entering = False
    golden_now = k_p <= d_p and k_n > d_n
    in_golden = k_n > d_n
    
    if golden_now and (best["buy"] is None or k_n < best["buy"]):
        entering = True
    
    # 價格區間
    h20 = df_30["high"].tail(60).max()
    l20 = df_30["low"].tail(60).min()
    
    if h20 > l20:
        pos_pct = (last_close - l20) / (h20 - l20) * 100
    else:
        pos_pct = 50
    
    return {
        "k_current": round(k_n, 2),
        "d_current": round(d_n, 2),
        "golden_now": golden_now,
        "in_golden": in_golden,
        "entering": entering,
        "last_close": round(last_close, 2),
        "high_60d": round(h20, 2),
        "low_60d": round(l20, 2),
        "price_pos": round(pos_pct, 0),
        "recent_bars": recent,
    }

def generate_entry_plan(name, sid, best, status):
    """產出進場建議"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  {name}({sid})")
    
    bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
    st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
    sr = round(best["wins"]/max(best["trades"],1)*100, 1)
    lines.append(f"  最佳參數: K={best['k']} {bt_s} {st_s}")
    lines.append(f"  6個月回測: +{best['pnl']:.2f}% | {best['trades']}筆交易 | 勝率{sr}%")
    lines.append(f"  最新收盤: {status['last_close']}")
    lines.append(f"  當前K={status['k_current']} D={status['d_current']}")
    lines.append(f"  價格區間(60根K): {status['low_60d']} ~ {status['high_60d']} (目前{status['price_pos']}%)")
    
    # 近5根K
    lines.append(f"  近5根30分K:")
    for b in status["recent_bars"]:
        marker = " ← 金叉!" if b["k"] > b["d"] and b != status["recent_bars"][0] else ""
        lines.append(f"    {b['time']} 收{b['close']} K={b['k']} D={b['d']}{marker}")
    
    # 進場建議
    if status["entering"]:
        lines.append(f"  ✅ 黃金交叉! 現在可以進場!")
        lines.append(f"  建議買進: {status['last_close']}附近")
    elif status["golden_now"]:
        reason = ""
        if best["buy"] and status["k_current"] >= best["buy"]:
            reason = f"K={status['k_current']} >= 門檻{best['buy']}"
        lines.append(f"  🟡 剛金叉但{reason}，等K回檔")
        d_val = status["d_current"]
        lines.append(f"  建議買進區間: {status['last_close']*0.97:.2f} ~ {status['last_close']:.2f}")
    elif status["in_golden"]:
        k = status["k_current"]
        if k < 50:
            lines.append(f"  🟢 低檔金叉持續中，適合進場")
            lines.append(f"  建議: 掛{status['last_close']*0.97:.2f}附近買")
        elif k < 70:
            lines.append(f"  🟡 金叉中K={k}中等，可買但要控制倉位")
        else:
            lines.append(f"  🔴 K={k}高檔金叉! 等拉回再買")
            lines.append(f"  目標: 等K回檔到D線({status['d_current']})附近")
    else:
        lines.append(f"  ❌ K<D 死叉狀態，等黃金交叉")
        lines.append(f"  目前K={status['k_current']} D={status['d_current']}")
    
    return "\n".join(lines)

def main():
    stocks = EXTRA_STOCKS
    
    print("="*70)
    print("  補充回測 + 即時KD現狀分析")
    print(f"  股票: {len(stocks)} 檔")
    print("="*70)
    
    api = login()
    results = {}
    
    for idx, (sid, name, cat) in enumerate(stocks, 1):
        print(f"\n[{idx}/{len(stocks)}] {name}({sid}) [{cat}]", end="", flush=True)
        
        try:
            df30 = fetch_30k(api, sid, 185)
        except Exception as e:
            print(f" .. err: {e}", flush=True)
            continue
        
        if df30 is None or len(df30) < 20:
            print(" .. 資料不足", flush=True)
            continue
        
        print(f" ({len(df30)}K/{df30['close'].iloc[-1]:.0f})", end="", flush=True)
        
        t0 = time.time()
        best = optimize_and_analyze(df30)
        status = current_kd_status(df30, best)
        elapsed = time.time() - t0
        print(f" {elapsed:.1f}s", flush=True)
        
        results[sid] = {
            "name": name, "category": cat,
            "best": {k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in best.items()},
            "status": status,
        }
        
        # 簡短輸出
        bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
        st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
        print(f"  K={best['k']} {bt_s} {st_s} +{best['pnl']:.1f}% | 現況K={status['k_current']} D={status['d_current']}", flush=True)
        
        time.sleep(0.2)
    
    api.logout()
    
    # 輸出報告
    print(f"\n\n{'='*70}")
    print(f"  🎯 進場機會分析報告")
    print(f"{'='*70}")
    
    # 分類：可進場 / 可觀察 / 等待
    print(f"\n{'='*70}")
    print(f"  ✅ 現在可以進場的股票 (黃金交叉+滿足買入條件)")
    print(f"{'='*70}")
    for sid, v in results.items():
        st = v["status"]
        if st["entering"]:
            print(generate_entry_plan(v["name"], sid, v["best"], st))
    
    print(f"\n{'='*70}")
    print(f"  🟢 低檔金叉中 (K<50, 可考慮進場)")
    print(f"{'='*70}")
    for sid, v in results.items():
        st = v["status"]
        if not st["entering"] and st["in_golden"] and st["k_current"] < 50:
            print(generate_entry_plan(v["name"], sid, v["best"], st))
    
    print(f"\n{'='*70}")
    print(f"  🟡 金叉中但K值偏高 (K>50, 等拉回)")
    print(f"{'='*70}")
    for sid, v in results.items():
        st = v["status"]
        if st["in_golden"] and st["k_current"] >= 50 and not st["entering"]:
            print(generate_entry_plan(v["name"], sid, v["best"], st))
    
    print(f"\n{'='*70}")
    print(f"  🔴 死叉中 (等待黃金交叉)")
    print(f"{'='*70}")
    for sid, v in results.items():
        st = v["status"]
        if not st["in_golden"]:
            print(generate_entry_plan(v["name"], sid, v["best"], st))
    
    # 保存JSON
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base, "extra_stocks_analysis.json")
    
    def clean(obj):
        if isinstance(obj, dict): return {k: clean(v) for k,v in obj.items()}
        elif isinstance(obj, list): return [clean(v) for v in obj]
        elif isinstance(obj, (np.integer,)): return int(obj)
        elif isinstance(obj, (np.floating,)): return float(obj)
        return obj
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean(results), f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 資料已儲存到 {json_path}")


if __name__ == "__main__":
    main()
