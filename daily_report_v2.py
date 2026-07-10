"""
晨報 v3 — 完整版
30分K黃金交叉 + 量能分析 + 股性備註 + 買賣策略
全部用Shioaji API即時資料
輸出HTML檔，不花token
"""
import os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
now = datetime.now()
OUTPUT_FILE = os.path.join(BASE, f"{now.strftime('%m%d')}_晨報.html")

# 股票備註資料庫（股性 + 策略）
STOCK_NOTES = {
    "3711": {"name":"日月光","type":"權值半導體","strategy":"跟著台積電走，適合KD順勢操作","note":"大戶主導，留意法人買超"},
    "4958": {"name":"臻鼎KY","type":"PCB","strategy":"區間操作，支撐買壓力賣","note":"波動較大，設好停損"},
    "3042": {"name":"晶技","type":"石英元件","strategy":"KD波段操作，K<50買K>70賣","note":"今日K值急升，注意量能是否跟上"},
    "2337": {"name":"旺宏","type":"記憶體","strategy":"K<20超賣區，黃金交叉+量增=買點","note":"套牢中，等30分K金叉+量增再回補"},
    "2436": {"name":"偉詮電","type":"IC設計","strategy":"KD+MACD順勢操作","note":"最後5分鐘追價轉弱，留意"},
    "3673": {"name":"TPKKY","type":"PCB","strategy":"趨勢股，沿著MA5操作","note":"買氣強勁93%，暫不需急賣"},
    "2330": {"name":"台積電","type":"權值龍頭","strategy":"長線持有，短線KD操作","note":"大盤風向球"},
    "2454": {"name":"聯發科","type":"IC設計龍頭","strategy":"高價股，適合KD波段","note":"黃金交叉中"},
    "6139": {"name":"亞翔","type":"半導體設備","strategy":"趨勢股，沿著MA10操作","note":"高檔死亡交叉注意"},
    "2303": {"name":"聯電","type":"晶圓代工","strategy":"跟台積電連動","note":"RSI超買注意"},
    "2317": {"name":"鴻海","type":"組裝龍頭","strategy":"區間操作","note":"K值極低，超賣區留意"},
    "8150": {"name":"南茂","type":"封測","strategy":"區間震盪股，支撐買壓力賣","note":"區間90~120，你設50萬等進場"},
    "6284": {"name":"佳邦","type":"PCB","strategy":"KD波段","note":"上櫃股波動大"},
    "6213": {"name":"聯茂","type":"銅箔基板","strategy":"趨勢股","note":"高檔死亡交叉注意"},
    "1303": {"name":"南亞","type":"塑化","strategy":"長線持有","note":"K=93極度超買，注意拉回"},
    "1802": {"name":"台玻","type":"玻璃","strategy":"區間操作","note":"波動小適合存股"},
    "6271": {"name":"同欣電","type":"封測","strategy":"KD順勢","note":"30分K黃金交叉！"},
    "6451": {"name":"訊芯KY","type":"封測","strategy":"區間操作","note":"曾跌破500，等低接"},
    "2327": {"name":"國巨","type":"被動元件","strategy":"KD波段","note":"被動元件龍頭"},
    "6173": {"name":"信昌電","type":"被動元件","strategy":"KD順勢","note":"上櫃股"},
    "5425": {"name":"台半","type":"二極體","strategy":"區間操作","note":"股性溫和"},
    "3131": {"name":"弘塑","type":"設備","strategy":"高價股順勢操作","note":"波動大"},
    "3583": {"name":"辛耘","type":"設備","strategy":"KD波段","note":"股性活潑"},
    "6239": {"name":"力成","type":"封測","strategy":"KD順勢","note":"記憶體封測"},
    "2344": {"name":"華邦電","type":"記憶體","strategy":"區間操作","note":"跟旺宏連動"},
    "2408": {"name":"南亞科","type":"記憶體","strategy":"區間操作","note":"DRAM景氣循環"},
    "6770": {"name":"力積電","type":"晶圓代工","strategy":"區間操作","note":"新股波動大"},
}

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def get_30min_data(api, sid):
    """抓15天1分K -> 合併30分K -> 算KD+量"""
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=15)
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=14), start)
        try:
            kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts)==0: break
            df = pd.DataFrame({"datetime":pd.to_datetime(kbars.ts),"open":kbars.Open,"high":kbars.High,"low":kbars.Low,"close":kbars.Close,"volume":kbars.Volume})
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except: break
    if not all_dfs: return None
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"],inplace=True)
    min_df.sort_values("datetime",inplace=True)
    min_df.set_index("datetime",inplace=True)
    df30 = min_df.resample("30min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    if len(df30)<15: return None
    # KD
    low_min = df30["low"].rolling(9).min()
    high_max = df30["high"].rolling(9).max()
    rsv = ((df30["close"] - low_min)/(high_max - low_min))*100
    rsv = rsv.fillna(50)
    k_vals,d_vals = [50]*9,[50]*9
    for i in range(9,len(df30)):
        k_new = (2/3)*k_vals[-1]+(1/3)*rsv.iloc[i]
        d_new = (2/3)*d_vals[-1]+(1/3)*k_new
        k_vals.append(k_new); d_vals.append(d_new)
    df30["K"]=k_vals; df30["D"]=d_vals
    # 均量
    df30["vol_ma5"] = df30["volume"].rolling(5).mean()
    df30["vol_ratio"] = df30["volume"]/df30["vol_ma5"].replace(0,np.nan)
    return df30

def analyze_30min(df, sid, name, note_info):
    """分析30分K狀態"""
    if df is None or len(df)<12:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    k_now,d_now = round(last["K"],1), round(last["D"],1)
    k_prev,d_prev = round(prev["K"],1), round(prev["D"],1)
    close = round(last["close"],2)
    vol = int(last["volume"])
    vol_ma5 = int(last["vol_ma5"]) if not pd.isna(last.get("vol_ma5",np.nan)) else 0
    vol_r = round(last["vol_ratio"],2) if not pd.isna(last.get("vol_ratio",np.nan)) else 0
    
    # 黃金/死亡交叉
    signal = "NONE"
    if k_prev <= d_prev and k_now > d_now: signal = "GOLDEN"
    elif k_prev >= d_prev and k_now < d_now: signal = "DEATH"
    
    # 量能判斷
    vol_status = ""
    vol_advice = ""
    if vol_r > 1.5:
        vol_status = "🔥 爆量"
        if signal == "GOLDEN": vol_advice = "量增價漲，黃金交叉有效"
        elif signal == "DEATH": vol_advice = "爆量下跌，賣壓沉重"
        else: vol_advice = "爆量盤整，觀望"
    elif vol_r > 0.8:
        vol_status = "✅ 量正常"
        if signal == "GOLDEN": vol_advice = "量能溫和，金叉可信"
        elif signal == "DEATH": vol_advice = "量縮下跌，動能不足"
        else: vol_advice = "量能正常，持續觀察"
    else:
        vol_status = "💤 量縮"
        if signal == "GOLDEN": vol_advice = "量縮金叉，動能不足，等量增確認"
        elif signal == "DEATH": vol_advice = "量縮下跌，賣壓減輕"
        else: vol_advice = "量縮盤整，不宜進場"
    
    # K值位置
    k_pos = ""
    if k_now > 80: k_pos = "高檔⚠️"
    elif k_now > 60: k_pos = "偏高"
    elif k_now > 40: k_pos = "中位"
    elif k_now > 20: k_pos = "偏低"
    else: k_pos = "超賣💡"
    
    # 建議
    if signal == "GOLDEN" and vol_r >= 0.8:
        final_advice = "🟢 黃金交叉+量能足夠，可進場"
    elif signal == "GOLDEN" and vol_r < 0.8:
        final_advice = "🟡 黃金交叉但量縮，等量增再進"
    elif signal == "DEATH" and vol_r >= 1.0:
        final_advice = "🔴 死亡交叉+放量，建議出場"
    elif signal == "DEATH":
        final_advice = "🟠 死亡交叉，觀察是否帶量"
    elif k_now > 80 and vol_r < 0.8:
        final_advice = "⚠️ 高檔量縮，動能不足注意反轉"
    elif k_now < 20 and vol_r > 1.0:
        final_advice = "💡 超賣區放量，可能有買盤進場"
    else:
        final_advice = "⚪ 盤整觀望"
    
    return {
        "sid": sid, "name": name, "price": close,
        "k": k_now, "d": d_now, "signal": signal,
        "vol": f"{vol:,}", "vol_ma5": f"{vol_ma5:,}" if vol_ma5 else "-",
        "vol_ratio": vol_r, "vol_status": vol_status,
        "vol_advice": vol_advice, "k_pos": k_pos,
        "final_advice": final_advice, "note": note_info,
    }

def build_html():
    api = login()
    
    html = f"""<!DOCTYPE html><html lang="zh-TW"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>晨報 {now.strftime('%m/%d')}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Microsoft JhengHei',sans-serif;background:#f0f2f5;padding:20px;color:#333}}
.container{{max-width:1200px;margin:0auto}}
.header{{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:25px 30px;border-radius:16px;margin-bottom:20px}}
.header h1{{font-size:26px}}
.header p{{opacity:.85;font-size:13px}}
.section{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.section h2{{font-size:18px;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #eee}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#f5f5f5;padding:8px 6px;text-align:left;font-weight:600;border-bottom:2px solid #ddd;position:sticky;top:0;font-size:11px}}
td{{padding:8px 6px;border-bottom:1px solid #eee;vertical-align:middle}}
tr:hover{{background:#f0f4ff}}
.golden{{background:#e8f5e9!important}}
.death{{background:#ffebee!important}}
.vol-up{{color:#d32f2f;font-weight:600}}
.vol-down{{color:#2e7d32}}
.vol-normal{{color:#666}}
.footer{{text-align:center;padding:20px;color:#999;font-size:11px}}
.note{{font-size:11px;color:#666;max-width:200px}}
.strategy{{font-size:11px;color:#1565c0}}
</style></head><body>
<div class=container>
<div class=header><h1>📊 晨報系統 v3 — 30分K即時分析</h1>
<p>{now.strftime('%Y/%m/%d %H:%M')} | 資料來源：永豐金Shioaji API（即時0延遲）</p></div>
"""
    
    # 庫存股 + 全部觀察股
    sids = ["3711","4958","3042","2337","2436","3673",
            "2330","2454","6139","2303","2317","8150",
            "6284","6213","1303","1802","6271","6451",
            "2327","6173","5425","3131","3583","6239",
            "2344","2408","6770","5351","2369","8016",
            "2464","3588","00947","3545","3003","6693",
            "6147","2316","8358","4961","6187","2458",
            "3234","6155","8121","6257","3026","6435",
            "2493","5493","8086","2492","8028","3455",
            "2481","6944","3532","2308"]
    
    # 收集所有結果
    results = {"golden":[], "death":[], "normal":[]}
    
    for sid in sids:
        try:
            df = get_30min_data(api, sid)
            note = STOCK_NOTES.get(sid, {})
            name = note.get("name", sid)
            note_info = note.get("note", "")
            strategy = note.get("strategy", "")
            r = analyze_30min(df, sid, name, note_info)
            if r:
                r["strategy"] = strategy
                if r["signal"] == "GOLDEN": results["golden"].append(r)
                elif r["signal"] == "DEATH": results["death"].append(r)
                else: results["normal"].append(r)
        except: pass
    
    api.logout()
    
    # ---- 黃金交叉表 ----
    html += '<div class="section"><h2>🟢 30分K 黃金交叉（潛在買點）</h2><table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>成交量</th><th>量比</th><th>量能狀態</th><th>量能分析</th><th>建議</th><th>股性備註</th><th>策略</th>'
    html += '</tr></thead><tbody>'
    for r in results["golden"]:
        vol_cls = "vol-up" if r["vol_ratio"]>1 else ("vol-down" if r["vol_ratio"]<0.5 else "vol-normal")
        html += f'<tr class="golden"><td><b>{r["name"]}</b><br><small>{r["sid"]}</small></td>'
        html += f'<td><b>{r["price"]}</b></td>'
        html += f'<td>{r["k"]}/{r["d"]}</td>'
        html += f'<td>{r["k_pos"]}</td>'
        html += f'<td>{r["vol"]}</td>'
        html += f'<td class="{vol_cls}">{r["vol_ratio"]}</td>'
        html += f'<td>{r["vol_status"]}</td>'
        html += f'<td style="font-size:11px">{r["vol_advice"]}</td>'
        html += f'<td><b>{r["final_advice"]}</b></td>'
        html += f'<td class="note">{r["note"]}</td>'
        html += f'<td class="strategy">{r["strategy"]}</td></tr>'
    if not results["golden"]:
        html += '<tr><td colspan="11" style="text-align:center;color:#999">目前無黃金交叉</td></tr>'
    html += '</tbody></table></div>'
    
    # ---- 死亡交叉表 ----
    html += '<div class="section"><h2>🔴 30分K 死亡交叉（注意賣點）</h2><table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>成交量</th><th>量比</th><th>量能狀態</th><th>量能分析</th><th>建議</th><th>股性備註</th><th>策略</th>'
    html += '</tr></thead><tbody>'
    for r in results["death"]:
        vol_cls = "vol-up" if r["vol_ratio"]>1 else ("vol-normal")
        html += f'<tr class="death"><td><b>{r["name"]}</b><br><small>{r["sid"]}</small></td>'
        html += f'<td><b>{r["price"]}</b></td>'
        html += f'<td>{r["k"]}/{r["d"]}</td>'
        html += f'<td>{r["k_pos"]}</td>'
        html += f'<td>{r["vol"]}</td>'
        html += f'<td class="{vol_cls}">{r["vol_ratio"]}</td>'
        html += f'<td>{r["vol_status"]}</td>'
        html += f'<td style="font-size:11px">{r["vol_advice"]}</td>'
        html += f'<td><b>{r["final_advice"]}</b></td>'
        html += f'<td class="note">{r["note"]}</td>'
        html += f'<td class="strategy">{r["strategy"]}</td></tr>'
    if not results["death"]:
        html += '<tr><td colspan="11" style="text-align:center;color:#999">目前無死亡交叉</td></tr>'
    html += '</tbody></table></div>'
    
    # ---- 其他股票 ----
    html += '<div class="section"><h2>⚪ 其他觀察股（無交叉訊號）</h2><table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>量比</th><th>量能狀態</th><th>建議</th><th>股性備註</th>'
    html += '</tr></thead><tbody>'
    for r in results["normal"][:30]:  # 只顯示前30支
        vol_cls = "vol-up" if r["vol_ratio"]>1 else ("vol-down" if r["vol_ratio"]<0.5 else "")
        html += f'<tr><td><b>{r["name"]}</b><br><small>{r["sid"]}</small></td>'
        html += f'<td>{r["price"]}</td>'
        html += f'<td>{r["k"]}/{r["d"]}</td>'
        html += f'<td>{r["k_pos"]}</td>'
        html += f'<td class="{vol_cls}">{r["vol_ratio"]}</td>'
        html += f'<td>{r["vol_status"]}</td>'
        html += f'<td style="font-size:11px">{r["final_advice"]}</td>'
        html += f'<td class="note">{r["note"]}</td></tr>'
    if not results["normal"]:
        html += '<tr><td colspan="8" style="text-align:center;color:#999">無其他股票</td></tr>'
    html += '</tbody></table></div>'
    
    # ---- 說明 ----
    html += f"""
<div class="section">
<h2>📖 使用說明</h2>
<table><tr><td style="width:120px">🟢 黃金交叉+量增</td><td>最佳買點，可進場</td></tr>
<tr><td>🟡 黃金交叉+量縮</td><td>假突破嫌疑，等量增再進</td></tr>
<tr><td>🔴 死亡交叉+放量</td><td>賣壓出籠，建議出場</td></tr>
<tr><td>💤 量縮盤整</td><td>不宜進場，等方向</td></tr>
<tr><td>🔥 爆量</td><td>量比>1.5，方向明確</td></tr>
<tr><td>💡 超賣區</td><td>K<20，留意反彈機會</td></tr>
<tr><td>⚠️ 高檔</td><td>K>80，注意回檔</td></tr>
</table>
<p style="margin-top:12px;color:#999;font-size:12px">
📌 30分K使用永豐金Shioaji API即時資料，無延遲<br>
📌 每天8:30自動更新，雙擊此檔案即可開啟
</p>
</div>
<div class=footer>晨報系統 v3 | {now.strftime('%Y/%m/%d %H:%M')}</div>
</div></body></html>
"""
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {OUTPUT_FILE}")

if __name__ == "__main__":
    build_html()
