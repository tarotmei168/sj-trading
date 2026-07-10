"""
小龍蝦三合一選股引擎 v2 — HTML網頁版
============================================
輸出分類:
  1. 成交量前20名 (永豐金動態池)
  2. 熱門題材股
  3. 高EPS低股價潛力股 (銅板價)
  4. 庫存股監控
"""
import os, sys, json, time, argparse, warnings
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np
import urllib.request

warnings.filterwarnings('ignore', category=RuntimeWarning)
sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ============================================================
# 鉅亨網新聞API
# ============================================================
NEWS_API = "https://news.cnyes.com/api/v3/news/category/tw_stock?limit=8"
MACRO_API = "https://news.cnyes.com/api/v3/news/category/tw_macro?limit=5"

CRITICAL_KW = ["戰爭","開戰","衝突","軍事","制裁","封鎖","通膨","CPI","利率","升息","降息",
               "FOMC","FED","崩盤","恐慌","股災","熔斷","地震","疫情","倒閉","破產","關稅","貿易戰"]

STOCK_KW = {"3042":["晶技","TXC"],"2337":["旺宏"],"2436":["偉詮電"],"5351":["鈺創"],
            "3711":["日月光","ASE"],"4958":["臻鼎"],"8150":["南茂"],"6139":["亞翔"],
            "2330":["台積電","TSMC"],"2454":["聯發科"],"2327":["國巨"],"3131":["弘塑"],
            "3583":["辛耘"],"3037":["欣興"],"3189":["景碩"],"2344":["華邦電"]}

def fetch_news():
    items = []
    for name, url in [("台股",NEWS_API),("政經",MACRO_API)]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            d = json.loads(resp.read().decode("utf-8"))
            for item in d.get("items",{}).get("data",[]):
                t = item.get("title","")
                s = item.get("summary","")
                p = item.get("publishAt",0)
                nid = item.get("newsId",0)
                stocks = item.get("otherProduct",[])
                full = (t+" "+s).lower()
                is_c = any(kw.lower() in full for kw in CRITICAL_KW)
                reasons = [kw for kw in CRITICAL_KW if kw.lower() in full]
                related = []
                for sp in stocks:
                    if sp.startswith("TWS:") and sp.endswith(":STOCK:COMMON"):
                        related.append(sp.split(":")[1])
                for sid, kws in STOCK_KW.items():
                    if any(kw.lower() in full for kw in kws) and sid not in related:
                        related.append(sid)
                items.append({
                    "title":t,"summary":s,
                    "time":datetime.fromtimestamp(p).strftime("%m/%d %H:%M") if p else "",
                    "is_critical":is_c,"reasons":reasons,
                    "related":related,"source":name,
                })
        except:
            pass
    return items

