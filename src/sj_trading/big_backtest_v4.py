"""
回測 v4 — 30分K KD策略 6個月 (詳細交易明細版)
使用 v3 找到的最佳參數，輸出每筆交易的買賣日期價格
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

def compute_kd_array(k_vals, d_vals, close, low, high, kp):
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

def backtest_with_trades(df_30min, kp, buy_th, sell_th):
    """回測並記錄每筆交易明細"""
    close = df_30min["close"].values
    low = df_30min["low"].values
    high = df_30min["high"].values
    dates = df_30min.index
    n = len(close)
    
    k_arr = np.full(n, 50.0)
    d_arr = np.full(n, 50.0)
    k_arr, d_arr = compute_kd_array(k_arr, d_arr, close, low, high, kp)
    
    position = 0
    bp = 0.0
    b_idx = 0
    total_pnl = 0.0
    trades = 0
    wins = 0
    trade_details = []
    
    for i in range(kp + 1, n):
        k_n = k_arr[i]
        d_n = d_arr[i]
        k_p = k_arr[i-1]
        d_p = d_arr[i-1]
        c = close[i]
        dt = dates[i]
        
        if position == 0 and k_p <= d_p and k_n > d_n:
            if buy_th is None or k_n < buy_th:
                position = 1
                bp = c
                b_idx = i
                trades += 1
        elif position == 1 and k_p >= d_p and k_n < d_n:
            if sell_th is None or k_n > sell_th:
                position = 0
                pnl = ((c - bp) / bp) * 100
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                trade_details.append({
                    "buy_date": dates[b_idx].strftime("%Y-%m-%d %H:%M"),
                    "buy_price": round(bp, 2),
                    "sell_date": dt.strftime("%Y-%m-%d %H:%M"),
                    "sell_price": round(c, 2),
                    "profit_pct": round(pnl, 2),
                    "hold_k_bars": i - b_idx,
                })
    
    # 最後持有
    if position == 1:
        pnl = ((close[-1] - bp) / bp) * 100
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        trade_details.append({
            "buy_date": dates[b_idx].strftime("%Y-%m-%d %H:%M"),
            "buy_price": round(bp, 2),
            "sell_date": dates[-1].strftime("%Y-%m-%d %H:%M") + " (持有中)",
            "sell_price": round(close[-1], 2),
            "profit_pct": round(pnl, 2),
            "hold_k_bars": n - b_idx,
        })
    
    return round(total_pnl, 2), trades, wins, trade_details

def find_best_params(df_30min):
    """找最佳參數 (同 v3)"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_vals = [20, 25, 30, 35, 40, 45, 50]
    sell_vals = [50, 55, 60, 65, 70, 75, 80]
    
    close = df_30min["close"].values
    low = df_30min["low"].values
    high = df_30min["high"].values
    n = len(close)
    
    best = {"pnl": -99999, "k": 0, "buy": None, "sell": None, "trades": 0, "wins": 0}
    
    for kp in k_range:
        k_arr = np.full(n, 50.0)
        d_arr = np.full(n, 50.0)
        k_arr, d_arr = compute_kd_array(k_arr, d_arr, close, low, high, kp)
        
        for bt in buy_vals + [None]:
            for st in sell_vals + [None]:
                position = 0
                bp = 0
                total = 0.0
                t_cnt = 0
                w_cnt = 0
                
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
                            t_cnt += 1
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
                    best = {"pnl": round(total, 2), "k": kp, "buy": bt, "sell": st, "trades": t_cnt, "wins": w_cnt}
    
    return best

