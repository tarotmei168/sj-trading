#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心11檔 3年30分K KD 黃金交叉完整回測
產出 HTML 報告供本機檢查
"""
import pandas as pd
import numpy as np
import os, json
from datetime import datetime

DB_DIR = "database/3y_kd"
OUTPUT_HTML = "output/bt_3y_kd_report.html"
OUTPUT_JSON = "output/bt_3y_kd_results.json"

CORE_STOCKS = {
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "3711": "日月光", "4958": "臻鼎-KY",
    "3042": "晶技", "2454": "聯發科", "2317": "鴻海",
    "8150": "南茂", "2330": "台積電",
}

def compute_kd(close, low, high, kp):
    n = len(close)
    k = np.full(n, 50.0, dtype=float)
    d = np.full(n, 50.0, dtype=float)
    for i in range(kp - 1, n):
        llv = np.min(low[i - kp + 1 : i + 1])
        hhv = np.max(high[i - kp + 1 : i + 1])
        denom = hhv - llv
        rsv = 50.0 if denom == 0 else ((close[i] - llv) / denom) * 100
        if i == kp - 1:
            k[i] = 50.0 * 2/3 + rsv * 1/3
        else:
            k[i] = k[i-1] * 2/3 + rsv * 1/3
        d[i] = d[i-1] * 2/3 + k[i] * 1/3
    return k, d

def backtest_gc(close, low, high, vol, kp, vol_filter, pos_filter, sl=0.03, tp=0.05):
    k_vals, d_vals = compute_kd(close, low, high, kp)
    avg_vol = pd.Series(vol).rolling(5, min_periods=5).mean().values
    n = len(close)
    trades = []
    in_pos = False
    entry_idx = 0
    entry_price = 0
    for i in range(kp, n):
        gc = k_vals[i-1] < d_vals[i-1] and k_vals[i] >= d_vals[i]
        dc = k_vals[i-1] >= d_vals[i-1] and k_vals[i] < d_vals[i]
        if vol_filter and not np.isnan(avg_vol[i]):
            gc = gc and vol[i] >= avg_vol[i] * 1.5
        if pos_filter == "mid":
            gc = gc and k_vals[i] < 50
        elif pos_filter == "low":
            gc = gc and k_vals[i] < 30
        if not in_pos and gc:
            in_pos = True
            entry_idx = i
            entry_price = close[i]
        elif in_pos and dc:
            ret = (close[i] - entry_price) / entry_price
            trades.append({"entry": entry_price, "exit": close[i], "ret": ret, "reason": "dc"})
            in_pos = False
        elif in_pos and sl and entry_price > 0:
            dd = (close[i] - entry_price) / entry_price
            if dd <= -sl:
                trades.append({"entry": entry_price, "exit": close[i], "ret": dd, "reason": "sl"})
                in_pos = False
            elif tp and dd >= tp:
                trades.append({"entry": entry_price, "exit": close[i], "ret": dd, "reason": "tp"})
                in_pos = False
    return trades, k_vals, d_vals

def calc_stats(trades):
    if not trades:
        return {"n":0,"wr":0,"avg":0,"total":0,"mdd":0,"pf":0}
    rets = [t["ret"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    cum = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        cum *= (1 + r)
        if cum > peak: peak = cum
        dd = (peak - cum) / peak
        if dd > mdd: mdd = dd
    pf = sum(wins)/abs(sum(losses)) if sum(losses) < 0 else 99
    return {
        "n": len(trades),
        "wr": round(len(wins)/len(trades)*100, 1),
        "avg": round(np.mean(rets)*100, 2),
        "total": round((cum-1)*100, 2),
        "mdd": round(mdd*100, 2),
        "pf": round(pf, 2),
    }

param_grid = [(kp, vf, pf) for kp in [5,9,14,21] for vf in [False,True] for pf in ["none","mid","low"]]

all_results = {}
for sid, name in CORE_STOCKS.items():
    fp = os.path.join(DB_DIR, f"{sid}_kd.csv")
    df = pd.read_csv(fp, parse_dates=["datetime"]).sort_values("datetime")
    c, L, h, v = df["close"].values.astype(float), df["low"].values.astype(float), df["high"].values.astype(float), df["volume"].values.astype(float)
    rows = []
    for kp, vf, pf in param_grid:
        trades, _, _ = backtest_gc(c, L, h, v, kp, vf, pf)
        s = calc_stats(trades)
        rows.append({"K":kp, "VolF":"Y" if vf else "N", "Pos":pf, "trades":s["n"], "WR":s["wr"], "AvgRet":s["avg"], "Total":s["total"], "MDD":s["mdd"], "PF":s["pf"]})
    rows.sort(key=lambda r: (r["Total"], r["WR"]), reverse=True)
    all_results[sid] = {"name":name, "rows":rows}

# HTML
now = datetime.now().strftime("%Y-%m-%d %H:%M")
html = f"""<!DOCTYPE html><html lang=zh-TW><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>3年30分K KD黃金交叉回測報告</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,'Noto Sans TC',sans-serif;padding:20px}}
h1{{color:#58a6ff;font-size:1.5rem;margin-bottom:5px}}
.sub{{color:#8b949e;font-size:.85rem;margin-bottom:20px}}
.stock-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px}}
.stock-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px}}
.stock-name{{font-size:1.15rem;font-weight:700;color:#f0f6fc}}
.stock-id{{color:#8b949e;font-size:.85rem}}
.best-badge{{background:#1f6feb22;border:1px solid #1f6feb44;border-radius:4px;padding:2px 8px;font-size:.8rem;color:#58a6ff}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{text-align:left;padding:6px 8px;border-bottom:2px solid #30363d;color:#8b949e;font-weight:600;white-space:nowrap}}
td{{padding:5px 8px;border-bottom:1px solid #21262d;white-space:nowrap}}
tr:hover td{{background:#1c2128}}
.best-row td{{color:#58a6ff;font-weight:700}}
.green{{color:#3fb950}}
.red{{color:#f85149}}
.yellow{{color:#d29922}}
.total-bar{{height:4px;border-radius:2px;background:#21262d;margin-top:2px;overflow:hidden;max-width:80px}}
.total-bar-fill{{height:100%;border-radius:2px}}
.footer{{text-align:center;color:#8b949e;font-size:.75rem;margin-top:24px;padding-top:16px;border-top:1px solid #21262d}}
</style></head><body>
<h1>3年30分K KD 黃金交叉回測</h1>
<p class=sub>資料範圍: 2023-07 ~ 2026-07-21 | 每檔 ~6,500根30分K | 參數: K=5/9/14/21, 成交量放大1.5x, KD位置過濾 | 停利+5% 停損-3%</p>
"""

for sid, data in all_results.items():
    name = data["name"]
    rows = data["rows"]
    best = rows[0]
    html += f"""<div class=stock-card>
<div class=stock-header>
<div><span class=stock-name>{name}</span> <span class=stock-id>({sid})</span></div>
<div><span class=best-badge>最佳: K={best["K"]} VolF={best["VolF"]} Pos={best["Pos"]} → WR {best["WR"]}% 總報酬 {best["Total"]}%</span></div>
</div>
<table><tr><th>K</th><th>VolF</th><th>Pos</th><th>次數</th><th>勝率</th><th>平均報酬</th><th>總報酬</th><th>MDD</th><th>PF</th><th>總報酬條</th></tr>"""
    for i, r in enumerate(rows[:10]):
        cls = "best-row" if i == 0 else ""
        color = "green" if r["Total"] > 0 else ("red" if r["Total"] < 0 else "yellow")
        bar_w = max(0, min(80, r["Total"] * 2))
        bar_color = "#3fb950" if r["Total"] > 0 else "#f85149"
        html += f"""<tr class="{cls}"><td>{r["K"]}</td><td>{r["VolF"]}</td><td>{r["Pos"]}</td><td>{r["trades"]}</td><td class=green>{r["WR"]}%</td><td>{r["AvgRet"]}%</td><td class={color}>{r["Total"]}%</td><td>{r["MDD"]}%</td><td>{r["PF"]}</td><td><div class=total-bar><div class=total-bar-fill style="width:{bar_w}px;background:{bar_color}"></div></div></td></tr>"""
    html += "</table></div>"

# 各檔最佳參數總表
html += """<div class=stock-card>
<div class=stock-header><span class=stock-name>各檔最佳參數一覽</span></div>
<table><tr><th>股票</th><th>最佳K</th><th>VolF</th><th>Pos</th><th>次數</th><th>勝率</th><th>總報酬</th><th>MDD</th><th>PF</th></tr>"""
for sid, data in all_results.items():
    b = data["rows"][0]
    color = "green" if b["Total"] > 0 else "red"
    html += f"""<tr><td>{data["name"]}({sid})</td><td>K={b["K"]}</td><td>{b["VolF"]}</td><td>{b["Pos"]}</td><td>{b["trades"]}</td><td class=green>{b["WR"]}%</td><td class={color}>{b["Total"]}%</td><td>{b["MDD"]}%</td><td>{b["PF"]}</td></tr>"""
html += "</table></div>"

html += f'<div class=footer>🦞 報告產生時間: {now} | 資料來源: Shioaji 1分K → 30分K KD</div></body></html>'

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML report: {OUTPUT_HTML}")
print(f"File size: {os.path.getsize(OUTPUT_HTML)} bytes")