# ============================================================
# 基本面資料庫 + 分類
# ============================================================
FUNDAMENTAL = {
    "3042":{"name":"晶技","eps":5.23,"pe":47.64,"industry":"石英元件","theme":"網通/車用/iPhone","type":"中型績優","school":"區間波段"},
    "2337":{"name":"旺宏","eps":-0.41,"pe":None,"industry":"NOR Flash","theme":"記憶體復甦","type":"景氣循環","school":"籌碼大戶"},
    "2436":{"name":"偉詮電","eps":3.47,"pe":21.85,"industry":"IC設計","theme":"USB PD","type":"中型IC設計","school":"籌碼大戶"},
    "5351":{"name":"鈺創","eps":0.96,"pe":85.51,"industry":"利基型DRAM","theme":"AI邊緣運算","type":"小型主力","school":"籌碼大戶"},
    "3673":{"name":"TPK-KY","eps":-5.31,"pe":None,"industry":"觸控","theme":"摺疊手機","type":"景氣循環","school":"區間波段"},
    "3711":{"name":"日月光","eps":6.89,"pe":24.09,"industry":"封測","theme":"先進封裝/AI","type":"大型權值","school":"區間波段"},
    "4958":{"name":"臻鼎-KY","eps":9.62,"pe":49.11,"industry":"PCB","theme":"AI伺服器/蘋果","type":"大型權值","school":"強勢動能"},
    "8150":{"name":"南茂","eps":1.19,"pe":88.24,"industry":"記憶體封測","theme":"記憶體復甦","type":"中型景氣","school":"區間波段"},
    "6139":{"name":"亞翔","eps":36.10,"pe":26.26,"industry":"無塵室","theme":"半導體擴廠/AI","type":"中型成長","school":"強勢動能","cheap_note":"EPS36但股價948→銅板價? 從293漲到948已非低檔"},
    "2330":{"name":"台積電","eps":75.52,"pe":32.36,"industry":"晶圓代工","theme":"AI晶片/先進製程","type":"龍頭權值","school":"區間波段"},
    "2454":{"name":"聯發科","eps":82.62,"pe":35.14,"industry":"IC設計","theme":"AI/手機晶片","type":"大型權值","school":"強勢動能"},
    "2317":{"name":"鴻海","eps":18.58,"pe":12.82,"industry":"EMS","theme":"AI伺服器/蘋果/電動車","type":"超級權值","school":"區間波段","cheap_note":"EPS18.5 PE12.8! 本益比低+蘋果+AI題材! 銅板價?"},
    "3037":{"name":"欣興","eps":7.54,"pe":137.63,"industry":"IC載板","theme":"ABF/AI","type":"大型權值","school":"強勢動能"},
    "3189":{"name":"景碩","eps":3.91,"pe":211.35,"industry":"IC載板","theme":"ABF載板","type":"中型權值","school":"強勢動能"},
    "2344":{"name":"華邦電","eps":0.27,"pe":681.48,"industry":"DRAM","theme":"記憶體/車用","type":"景氣循環","school":"籌碼大戶"},
    "2327":{"name":"國巨","eps":12.71,"pe":82.20,"industry":"被動元件","theme":"MLCC/車用","type":"龍頭權值","school":"區間波段"},
    "3131":{"name":"弘塑","eps":52.89,"pe":71.57,"industry":"半導體濕式設備","theme":"先進封裝","type":"高價小型績優","school":"強勢動能"},
    "3583":{"name":"辛耘","eps":14.76,"pe":57.67,"industry":"半導體設備","theme":"AI/先進封裝","type":"中型投信","school":"強勢動能"},
    "2308":{"name":"台達電","eps":19.63,"pe":29.99,"industry":"電源","theme":"AI伺服器電源","type":"龍頭權值","school":"區間波段"},
    "2382":{"name":"廣達","eps":12.21,"pe":16.67,"industry":"伺服器","theme":"AI伺服器","type":"大型權值","school":"強勢動能"},
    "8046":{"name":"南電","eps":26.68,"pe":44.42,"industry":"IC載板","theme":"ABF載板","type":"大型權值","school":"強勢動能"},
    "3231":{"name":"緯創","eps":5.70,"pe":27.58,"industry":"伺服器","theme":"AI伺服器","type":"大型權值","school":"強勢動能"},
    "6770":{"name":"力積電","eps":0.42,"pe":172.38,"industry":"晶圓代工","theme":"成熟製程","type":"中型","school":"區間波段"},
    "2603":{"name":"長榮","eps":21.21,"pe":8.91,"industry":"貨櫃航運","theme":"運價反彈","type":"景氣循環","school":"區間波段"},
    "2609":{"name":"陽明","eps":10.14,"pe":5.43,"industry":"貨櫃航運","theme":"運價反彈","type":"景氣循環","school":"區間波段"},
    "2618":{"name":"長榮航","eps":2.63,"pe":16.27,"industry":"航空","theme":"客運復甦","type":"景氣循環","school":"區間波段"},
    "2888":{"name":"新光金","eps":0.89,"pe":32.58,"industry":"金控","theme":"金融","type":"金融","school":"區間波段"},
    "2892":{"name":"第一金","eps":1.73,"pe":18.50,"industry":"銀行","theme":"金融","type":"金融權值","school":"區間波段"},
    "1301":{"name":"台塑","eps":1.41,"pe":34.04,"industry":"石化","theme":"塑化","type":"傳統權值","school":"區間波段"},
    "2002":{"name":"中鋼","eps":0.32,"pe":56.25,"industry":"鋼鐵","theme":"鋼價","type":"傳統權值","school":"區間波段"},
    "2412":{"name":"中華電","eps":4.53,"pe":30.03,"industry":"電信","theme":"5G","type":"電信權值","school":"區間波段"},
}