def main():
    stocks = get_stocks()
    
    print("="*70)
    print("  30分K KD策略 6個月回測 v4 (交易明細版)")
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
        
        # 找最佳參數 + 交易明細
        t0 = time.time()
        best = find_best_params(df30)
        total_pnl, t_cnt, w_cnt, trades = backtest_with_trades(
            df30, best["k"], best["buy"], best["sell"])
        elapsed = time.time() - t0
        print(f" {elapsed:.1f}s", flush=True)
        
        results[sid] = {
            "name": name, "category": cat,
            "bars": bar_cnt, "latest_price": round(lprice, 2),
            "best": {k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in best.items()},
            "trades": trades,
        }
        
        if trades:
            sr = round(w_cnt / max(t_cnt, 1) * 100, 1)
            bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
            st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
            print(f"  => K={best['k']} {bt_s} {st_s} +{total_pnl:.1f}% {t_cnt}筆 {sr}%", flush=True)
        else:
            print(f"  => 無訊號", flush=True)
        
        time.sleep(0.2)
    
    api.logout()
    
    # ===== 輸出 HTML 報表 =====
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base, "backtest_6m_v4.json")
    html_path = os.path.join(base, "backtest_6m_v4.html")
    
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
    
    # 分類
    cat_0050 = [(k, v) for k, v in results.items() if v["category"] == "0050"]
    cat_hot = [(k, v) for k, v in results.items() if v["category"] == "熱門"]
    cat_extra = [(k, v) for k, v in results.items() if v["category"] == "亞翔"]
    
    all_stocks = sorted(results.items(), key=lambda x: x[1]["best"]["pnl"], reverse=True)
    
    def stock_rows(items):
        rows = ""
        for sid, v in sorted(items, key=lambda x: x[1]["best"]["pnl"], reverse=True):
            b = v["best"]
            bt = f"<{b['buy']}" if b['buy'] else "不限"
            st = f">{b['sell']}" if b['sell'] else "不限"
            sr = round(b["wins"]/max(b["trades"],1)*100, 1)
            color = "#FF3B30" if b["pnl"] > 0 else "#34C759"
            
            # 交易明細
            trade_rows = ""
            for t in v["trades"]:
                bg = "#F0FFF4" if t["profit_pct"] > 0 else "#FFF0F0"
                trade_rows += f"""<tr style="background:{bg};font-size:12px;">
                    <td>{t['buy_date']}</td>
                    <td style="color:#FF3B30;font-weight:bold;">{t['buy_price']}</td>
                    <td>{t['sell_date']}</td>
                    <td style="color:{'#FF3B30' if t['profit_pct']>0 else '#34C759'};font-weight:bold;">{t['sell_price']}</td>
                    <td style="color:{'#FF3B30' if t['profit_pct']>0 else '#34C759'};font-weight:bold;">{t['profit_pct']:+.2f}%</td>
                    <td>{t['hold_k_bars']}根K</td>
                </tr>"""
            
            rows += f"""<tr onclick="toggle('t_{sid}')" style="cursor:pointer;">
                <td><b>{v['name']}</b><br><small>{sid}</small></td>
                <td>{v['category']}</td>
                <td>K={b['k']}</td>
                <td>{bt}</td>
                <td>{st}</td>
                <td style="color:{color};font-weight:bold;">{b['pnl']:+.2f}%</td>
                <td>{b['trades']}</td>
                <td>{sr}%</td>
                <td style="font-size:11px;color:#8E8E93;">▼ 明細</td>
            </tr>
            <tr id="t_{sid}" style="display:none;">
                <td colspan="9" style="padding:0;">
                    <table style="width:100%;font-size:12px;border-collapse:collapse;margin:0;">
                        <tr style="background:#1A2B4C;color:#fff;font-size:11px;">
                            <th style="padding:6px;">買入時間</th>
                            <th style="padding:6px;">買入價</th>
                            <th style="padding:6px;">賣出時間</th>
                            <th style="padding:6px;">賣出價</th>
                            <th style="padding:6px;">獲利%</th>
                            <th style="padding:6px;">持有K線</th>
                        </tr>
                        {trade_rows}
                    </table>
                </td>
            </tr>"""
        return rows
    
    # 整體統計
    win_n = sum(1 for v in results.values() if v["best"]["pnl"] > 0)
    loss_n = sum(1 for v in results.values() if v["best"]["pnl"] <= 0)
    avg_pnl = round(sum(v["best"]["pnl"] for v in results.values()) / max(len(results), 1), 2)
    avg_trades = round(sum(v["best"]["trades"] for v in results.values()) / max(len(results), 1), 1)
    avg_sr = round(sum(v["best"]["wins"]/max(v["best"]["trades"],1)*100 for v in results.values()) / max(len(results), 1), 1)
    
    rows_0050 = stock_rows(cat_0050)
    rows_hot = stock_rows(cat_hot)
    rows_extra = stock_rows(cat_extra)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>30分K KD策略 6個月回測報告</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'PingFang TC','Microsoft JhengHei',sans-serif; background:#F2F2F7; padding:15px; }}
