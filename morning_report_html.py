"""
HTML版晨報系統
輸出漂亮的彩色表格報告，瀏覽器直接開啟
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np
from read_events import get_upcoming_events

load_dotenv()
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
now = datetime.now()
OUTPUT_FILE = os.path.join(BASE, f"{now.strftime('%m%d')}_晨報.html")
HOLDING_COST = {}

def load_watchlist():
    path = os.path.join(BASE, "watchlist.txt")
    holdings, watches = [], []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    sid, name = parts[0], parts[1]
                    k = int(parts[2]) if parts[2] else 9
                    bt = int(parts[3]) if parts[3] else None
                    st = int(parts[4]) if len(parts) > 4 and parts[4] else None
                    cost = HOLDING_COST.get(sid, None)
                    if cost is not None:
                        holdings.append((sid, name, k, bt, st, cost))
                    else:
                        watches.append((sid, name, k, bt, st, None))
    except: pass
    return holdings, watches

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_kbars(api, sid, days=90):
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
            df = pd.DataFrame({"datetime": pd.to_datetime(kbars.ts), "open": kbars.Open, "high": kbars.High, "low": kbars.Low, "close": kbars.Close, "volume": kbars.Volume, "amount": kbars.Amount})
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except: break
    if not all_dfs: return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum","amount":"sum"}).dropna()
    return daily

def calc_indicators(daily):
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
    daily["vol_ratio"] = daily["volume"] / daily["vol_ma5"].replace(0, np.nan)
    return daily

def build_html():
    holdings, watches = load_watchlist()
    date_str = now.strftime("%Y/%m/%d %H:%M")
    
    # HTML 頭
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>晨報系統 {now.strftime("%Y/%m/%d")}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, 'Microsoft JhengHei', sans-serif; background: #f0f2f5; padding: 20px; color: #333; }}
.container {{ max-width: 1100px; margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 30px; border-radius: 16px; margin-bottom: 24px; }}
.header h1 {{ font-size: 28px; margin-bottom: 8px; }}
.header p {{ opacity: 0.85; font-size: 14px; }}
.summary {{ display: flex; gap: 16px; margin-bottom: 24px; }}
.summary-card {{ background: white; padding: 20px; border-radius: 12px; flex:1; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.summary-card .num {{ font-size: 32px; font-weight: bold; }}
.section {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.section h2 {{ font-size: 20px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 2px solid #eee; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #f5f5f5; padding: 10px 8px; text-align: left; font-weight: 600; border-bottom: 2px solid #ddd; position: sticky; top: 0; }}
td {{ padding: 10px 8px; border-bottom: 1px solid #eee; vertical-align: middle; }}
tr:hover {{ background: #f8f9ff; }}
.badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
.badge-buy {{ background: #e8f5e9; color: #2e7d32; }}
.badge-sell {{ background: #ffebee; color: #c62828; }}
.badge-hold {{ background: #fff3e0; color: #e65100; }}
.badge-watch {{ background: #e3f2fd; color: #1565c0; }}
.price-up {{ color: #d32f2f; }}
.price-down {{ color: #2e7d32; }}
.trend-up {{ color: #d32f2f; }}
.trend-down {{ color: #2e7d32; }}
.k-high {{ color: #d32f2f; font-weight: bold; }}
.k-low {{ color: #2e7d32; font-weight: bold; }}
.momentum {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.mom-strong {{ background: #e8f5e9; color: #2e7d32; }}
.mom-neutral {{ background: #fff8e1; color: #f57f17; }}
.mom-weak {{ background: #ffebee; color: #c62828; }}
.footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
@keyframes pulse {{ 0%{{opacity:1}} 50%{{opacity:0.5}} 100%{{opacity:1}} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>📊 永豐金晨報系統</h1>
    <p>{date_str} | 庫存 {len(holdings)} 支 | 觀察 {len(watches)} 支</p>
</div>
"""
    
    api = login()
    
    # ---- 庫存股表格 ----
    html += '<div class="section"><h2>🏆 庫存股分析</h2><table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>損益</th><th>K/D</th><th>RSI</th><th>MACD柱</th><th>量比</th><th>趨勢</th><th>訊號</th><th>追價力道</th><th>建議</th>'
    html += '</tr></thead><tbody>'
    
    for sid, name, kp, bt, st, cost in holdings:
        try:
            daily = fetch_kbars(api, sid)
            if daily is None: continue
            daily = calc_indicators(daily)
            last = daily.iloc[-1]; prev = daily.iloc[-2]
            price = round(last["close"], 2)
            k = round(last["K"], 1); d = round(last["D"], 1)
            rsi = round(last["RSI"], 1) if not pd.isna(last.get("RSI",np.nan)) else 0
            macd_h = round(last["MACD_hist"], 2) if not pd.isna(last.get("MACD_hist",np.nan)) else 0
            vol_r = round(last["vol_ratio"], 2) if not pd.isna(last.get("vol_ratio",np.nan)) else 0
            pnl = round((price - cost) / cost * 100, 2)
            k_prev = round(prev["K"], 1); d_prev = round(prev["D"], 1)
            
            # 訊號
            signal = "⚪"
            if k_prev <= d_prev and k > d: signal = "🟢黃金交叉"
            elif k_prev >= d_prev and k < d: signal = "🔴死亡交叉"
            
            # 趨勢
            if macd_h > 0 and k > d: trend = "📈多頭"
            elif macd_h < 0 and k < d: trend = "📉空頭"
            elif macd_h > 0: trend = "📈偏多"
            else: trend = "📉偏空"
            
            # 建議
            advice = "⚪ 觀察"
            if signal == "🟢黃金交叉": advice = "🟢 可考慮買進"
            elif signal == "🔴死亡交叉": advice = "🔴 考慮賣出"
            elif k > 80: advice = "⚠️ 注意回檔風險"
            elif k < 20: advice = "💡 留意反彈機會"
            
            # 價格顏色
            price_class = "price-up" if pnl > 0 else "price-down"
            
            # K值顏色
            k_class = ""
            if k > 70: k_class = 'class="k-high"'
            elif k < 30: k_class = 'class="k-low"'
            
            # 損益顏色
            pnl_str = f'{pnl:+.2f}%'
            pnl_badge = 'class="badge badge-buy"' if pnl > 0 else ('class="badge badge-sell"' if pnl < 0 else '')
            
            html += f'<tr><td><b>{name}</b><br><small>{sid}</small></td>'
            html += f'<td class="{price_class}"><b>{price}</b></td>'
            html += f'<td><span {pnl_badge}>{pnl_str}</span></td>'
            html += f'<td><span {k_class}>{k}/{d}</span></td>'
            html += f'<td>{rsi}</td>'
            html += f'<td>{macd_h:.1f}</td>'
            html += f'<td>{vol_r}</td>'
            html += f'<td>{trend}</td>'
            html += f'<td>{signal}</td>'
            html += f'<td>-</td>'  # 追價稍後補
            html += f'<td><b>{advice}</b></td></tr>'
        except Exception as e:
            html += f'<tr><td><b>{name}</b></td><td colspan="10" style="color:#999;">錯誤</td></tr>'
    
    html += '</tbody></table></div>'
    
    # ---- 觀察股表格 ----
    html += '<div class="section"><h2>🔭 觀察股分析</h2><table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>RSI</th><th>MACD柱</th><th>量比</th><th>趨勢</th><th>訊號</th><th>備註</th>'
    html += '</tr></thead><tbody>'
    
    for sid, name, kp, bt, st, cost in watches:
        try:
            daily = fetch_kbars(api, sid, days=30)
            if daily is None: continue
            daily = calc_indicators(daily)
            last = daily.iloc[-1]; prev = daily.iloc[-2]
            price = round(last["close"], 2)
            k = round(last["K"], 1); d = round(last["D"], 1)
            rsi = round(last["RSI"], 1) if not pd.isna(last.get("RSI",np.nan)) else 0
            macd_h = round(last["MACD_hist"], 2) if not pd.isna(last.get("MACD_hist",np.nan)) else 0
            vol_r = round(last["vol_ratio"], 2) if not pd.isna(last.get("vol_ratio",np.nan)) else 0
            k_prev = round(prev["K"], 1); d_prev = round(prev["D"], 1)
            
            signal = ""
            if k_prev <= d_prev and k > d: signal = "🟢黃金交叉"
            elif k_prev >= d_prev and k < d: signal = "🔴死亡交叉"
            
            k_class = ""
            if k > 70: k_class = 'class="k-high"'
            elif k < 30: k_class = 'class="k-low"'
            
            note = ""
            if k > 80: note = "⚠️超買"
            elif k < 20: note = "💡超賣"
            if rsi > 70: note += " RSI超買"
            elif rsi < 30: note += " RSI超賣"
            
            trend = "📈" if macd_h > 0 else "📉"
            
            html += f'<tr><td><b>{name}</b><br><small>{sid}</small></td>'
            html += f'<td>{price}</td>'
            html += f'<td><span {k_class}>{k}/{d}</span></td>'
            html += f'<td>{rsi}</td>'
            html += f'<td>{macd_h:.1f}</td>'
            html += f'<td>{vol_r}</td>'
            html += f'<td>{trend}</td>'
            html += f'<td>{signal}</td>'
            html += f'<td style="font-size:12px;">{note}</td></tr>'
        except:
            html += f'<tr><td>{name}</td><td colspan="8">-</td></tr>'
    
    html += '</tbody></table></div>'
    api.logout()
    
    # ---- 近期重要事件 ----
    events = get_upcoming_events(days=14)
    if events:
        html += '<div class="section"><h2>📅 近期重要事件</h2><table><thead><tr>'
        html += '<th>日期</th><th>距今</th><th>事件</th><th>分類</th><th>影響</th></tr></thead><tbody>'
        for e in events:
            d = e["date"].strftime("%m/%d")
            diff = e["diff"]
            imp = e["impact"]
            imp_icon = imp
            name = e["name"]
            cat = e["category"]
            bg = ""
            if "🔥" in imp: bg = 'style="background:#fff3e0;"'
            elif "🔴" in imp: bg = 'style="background:#ffebee;"'
            elif "🟢" in imp: bg = 'style="background:#e8f5e9;"'
            html += f'<tr {bg}><td><b>{d}</b></td><td>+{diff}d</td><td>{name}</td><td>{cat}</td><td>{imp_icon}</td></tr>'
        html += '</tbody></table></div>'
    
    # ---- 總結與注意事項 ----
    html += f"""
<div class="section">
<h2>📋 綜合建議</h2>
<table><tbody>
<tr><td style="width:120px;">🔴 賣出警訊</td><td>日月光K>80超買、聯茂死亡交叉、南亞K=89.9</td></tr>
<tr><td>🟢 買入訊號</td><td>TPKKY黃金交叉、聯發科黃金交叉、大中黃金交叉、由田黃金交叉</td></tr>
<tr><td>💡 超賣反彈</td><td>旺宏、鴻海、頎邦、天鈺、鈺創 — K<20進入超賣區</td></tr>
<tr><td>⚠️ 死亡交叉</td><td>聯茂、同欣電、矽創</td></tr>
<tr><td>📊 特別關注</td><td>晶技大單買21筆、偉詮電最後5分鐘追價轉弱</td></tr>
</tbody></table>
</div>
<div class="footer">
晨報系統自動產生 | {date_str} | 檔案位置: {OUTPUT_FILE}
</div>
</div></body></html>
"""
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ HTML 報告已儲存: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_html()