# ============================================================
# 永豐金熱門股池 (成交量前20常駐, 動態由shioaji更新)
# ============================================================
HOT_STOCKS = [
    "2330","2454","2317","2303","2344","2408","6770","2603","2609","2618",
    "2610","2888","2892","2881","2882","3037","3189","8046","3711","2382",
    "3034","2308","3231","2356","2357","2301","2885","2887","2886","2891",
    "5880","1101","1216","1301","1303","2002","2105","2207","2412",
]

# 題材分類
THEME_STOCKS = {
    "AI/先進封裝": ["2330","2454","2317","2382","3231","2308","3711","3131","3583","6139","3037","3189","8046","2327"],
    "蘋概股": ["2317","4958","3042","3008","2353","2474"],
    "記憶體": ["2337","2344","2408","5351","8150","6770"],
    "金融": ["2881","2882","2886","2887","2885","2891","2892","5880","2888"],
    "傳產/航運": ["2603","2609","2610","2618","1301","1303","2002","1101","1216"],
}

# 高EPS低股價潛力股篩選
def find_bargain_stocks():
    """找高EPS但股價低的潛力股"""
    bargains = []
    for sid, info in FUNDAMENTAL.items():
        eps = info.get("eps", 0)
        pe = info.get("pe")
        if eps and eps > 3:
            if pe is None or pe < 20:
                bargains.append(sid)
            elif eps > 10 and (pe is None or pe < 30):
                bargains.append(sid)
    return bargains

# ============================================================
# Shioaji API
# ============================================================
def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_30k(api, sid, days=200):
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
        k_new = (2/3)*k_vals[i-1] + (1/3)*rsv[i]
        d_new = (2/3)*d_vals[i-1] + (1/3)*k_new
        k_vals[i] = k_new; d_vals[i] = d_new
    return k_vals, d_vals