.header {{ background:linear-gradient(135deg,#1A2B4C,#2E4A7D); color:#fff; border-radius:12px; padding:20px; margin-bottom:15px; text-align:center; }}
.header h1 {{ font-size:20px; margin-bottom:5px; }}
.header p {{ font-size:13px; opacity:0.8; }}
.stats {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:15px; }}
.stat-card {{ background:#fff; border-radius:10px; padding:12px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
.stat-card .num {{ font-size:24px; font-weight:bold; color:#1A2B4C; }}
.stat-card .label {{ font-size:11px; color:#8E8E93; margin-top:3px; }}
.stat-card.green .num {{ color:#FF3B30; }}
.section {{ background:#fff; border-radius:12px; margin-bottom:15px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
.section-title {{ background:#1A2B4C; color:#fff; padding:12px 15px; font-size:15px; font-weight:bold; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#1A2B4C; color:#fff; padding:10px 8px; text-align:center; font-size:12px; }}
td {{ padding:10px 8px; text-align:center; border-bottom:1px solid #E5E5EA; }}
tr:nth-child(even) {{ background:#F8F9FA; }}
tr:hover:not([id^="t_"]) {{ background:#E8F0FE; }}
.up {{ color:#FF3B30 !important; font-weight:bold; }}
.down {{ color:#34C759 !important; font-weight:bold; }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold; }}
.tag-0050 {{ background:#E3F2FD; color:#1565C0; }}
.tag-hot {{ background:#FFF3E0; color:#E65100; }}
.tag-yaxiang {{ background:#F3E5F5; color:#7B1FA2; }}
@media (max-width:600px) {{
    .stats {{ grid-template-columns:1fr; }}
    table {{ font-size:12px; }}
    th, td {{ padding:8px 4px; }}
}}
</style>
</head>
<body>
<div class="header">
    <h1>🦞 小龍蝦 30分K KD策略 6個月回測</h1>
    <p>測試日期: {datetime.now().strftime('%Y/%m/%d %H:%M')} | 資料範圍: 近6個月 (約1200根30分K)</p>
</div>

<div class="stats">
    <div class="stat-card green">
        <div class="num">{len(results)}</div>
        <div class="label">成功回測檔數</div>
    </div>
    <div class="stat-card">
        <div class="num" style="color:#FF3B30;">{win_n}</div>
        <div class="label">正報酬檔數</div>
    </div>
    <div class="stat-card">
        <div class="num" style="color:#34C759;">{loss_n}</div>
        <div class="label">負報酬檔數</div>
    </div>
    <div class="stat-card">
        <div class="num" style="color:#1A2B4C;">{avg_pnl}%</div>
        <div class="label">平均報酬率</div>
    </div>
    <div class="stat-card">
        <div class="num" style="color:#1A2B4C;">{avg_trades}</div>
        <div class="label">平均交易次數</div>
    </div>
    <div class="stat-card">
        <div class="num" style="color:#1A2B4C;">{avg_sr}%</div>
        <div class="label">平均勝率</div>
    </div>
</div>

<div class="section">
    <div class="section-title">📂 0050 成分股 ({len(cat_0050)}檔) — 均+{round(sum(v['best']['pnl'] for _,v in cat_0050)/max(len(cat_0050),1),2)}%</div>
    <table>
        <tr><th>股票</th><th>分類</th><th>K值</th><th>買門檻</th><th>賣門檻</th><th>總報酬</th><th>交易</th><th>勝率</th><th>明細</th></tr>
        {rows_0050}
    </table>
</div>

<div class="section">
    <div class="section-title">🔥 永豐金熱門池 ({len(cat_hot)}檔) — 均+{round(sum(v['best']['pnl'] for _,v in cat_hot)/max(len(cat_hot),1),2)}%</div>
    <table>
        <tr><th>股票</th><th>分類</th><th>K值</th><th>買門檻</th><th>賣門檻</th><th>總報酬</th><th>交易</th><th>勝率</th><th>明細</th></tr>
        {rows_hot}
    </table>
</div>

<div class="section">
    <div class="section-title">🎯 亞翔 (6139)</div>
    <table>
        <tr><th>股票</th><th>分類</th><th>K值</th><th>買門檻</th><th>賣門檻</th><th>總報酬</th><th>交易</th><th>勝率</th><th>明細</th></tr>
        {rows_extra}
    </table>
</div>

{('<div class="section"><div class="section-title" style="background:#C62828;">❌ 失敗清單 ('+str(len(errors))+')</div><table><tr><th>股票</th><th>代號</th><th>原因</th></tr>' + ''.join(f'<tr><td>{n}</td><td>{s}</td><td>{r}</td></tr>' for s,n,r in errors) + '</table></div>') if errors else ''}

<script>
function toggle(id) {{
    var el = document.getElementById(id);
    el.style.display = el.style.display === 'none' ? '' : 'none';
}}
</script>
</body>
</html>"""
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n✅ HTML 報表已產生")
    print(f"  {html_path}")
    print(f"  {json_path}")

if __name__ == "__main__":
    main()