def analyze_stock(api, sid, f_info):
    close = None; k_now = None; d_now = None; price_pos = None; can_buy = False
    h60=None; l60=None; zone="無資料"; in_golden=False; golden_now=False
    best_pnl=None; best_k=None; best_trades=None
    recent_bars = []
    try:
        df30 = fetch_30k(api, sid, 200)
        if df30 is not None and len(df30) >= 20:
            close = round(df30["close"].iloc[-1], 2)
            cl = df30["close"].values; lv = df30["low"].values; hv = df30["high"].values; n = len(cl)
            # 快速找最佳K (用K=3,5,7)
            best_pnl_t = -999
            for kp in [3,5,7,9,12]:
                k_arr = np.full(n, 50.0); d_arr = np.full(n, 50.0)
                k_arr, d_arr = compute_kd(k_arr, d_arr, cl, lv, hv, kp)
                pos=0; bp=0; total=0.0
                for i in range(kp+1, n):
                    if pos==0 and k_arr[i-1]<=d_arr[i-1] and k_arr[i]>d_arr[i]:
                        pos=1; bp=cl[i]
                    elif pos==1 and k_arr[i-1]>=d_arr[i-1] and k_arr[i]<d_arr[i]:
                        pos=0; total+=((cl[i]-bp)/bp)*100
                if pos==1: total+=((cl[-1]-bp)/bp)*100
                if total > best_pnl_t:
                    best_pnl_t = total; best_k = kp
            
            # 用最佳K算當前KD
            k_arr = np.full(n, 50.0); d_arr = np.full(n, 50.0)
            k_arr, d_arr = compute_kd(k_arr, d_arr, cl, lv, hv, best_k)
            k_now = round(k_arr[-1],2); d_now = round(d_arr[-1],2)
            in_golden = k_now > d_now
            golden_now = (k_arr[-2] <= d_arr[-2] and k_now > d_now)
            best_pnl = round(best_pnl_t,1); best_trades = 0
            
            h60 = round(df30["high"].tail(60).max(),2)
            l60 = round(df30["low"].tail(60).min(),2)
            price_pos = round((close - l60)/(h60-l60)*100,0) if h60>l60 else 50
            
            if k_now <= 20: zone="極低檔"
            elif k_now <= 40: zone="偏低檔"
            elif k_now <= 60: zone="中檔"
            elif k_now <= 80: zone="偏高檔"
            else: zone="超高檔"
            
            if golden_now:
                can_buy = True
            
            for i in range(min(5,n),0,-1):
                recent_bars.append({
                    "t": df30.index[-i].strftime("%m/%d %H:%M"),
                    "c": round(cl[-i],2),
                    "k": round(k_arr[-i],2),
                    "d": round(d_arr[-i],2),
                })
    except:
        pass
    
    return {
        "close": close, "k": k_now, "d": d_now,
        "golden_now": golden_now, "in_golden": in_golden,
        "can_buy": can_buy, "zone": zone,
        "h60": h60, "l60": l60, "pos_pct": price_pos,
        "best_pnl": best_pnl, "best_k": best_k, "best_trades": best_trades,
        "recent_bars": recent_bars,
        "error": close is None,
    }

def score_stock(sid, info, kd):
    s = 5
    eps = info.get("eps", 0)
    if eps >= 30: s += 3
    elif eps >= 10: s += 2
    elif eps >= 3: s += 1
    elif eps < 0: s -= 2
    
    pe = info.get("pe")
    if pe and pe < 15: s += 2
    elif pe and pe > 80: s -= 1
    
    if kd and not kd["error"]:
        if kd["can_buy"]: s += 2
        elif kd["in_golden"] and kd["k"] and kd["k"] < 50: s += 1
        elif kd["k"] and kd["k"] > 80: s -= 1
    
    return max(1, min(10, s))

def main():
    print("Loading...")
    news = fetch_news()
    
    api = login()
    
    # 分類
    bargain_sids = find_bargain_stocks()
    all_sids = list(set(list(FUNDAMENTAL.keys()) + HOT_STOCKS))
    
    results = {}
    total = len(all_sids)
    
    for idx, sid in enumerate(all_sids):
        if sid not in FUNDAMENTAL:
            continue
        info = FUNDAMENTAL[sid]
        name = info["name"]
        print(f"[{idx+1}/{total}] {name}...", end=" ", flush=True)
        
        kd = analyze_stock(api, sid, info)
        score = score_stock(sid, info, kd)
        
        results[sid] = {
            "name": name, "info": info, "kd": kd, "score": score,
            "is_hot": sid in HOT_STOCKS,
            "is_bargain": sid in bargain_sids,
        }
        
        k_str = f"K={kd['k']}" if kd["k"] else "無KD"
        print(f"{k_str} {score}分", flush=True)
        time.sleep(0.2)
    
    api.logout()
    
    # ===== 分類輸出 =====
    cat_hot = {t: [] for t in THEME_STOCKS}
    for theme_name, sids in THEME_STOCKS.items():
        for sid in sids:
            if sid in results:
                cat_hot[theme_name].append(results[sid])
    
    bargain_list = [results[s] for s in bargain_sids if s in results]
    hot20_list = [results[s] for s in HOT_STOCKS if s in results and s in FUNDAMENTAL]
    
    # ===== 產出HTML =====
    def td(r):
        kd = r["kd"]; info = r["info"]
        name = info["name"]; sid_val = r.get("sid_hint","")
        
        price = f"{kd['close']}" if kd["close"] else "?"
        eps_s = f"EPS{info['eps']}" if info.get("eps") else ""
        pe_s = f"PE{info['pe']}" if info.get("pe") else ""
        k_str = f"K={kd['k']} D={kd['d']}" if kd["k"] else "無KD"
        zone_s = kd["zone"] if kd["zone"] else ""
        
        act = ""
        if kd["can_buy"]: act = "✅ Now!"
        elif kd["in_golden"] and kd["k"] and kd["k"] < 50: act = "🟢 進"
        elif kd["in_golden"]: act = "🟡 持"
        elif kd["k"] and kd["k"] < 30: act = "🔵 等"
        else: act = "🔴 觀"
        
        pct = f"{kd['pos_pct']}%" if kd["pos_pct"] is not None else "?"
        h = kd["h60"] if kd["h60"] else "?"; l = kd["l60"] if kd["l60"] else "?"
        score_s = f"{r['score']}/10"
        
        return f"""<tr>
            <td><b>{name}</b><br><small>{sid_val}</small></td>
            <td>{price}</td>
            <td><small>{eps_s}<br>{pe_s}</small></td>
            <td><small>{k_str}<br><span class="{'green' if kd['in_golden'] else 'red'}">{zone_s}</span></small></td>
            <td><small>{l}-{h}<br>位置{pct}</small></td>
            <td><small>{info['theme']}</small></td>
            <td class="{ 'up' if kd['can_buy'] else 'down' }">{act}</td>
            <td>{score_s}</td>
        </tr>"""
    
    def section(title, items, sid_key="sid"):
        rows = ""
        for r in items:
            rows += td(r)
        return title, rows, len(items)
    
    # 新聞區
    news_html = ""
    for n in news:
        tag = "🚨 CRITICAL" if n["is_critical"] else "📰"
        rel = ""
        if n["related"]:
            names = []
            for s in n["related"]:
                if s in FUNDAMENTAL:
                    names.append(FUNDAMENTAL[s]["name"])
            if names:
                rel = f'<span class="tag-rel">{" ".join(names)}</span>'
        news_html += f"""<div class="news-item {'critical' if n['is_critical'] else ''}">
            <div class="news-time">{n['time']}</div>
            <div class="news-title">{tag} {n['title']}</div>
            {rel}
        </div>"""
    
    # 庫存股
    hold_sids = ["3042","2337","2436","5351","3673","3711","4958","8150"]
    hold_items = [results[s] for s in hold_sids if s in results]
    bargain_items = sorted(bargain_list, key=lambda x: x["info"]["eps"], reverse=True)[:15]
    
    s_hot, r_hot, n_hot = section("🔥 成交量熱門股 (永豐金動態池)", sorted(hot20_list, key=lambda x: x["score"], reverse=True))
    
    theme_sections = []
    for tn, items in cat_hot.items():
        if items:
            theme_sections.append((tn, sorted(items, key=lambda x: x["score"], reverse=True)))
    
    hold_s, hold_r, hold_n = section("📦 庫存股監控", hold_items)
    bargain_s, bargain_r, bargain_n = section("💰 高EPS低股價潛力股", bargain_items)
    
    # 高EPS高分推薦
    top_eps = sorted([results[s] for s in FUNDAMENTAL if s in results], key=lambda x: x["info"]["eps"], reverse=True)[:8]
    
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>小龍蝦台股三合一選股</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'PingFang TC','Microsoft JhengHei',sans-serif; background:#F2F2F7; padding:12px; }}
.header {{ background:linear-gradient(135deg,#1A2B4C,#2E4A7D); color:#fff; border-radius:10px; padding:15px; margin-bottom:12px; text-align:center; }}
.header h1 {{ font-size:17px; }}
.header p {{ font-size:11px; opacity:0.8; }}
.news-bar {{ background:#fff; border-radius:10px; margin-bottom:12px; padding:10px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.news-item {{ padding:6px 0; border-bottom:1px solid #eee; font-size:12px; line-height:1.4; }}
.news-item.critical {{ background:#FFF0F0; margin:0 -10px; padding:6px 10px; border-left:3px solid #FF3B30; }}
.news-time {{ color:#8E8E93; font-size:10px; }}
.news-title {{ font-weight:500; }}
.tag-rel {{ display:inline-block; background:#E3F2FD; color:#1565C0; padding:1px 6px; border-radius:3px; font-size:10px; margin-top:2px; }}
.section {{ background:#fff; border-radius:10px; margin-bottom:10px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.section-title {{ background:#1A2B4C; color:#fff; padding:10px 12px; font-size:13px; font-weight:bold; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:#1A2B4C; color:#fff; padding:6px 4px; text-align:center; font-size:10px; }}
td {{ padding:8px 4px; text-align:center; border-bottom:1px solid #E5E5EA; }}
tr:nth-child(even) {{ background:#F8F9FA; }}
tr:hover {{ background:#E8F0FE; }}
.up {{ color:#FF3B30; }}
.down {{ color:#34C759; }}
.green {{ color:#34C759; }}
.red {{ color:#FF3B30; }}
small {{ font-size:11px; color:#555; }}
</style>
</head>
<body>

<div class="header">
    <h1>🦞 小龍蝦台股三合一選股</h1>
    <p>{datetime.now().strftime('%m/%d %H:%M')} | 📊 基本面+KD技術+資金流向</p>
</div>

<div class="news-bar">
    <div style="font-weight:bold;font-size:13px;margin-bottom:6px;">📡 鉅亨網即時新聞</div>
    {news_html}
</div>

<div class="section">
    <div class="section-title">🏆 高EPS績優股 TOP8</div>
    <table>
        <tr><th>股票</th><th>股價</th><th>EPS/PE</th><th>KD</th><th>區間</th><th>題材</th><th>訊號</th><th>評分</th></tr>
        {''.join(td(r) for r in top_eps)}
    </table>
</div>

<div class="section">
    <div class="section-title">{s_hot} ({n_hot}檔)</div>
    <table>
        <tr><th>股票</th><th>股價</th><th>EPS/PE</th><th>KD</th><th>區間</th><th>題材</th><th>訊號</th><th>評分</th></tr>
        {r_hot}
    </table>
</div>

<div class="section">
    <div class="section-title">{bargain_s} ({bargain_n}檔)</div>
    <table>
        <tr><th>股票</th><th>股價</th><th>EPS/PE</th><th>KD</th><th>區間</th><th>題材</th><th>訊號</th><th>評分</th></tr>
        {bargain_r}
    </table>
</div>

<div class="section">
    <div class="section-title">{hold_s} ({hold_n}檔)</div>
    <table>
        <tr><th>股票</th><th>股價</th><th>EPS/PE</th><th>KD</th><th>區間</th><th>題材</th><th>訊號</th><th>評分</th></tr>
        {hold_r}
    </table>
</div>
"""

    for tn, items in theme_sections:
        html += f"""<div class="section">
            <div class="section-title">{tn} ({len(items)}檔)</div>
            <table><tr><th>股票</th><th>股價</th><th>EPS/PE</th><th>KD</th><th>區間</th><th>題材</th><th>訊號</th><th>評分</th></tr>
            {''.join(td(r) for r in sorted(items, key=lambda x: x["score"], reverse=True))}
            </table></div>"""
    
    html += "</body></html>"
    
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "triple_engine_v2.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"\n✅ 報表已產生: {path}")
    print(f"  共分析 {len(results)} 檔股票")

if __name__ == "__main__":
    main()
