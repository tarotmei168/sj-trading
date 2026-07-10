"""
小龍蝦三合一選股引擎 v1
======================================
整合三大技能：
  1. mx-search 情報官 → 抓基本面資料(鉅亨網)
  2. mx-xuangu 波段主將 → 30分K KD技術面分析 + 三大門派分類
  3. mx-data 資金流向 → 產業題材分類 + 進出場建議

用法:
  python -X utf8 -m src.sj_trading.triple_engine
  python -X utf8 -m src.sj_trading.triple_engine --stock 3042 2337 6139
"""
import os, sys, json, time, argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np
import urllib.request
import re

# 抑制 numpy RuntimeWarning
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ============================================================
# 股票資料庫（含產業分類、EPS參考、股性）
# ============================================================
STOCK_DB = [
    # (代號, 名稱, 產業, 題材, 股性分類, 門派)
    # --- 庫存股 ---
    ("3042","晶技","石英元件","網通/車用/iPhone供應鏈","中型績優股","區間波段"),
    ("2337","旺宏","NOR Flash/記憶體","記憶體復甦/車用","景氣循環","籌碼大戶"),
    ("2436","偉詮電","IC設計","USB PD/消費性IC","中型IC設計","籌碼大戶"),
    ("5351","鈺創","利基型DRAM","AI邊緣運算/車用","小型主力","籌碼大戶"),
    ("3673","TPK-KY","觸控面板","摺疊手機/車用","景氣循環","區間波段"),
    ("3711","日月光投控","半導體封測","先進封裝/AI晶片","大型權值","區間波段"),
    ("4958","臻鼎-KY","PCB","AI伺服器/蘋果","大型權值","強勢動能"),
    ("8150","南茂","記憶體封測","記憶體復甦","中型景氣","區間波段"),
    # --- 觀察/熱門 ---
    ("2330","台積電","晶圓代工","AI晶片/先進製程","龍頭權值","區間波段"),
    ("2454","聯發科","IC設計","AI/旗艦手機晶片","大型權值","強勢動能"),
    ("2317","鴻海","EMS/伺服器","AI伺服器/電動車","超級權值","區間波段"),
    ("2303","聯電","晶圓代工","成熟製程","大型權值","區間波段"),
    ("3037","欣興","IC載板","ABF載板/AI","大型權值","強勢動能"),
    ("3189","景碩","IC載板","ABF載板","中型權值","強勢動能"),
    ("2344","華邦電","DRAM/NOR","記憶體/車用","景氣循環","籌碼大戶"),
    ("2327","國巨","被動元件","MLCC/車用","龍頭權值","區間波段"),
    ("6139","亞翔","無塵室工程","半導體擴廠/AI","中型成長","強勢動能"),
    # --- 設備股 ---
    ("3131","弘塑","半導體濕式設備","先進封裝/前段製程","高價小型績優","強勢動能"),
    ("3583","辛耘","半導體設備","AI/先進封裝","中型投信","強勢動能"),
    # --- 0050精選 ---
    ("2308","台達電","電源/電動車","AI伺服器電源","龍頭權值","區間波段"),
    ("2382","廣達","伺服器","AI伺服器","大型權值","強勢動能"),
    ("3231","緯創","AI伺服器","AI伺服器/組裝","大型權值","強勢動能"),
    ("8046","南電","IC載板","ABF載板","大型權值","強勢動能"),
    ("2603","長榮","貨櫃航運","運價反彈","景氣循環","區間波段"),
    ("2609","陽明","貨櫃航運","運價反彈","景氣循環","區間波段"),
    ("2610","華航","航空","客運復甦","景氣循環","區間波段"),
    ("2618","長榮航","航空","客運復甦","景氣循環","區間波段"),
    ("2881","富邦金","金控","金融","金融權值","區間波段"),
    ("2882","國泰金","金控","金融","金融權值","區間波段"),
    ("2892","第一金","銀行","金融","金融權值","區間波段"),
    ("6770","力積電","晶圓代工","成熟製程","中型","區間波段"),
    ("6284","佳邦","天線/保護元件","網通/車用","中小型","籌碼大戶"),
    ("6213","聯茂","銅箔基板","AI伺服器/高速材料","中型","強勢動能"),
    ("6271","同欣電","陶瓷基板","車用/光通訊","中型績優","強勢動能"),
    ("6451","訊芯-KY","SiP封裝","光通訊/CPO","中小型","籌碼大戶"),
    ("6173","信昌電","MLCC","被動元件","中小型","強勢動能"),
    ("5425","台半","二極體","車用","中型","區間波段"),
    ("3131","弘塑","半導體設備","先進封裝","小型績優","強勢動能"),
    ("6239","力成","IC封測","記憶體/邏輯","大型權值","區間波段"),
    ("1802","台玻","玻璃","建築/太陽能","景氣循環","區間波段"),
    ("4906","正文","網通設備","5G/WiFi7","中型","籌碼大戶"),
    ("6005","群益證","證券","股市熱絡","金融","區間波段"),
    ("1301","台塑","石化","塑化","傳統權值","區間波段"),
    ("1303","南亞","石化/電子材料","塑化/銅箔","傳統權值","區間波段"),
    ("2002","中鋼","鋼鐵","鋼價","傳統權值","區間波段"),
]

def get_stock_info(sid):
    for s in STOCK_DB:
        if s[0] == sid:
            return s
    return (sid, sid, "未分類", "無", "未知", "未知")

def get_all_sids():
    return list(set(s[0] for s in STOCK_DB))

# ============================================================
# 模塊A: mx-search 情報官 — 從鉅亨網抓基本面資料
# ============================================================
# ============================================================
# 模塊D: 即時新聞過濾器 (鉅亨網API)
# ============================================================
NEWS_API_URL = "https://news.cnyes.com/api/v3/news/category/tw_stock?limit=5"
MACRO_API_URL = "https://news.cnyes.com/api/v3/news/category/tw_macro?limit=5"

# 重大事件關鍵字過濾
CRITICAL_KEYWORDS = [
    "戰爭", "開戰", "衝突", "軍事", "制裁", "封鎖",
    "通膨", "CPI", "利率", "升息", "降息", "FOMC", "FED",
    "崩盤", "恐慌", "股災", "熔斷",
    "地震", "疫情", "封城",
    "倒閉", "破產", "擠兌",
    "稅改", "關稅", "貿易戰",
    "法說", "財報", "營收", "展望",
]

# 各股相關關鍵字
STOCK_KEYWORDS = {
    "3042": ["晶技", "TXC", "石英"],
    "2337": ["旺宏", "Macronix", "NOR Flash"],
    "2436": ["偉詮電", "Weltrend"],
    "5351": ["鈺創", "Etron"],
    "3711": ["日月光", "ASE"],
    "4958": ["臻鼎", "臻鼎-KY"],
    "8150": ["南茂", "ChipMOS"],
    "6139": ["亞翔", "L&K"],
    "2330": ["台積電", "TSMC"],
    "2454": ["聯發科", "MediaTek"],
    "2327": ["國巨", "Yageo"],
    "3131": ["弘塑", "GPTC"],
    "3583": ["辛耘", "Scientech"],
    "3037": ["欣興", "Unimicron"],
    "3189": ["景碩", "Kinsus"],
    "2344": ["華邦電", "Winbond"],
}

def fetch_latest_news():
    """從鉅亨網API抓即時新聞"""
    news_list = []
    
    for name, url in [("台股新聞", NEWS_API_URL), ("政經新聞", MACRO_API_URL)]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
            
            items = data.get("items", {}).get("data", [])
            for item in items:
                title = item.get("title", "")
                summary = item.get("summary", "")
                pub_time = item.get("publishAt", 0)
                news_id = item.get("newsId", 0)
                keywords = item.get("keyword", [])
                stocks = item.get("otherProduct", [])
                
                # 判斷是否重大事件
                is_critical = False
                critical_reason = []
                full_text = (title + " " + summary).lower()
                
                for kw in CRITICAL_KEYWORDS:
                    if kw.lower() in full_text:
                        is_critical = True
                        critical_reason.append(kw)
                
                # 判斷相關股票
                related_stocks = []
                for sp in stocks:
                    if sp.startswith("TWS:") and sp.endswith(":STOCK:COMMON"):
                        sid = sp.split(":")[1]
                        related_stocks.append(sid)
                
                # 也從標題內容判斷
                for sid, kws in STOCK_KEYWORDS.items():
                    for kw in kws:
                        if kw.lower() in full_text and sid not in related_stocks:
                            related_stocks.append(sid)
                
                news_list.append({
                    "title": title,
                    "summary": summary,
                    "time": datetime.fromtimestamp(pub_time).strftime("%m/%d %H:%M") if pub_time else "",
                    "url": f"https://news.cnyes.com/news/id/{news_id}" if news_id else "",
                    "is_critical": is_critical,
                    "critical_reason": critical_reason,
                    "keywords": keywords,
                    "related_stocks": related_stocks,
                    "source": name,
                })
        except:
            pass
    
    return news_list

def print_news_report(news_list):
    """輸出新聞報告"""
    lines = []
    
    # 過濾重大事件
    critical = [n for n in news_list if n["is_critical"]]
    normal = [n for n in news_list if not n["is_critical"]]
    
    if critical:
        lines.append(f"\n{'='*75}")
        lines.append(f"  🚨 重大事件警報! ({len(critical)}則)")
        lines.append(f"{'='*75}")
        for n in critical:
            lines.append(f"  [{n['time']}] {n['title']}")
            lines.append(f"  關鍵字: {', '.join(n['critical_reason'])}")
            if n["related_stocks"]:
                lines.append(f"  相關股: {', '.join(n['related_stocks'])}")
            lines.append(f"")
    
    if normal:
        lines.append(f"\n{'='*75}")
        lines.append(f"  📰 近期財經新聞")
        lines.append(f"{'='*75}")
        for n in normal[:5]:
            lines.append(f"  [{n['time']}] {n['title']}")
            if n["related_stocks"]:
                lines.append(f"    相關股: {n['related_stocks']}")
            lines.append(f"")
    
    return "\n".join(lines)


# 基本面資料庫（來自信譽良好來源：鉅亨網、公開資訊觀測站 2026/07 止）
FUNDAMENTAL_DB = {
    "3042": {"name":"晶技","eps":5.23,"pe":47.64,"pb":6.49,"gross_margin":32.33,"net_margin":13.50,"nav":38.33,"52w_high":249,"52w_low":79,"revenue_yoy":"+10~30%"},
    "2337": {"name":"旺宏","eps":-0.41,"pe":None,"pb":5.46,"gross_margin":40.80,"net_margin":17.00,"nav":26.07,"52w_high":192,"52w_low":18,"revenue_yoy":"轉虧"},
    "2436": {"name":"偉詮電","eps":3.47,"pe":21.85,"pb":3.86,"gross_margin":33.54,"net_margin":13.12,"nav":19.66,"52w_high":84.4,"52w_low":43,"revenue_yoy":"穩定"},
    "5351": {"name":"鈺創","eps":0.96,"pe":85.51,"pb":7.98,"gross_margin":36.65,"net_margin":21.74,"nav":10.25,"52w_high":103,"52w_low":25.3,"revenue_yoy":"轉盈"},
    "3673": {"name":"TPK-KY","eps":-5.31,"pe":None,"pb":0.64,"gross_margin":2.88,"net_margin":-4.33,"nav":55.61,"52w_high":53.7,"52w_low":25.35,"revenue_yoy":"虧損"},
    "3711": {"name":"日月光","eps":6.89,"pe":24.09,"pb":0.87,"gross_margin":16.20,"net_margin":7.28,"nav":191.26,"52w_high":682,"52w_low":129,"revenue_yoy":"+15%"},
    "4958": {"name":"臻鼎-KY","eps":9.62,"pe":49.11,"pb":2.49,"gross_margin":21.05,"net_margin":9.21,"nav":208.56,"52w_high":613,"52w_low":82,"revenue_yoy":"+20%"},
    "8150": {"name":"南茂","eps":1.19,"pe":88.24,"pb":3.07,"gross_margin":13.78,"net_margin":7.28,"nav":34.18,"52w_high":114,"52w_low":23.1,"revenue_yoy":"復甦"},
    "6139": {"name":"亞翔","eps":36.10,"pe":26.26,"pb":19.56,"gross_margin":18.73,"net_margin":14.67,"nav":48.46,"52w_high":987,"52w_low":293,"revenue_yoy":"+50%"},
    "2330": {"name":"台積電","eps":75.52,"pe":32.36,"pb":7.46,"gross_margin":52.25,"net_margin":38.83,"nav":327.88,"52w_high":2445,"52w_low":796,"revenue_yoy":"+35%"},
    "2454": {"name":"聯發科","eps":82.62,"pe":35.14,"pb":2.89,"gross_margin":48.67,"net_margin":18.48,"nav":998.44,"52w_high":5540,"52w_low":1055,"revenue_yoy":"+40%"},
    "2317": {"name":"鴻海","eps":18.58,"pe":12.82,"pb":1.58,"gross_margin":6.25,"net_margin":2.09,"nav":151.10,"52w_high":240,"52w_low":88.2,"revenue_yoy":"+12%"},
    "3037": {"name":"欣興","eps":7.54,"pe":137.63,"pb":4.95,"gross_margin":16.16,"net_margin":8.95,"nav":195.8,"52w_high":1460,"52w_low":116,"revenue_yoy":"+15%"},
    "3189": {"name":"景碩","eps":3.91,"pe":211.35,"pb":3.28,"gross_margin":25.51,"net_margin":10.72,"nav":254.23,"52w_high":1185,"52w_low":65,"revenue_yoy":"+25%"},
    "2344": {"name":"華邦電","eps":0.27,"pe":681.48,"pb":2.23,"gross_margin":18.42,"net_margin":1.05,"nav":82.59,"52w_high":184,"52w_low":16,"revenue_yoy":"微幅"},
    "2327": {"name":"國巨","eps":12.71,"pe":82.20,"pb":3.25,"gross_margin":38.10,"net_margin":21.06,"nav":321.19,"52w_high":1220,"52w_low":132.50,"revenue_yoy":"+10%"},
    "3131": {"name":"弘塑","eps":52.89,"pe":71.57,"pb":29.44,"gross_margin":33.78,"net_margin":28.87,"nav":128.54,"52w_high":4045,"52w_low":1320,"revenue_yoy":"+30%"},
    "3583": {"name":"辛耘","eps":14.76,"pe":57.67,"pb":17.13,"gross_margin":33.58,"net_margin":10.99,"nav":49.66,"52w_high":1010,"52w_low":298,"revenue_yoy":"+25%"},
    "2609": {"name":"陽明","eps":10.14,"pe":5.43,"pb":0.79,"gross_margin":35.14,"net_margin":24.13,"nav":68.74,"52w_high":72.5,"52w_low":9.81,"revenue_yoy":"運價波動"},
    "2618": {"name":"長榮航","eps":2.63,"pe":16.27,"pb":1.50,"gross_margin":15.18,"net_margin":8.83,"nav":29.56,"52w_high":44.5,"52w_low":30.55,"revenue_yoy":"+15%"},
    "2308": {"name":"台達電","eps":19.63,"pe":29.99,"pb":5.58,"gross_margin":28.60,"net_margin":10.64,"nav":161.43,"52w_high":2250,"52w_low":232,"revenue_yoy":"+20%"},
    "2382": {"name":"廣達","eps":12.21,"pe":16.67,"pb":4.90,"gross_margin":5.27,"net_margin":2.84,"nav":58.81,"52w_high":377,"52w_low":166,"revenue_yoy":"+30%"},
    "8046": {"name":"南電","eps":26.68,"pe":44.42,"pb":3.71,"gross_margin":22.83,"net_margin":15.30,"nav":319.19,"52w_high":1460,"52w_low":137,"revenue_yoy":"+25%"},
    "6770": {"name":"力積電","eps":0.42,"pe":172.38,"pb":1.13,"gross_margin":15.58,"net_margin":2.49,"nav":64.75,"52w_high":75,"52w_low":14.2,"revenue_yoy":"轉虧"},
    "3231": {"name":"緯創","eps":5.70,"pe":27.58,"pb":2.92,"gross_margin":7.60,"net_margin":2.64,"nav":53.96,"52w_high":159,"52w_low":77,"revenue_yoy":"+25%"},
    "2412": {"name":"中華電","eps":4.53,"pe":30.03,"pb":2.60,"gross_margin":56.07,"net_margin":17.33,"nav":54.19,"52w_high":143,"52w_low":119,"revenue_yoy":"持平"},
    "2881": {"name":"富邦金","eps":3.55,"pe":33.80,"pb":1.01,"gross_margin":None,"net_margin":28.75,"nav":119.49,"52w_high":121,"52w_low":65,"revenue_yoy":"穩定"},
    "2882": {"name":"國泰金","eps":3.99,"pe":23.56,"pb":1.12,"gross_margin":None,"net_margin":15.42,"nav":83.84,"52w_high":95,"52w_low":43,"revenue_yoy":"穩定"},
    "2303": {"name":"聯電","eps":3.72,"pe":45.70,"pb":2.02,"gross_margin":33.52,"net_margin":26.14,"nav":83.94,"52w_high":170,"52w_low":39,"revenue_yoy":"+10%"},
    "1301": {"name":"台塑","eps":1.41,"pe":34.04,"pb":1.03,"gross_margin":11.81,"net_margin":5.60,"nav":52.41,"52w_high":72,"52w_low":29,"revenue_yoy":"-15%"},
    "1303": {"name":"南亞","eps":9.34,"pe":16.06,"pb":0.97,"gross_margin":15.83,"net_margin":9.56,"nav":135.56,"52w_high":197,"52w_low":58,"revenue_yoy":"+10%"},
    "2002": {"name":"中鋼","eps":0.32,"pe":56.25,"pb":1.28,"gross_margin":6.96,"net_margin":1.53,"nav":15.32,"52w_high":25,"52w_low":17,"revenue_yoy":"持平"},
    "2603": {"name":"長榮","eps":21.21,"pe":8.91,"pb":0.88,"gross_margin":32.33,"net_margin":25.85,"nav":214.63,"52w_high":225,"52w_low":106,"revenue_yoy":"運價波動"},
    "2610": {"name":"華航","eps":1.60,"pe":14.38,"pb":1.46,"gross_margin":11.14,"net_margin":5.07,"nav":15.91,"52w_high":29,"52w_low":15,"revenue_yoy":"+15%"},
}

def fetch_fundamental(sid):
    """從內建資料庫取得基本面數據"""
    return FUNDAMENTAL_DB.get(sid)

# ============================================================
# 模塊A2: 基本面評分
# ============================================================
def score_fundamental(info, fundamental):
    """基本面評分 1-10"""
    if fundamental is None or fundamental.get("eps") is None:
        return 5, "資料不足，中等評分"
    
    eps = fundamental["eps"]
    pe = fundamental.get("pe")
    gross = fundamental.get("gross_margin")
    net = fundamental.get("net_margin")
    low52 = fundamental.get("52w_low")
    high52 = fundamental.get("52w_high")
    
    score = 5
    reasons = []
    
    # EPS評分
    if eps >= 30:
        score += 3
        reasons.append(f"EPS{eps}超強")
    elif eps >= 10:
        score += 2
        reasons.append(f"EPS{eps}優良")
    elif eps >= 3:
        score += 1
        reasons.append(f"EPS{eps}穩定")
    elif eps < 0:
        score -= 2
        reasons.append(f"EPS{eps}虧損")
    else:
        reasons.append(f"EPS{eps}普通")
    
    # 本益比評分
    if pe:
        if pe < 15:
            score += 1
            reasons.append("本益比低")
        elif pe > 80:
            score -= 1
            reasons.append("本益比偏高")
    
    # 毛利率評分
    if gross:
        if gross >= 50:
            score += 1
            reasons.append("高毛利")
        elif gross >= 30:
            score += 1
            reasons.append("毛利穩定")
        elif gross < 15:
            score -= 1
            reasons.append("低毛利")
    
    # 價格位置評分
    if low52 and high52 and high52 > low52:
        current = fundamental.get("market_cap", 0)
        pos = (info[4] == "景氣循環")  # 景氣循環股在低檔才安全
        reasons.append(f"區間{low52}~{high52}")
    
    return min(max(score, 1), 10), ", ".join(reasons)

# ============================================================
# 模塊B: mx-xuangu 波段主將 — 30分K KD分析
# ============================================================
def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_30k_data(api, sid, days=200):
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

def find_best_kd_params(df_30):
    """回測找最佳KD參數"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_vals = [20, 25, 30, 35, 40, 45, 50]
    sell_vals = [50, 55, 60, 65, 70, 75, 80]
    
    close = df_30["close"].values
    low = df_30["low"].values
    high = df_30["high"].values
    n = len(close)
    
    best = {"pnl": -99999, "k": 3, "buy": None, "sell": None, "trades": 0, "wins": 0}
    top5 = []
    
    for kp in k_range:
        k_arr = np.full(n, 50.0)
        d_arr = np.full(n, 50.0)
        k_arr, d_arr = compute_kd(k_arr, d_arr, close, low, high, kp)
        
        for bt in buy_vals + [None]:
            for st in sell_vals + [None]:
                position = 0; bp = 0; total = 0.0; t_cnt = 0; w_cnt = 0
                for i in range(kp + 1, n):
                    if position == 0 and k_arr[i-1] <= d_arr[i-1] and k_arr[i] > d_arr[i]:
                        if bt is None or k_arr[i] < bt:
                            position = 1; bp = close[i]; t_cnt += 1
                    elif position == 1 and k_arr[i-1] >= d_arr[i-1] and k_arr[i] < d_arr[i]:
                        if st is None or k_arr[i] > st:
                            position = 0
                            pnl = ((close[i] - bp) / bp) * 100
                            total += pnl
                            if pnl > 0: w_cnt += 1
                if position == 1:
                    pnl = ((close[-1] - bp) / bp) * 100
                    total += pnl
                    if pnl > 0: w_cnt += 1
                    t_cnt += 1
                
                total_r = round(total, 2)
                if total_r > best["pnl"] and t_cnt >= 2:
                    best = {"pnl": total_r, "k": kp, "buy": bt, "sell": st, "trades": t_cnt, "wins": w_cnt}
    
    return best

def analyze_current_kd(df_30, best):
    """分析當前KD狀態"""
    kp = best["k"]
    close = df_30["close"].values
    low = df_30["low"].values
    high = df_30["high"].values
    n = len(close)
    
    k_arr = np.full(n, 50.0)
    d_arr = np.full(n, 50.0)
    k_arr, d_arr = compute_kd(k_arr, d_arr, close, low, high, kp)
    
    last_price = close[-1]
    k_now = k_arr[-1]
    d_now = d_arr[-1]
    k_prev = k_arr[-2]
    d_prev = d_arr[-2]
    
    last_10 = []
    for i in range(min(10, n), 0, -1):
        last_10.append({
            "time": df_30.index[-i].strftime("%m/%d %H:%M"),
            "close": round(close[-i], 2),
            "k": round(k_arr[-i], 2),
            "d": round(d_arr[-i], 2),
        })
    
    # KD狀態
    golden_now = k_prev <= d_prev and k_now > d_now
    in_golden = k_now > d_now
    death_now = k_prev >= d_prev and k_now < d_now
    
    # 價格區間
    h60 = df_30["high"].tail(60).max()
    l60 = df_30["low"].tail(60).min()
    pos_pct = round((last_price - l60) / (h60 - l60) * 100, 0) if h60 > l60 else 50
    
    # 買入條件
    can_buy = False
    if golden_now and (best["buy"] is None or k_now < best["buy"]):
        can_buy = True
    
    # 價格判斷
    if k_now > 80:
        zone = "超高檔"
    elif k_now > 60:
        zone = "偏高檔"
    elif k_now > 40:
        zone = "中檔"
    elif k_now > 20:
        zone = "偏低檔"
    else:
        zone = "極低檔"
    
    return {
        "k": round(k_now, 2),
        "d": round(d_now, 2),
        "golden_now": golden_now,
        "in_golden": in_golden,
        "death_now": death_now,
        "can_buy": can_buy,
        "zone": zone,
        "price_pos": pos_pct,
        "high_60": round(h60, 2),
        "low_60": round(l60, 2),
        "last_price": round(last_price, 2),
        "last_10_bars": last_10,
    }

# ============================================================
# 模塊C: mx-data 資金流向過濾 + 三門派分類
# ============================================================
def analyze_stock_full(name, sid, info, fundamental, kd_status, best_params, category="觀察"):
    """完整分析一支股票"""
    db_info = get_stock_info(sid)
    industry = db_info[2]
    theme = db_info[3]
    stock_type = db_info[4]
    school = db_info[5]
    
    # 基本面評分
    base_score, base_reason = score_fundamental(info, fundamental)
    
    # 技術面評分
    tech_score = 5
    tech_reason = ""
    if kd_status:
        if kd_status["can_buy"]:
            tech_score = 8
            tech_reason = "金叉可進場"
        elif kd_status["golden_now"]:
            if best_params["buy"] and kd_status["k"] >= best_params["buy"]:
                tech_score = 6
                tech_reason = f"剛金叉但K={kd_status['k']}超過買門檻{best_params['buy']}"
            else:
                tech_score = 7
                tech_reason = "黃金交叉"
        elif kd_status["in_golden"]:
            if kd_status["k"] > 70:
                tech_score = 5
                tech_reason = "高檔金叉(等拉回)"
            elif kd_status["k"] > 50:
                tech_score = 6
                tech_reason = "中檔金叉(可買)"
            else:
                tech_score = 7
                tech_reason = "低檔金叉(適合進)"
        else:
            if kd_status["k"] < 30:
                tech_score = 6
                tech_reason = "極低檔死叉(等金叉)"
            else:
                tech_score = 4
                tech_reason = "死叉中"
    
    # 題材熱度評分
    theme_score = 5
    hot_themes = ["AI", "先進封裝", "半導體", "伺服器", "CPO", "車用"]
    theme_hotness = sum(1 for t in hot_themes if t in theme + industry)
    theme_score += theme_hotness
    if "龍頭" in stock_type or "權值" in stock_type:
        theme_score += 1
    
    # 綜合評分 (面面俱到)
    total = round((base_score * 0.35 + tech_score * 0.35 + theme_score * 0.3), 1)
    
    # 操作建議
    if total >= 7 and kd_status and kd_status["can_buy"]:
        action = "✅ 強烈建議買進"
    elif total >= 6.5 and kd_status and (kd_status["golden_now"] or (kd_status["in_golden"] and kd_status["k"] < 50)):
        action = "🟢 可以買進"
    elif total >= 6 and kd_status and kd_status["in_golden"]:
        action = "🟡 可觀察，等拉回"
    elif total >= 5 and kd_status and not kd_status["in_golden"] and kd_status["k"] < 30:
        action = "🔵 極低檔死叉，準備布局"
    elif total >= 5:
        action = "🔴 等待訊號"
    else:
        action = "⛔ 暫不考慮"
    
    return {
        "sid": sid, "name": name, "category": category,
        "industry": industry, "theme": theme, "stock_type": stock_type, "school": school,
        "fundamental": fundamental,
        "base_score": base_score, "base_reason": base_reason,
        "tech_score": tech_score, "tech_reason": tech_reason,
        "theme_score": theme_score,
        "total_score": total,
        "best_params": best_params,
        "kd": kd_status,
        "action": action,
    }

# ============================================================
# 主引擎
# ============================================================

def run_engine(stock_list=None, api=None):
    """執行完整分析引擎"""
    if stock_list is None:
        stock_list = get_all_sids()
    
    own_api = api is None
    if own_api:
        api = login()
    
    results = []
    
    for idx, sid in enumerate(stock_list):
        db_info = get_stock_info(sid)
        name = db_info[1]
        
        print(f"\n[{idx+1}/{len(stock_list)}] {name}({sid})", end="", flush=True)
        
        # 1. 抓基本面
        print(" 📊", end="", flush=True)
        fundamental = fetch_fundamental(sid)
        if fundamental:
            eps = fundamental.get("eps")
            pe = fundamental.get("pe")
            print(f" EPS={eps}", end="", flush=True)
        
        # 2. 抓技術面
        print(" 📈", end="", flush=True)
        try:
            df_30 = fetch_30k_data(api, sid, 200)
        except:
            df_30 = None
        
        if df_30 is None or len(df_30) < 20:
            print(" ❌ 無資料", flush=True)
            results.append(analyze_stock_full(name, sid, db_info, fundamental, None, {"pnl":0,"k":3,"buy":None,"sell":None,"trades":0,"wins":0}, "資料不足"))
            continue
        
        print(f" {len(df_30)}K", end="", flush=True)
        
        # 3. 找最佳KD參數
        t0 = time.time()
        best = find_best_kd_params(df_30)
        
        # 4. 分析當前KD
        kd_status = analyze_current_kd(df_30, best)
        elapsed = time.time() - t0
        
        bt_s = f"買<{best['buy']}" if best['buy'] else "買不限"
        st_s = f"賣>{best['sell']}" if best['sell'] else "賣不限"
        sr = round(best["wins"]/max(best["trades"],1)*100, 1)
        print(f" K={best['k']} {bt_s}{st_s}+{best['pnl']:.1f}%({best['trades']}筆{sr}%)", end="", flush=True)
        print(f" K={kd_status['k']} D={kd_status['d']}", flush=True)
        
        # 5. 完整分析
        result = analyze_stock_full(name, sid, db_info, fundamental, kd_status, best, "一般")
        results.append(result)
        
        time.sleep(0.3)
    
    if own_api:
        api.logout()
    
    return results

def print_report(results):
    """輸出完整報表"""
    # 依總分排序
    sorted_r = sorted(results, key=lambda r: r["total_score"], reverse=True)
    
    lines = []
    lines.append("=" * 75)
    lines.append(f"  小龍蝦三合一選股引擎 — 分析報告")
    lines.append(f"  時間: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    lines.append(f"  總計: {len(results)} 檔")
    lines.append("=" * 75)
    
    # 分類
    categories = {
        "✅ 強烈建議買進": [],
        "🟢 可以買進": [],
        "🟡 可觀察": [],
        "🔵 低檔布局": [],
        "🔴 等待": [],
        "⛔ 暫不考慮": [],
        "❌ 無資料": [],
    }
    
    for r in sorted_r:
        if r["action"] in categories:
            categories[r["action"]].append(r)
        else:
            categories["🔴 等待"].append(r)
    
    for cat_name, items in categories.items():
        if not items:
            continue
        lines.append(f"\n{'='*75}")
        lines.append(f"  {cat_name} ({len(items)}檔)")
        lines.append(f"{'='*75}")
        
        for r in items:
            bt = "買不限" if r["best_params"]["buy"] is None else f"買<{r['best_params']['buy']}"
            st = "賣不限" if r["best_params"]["sell"] is None else f"賣>{r['best_params']['sell']}"
            
            fnl = r["fundamental"]
            eps_str = f"EPS={fnl['eps']}" if fnl and fnl.get("eps") else "EPS=?"
            pe_str = f"PE={fnl['pe']}" if fnl and fnl.get("pe") else ""
            
            lines.append(f"")
            lines.append(f"  {r['name']}({r['sid']}) 總評:{r['total_score']}/10 {'⭐'*int(r['total_score']/2)}")
            lines.append(f"    產業: {r['industry']} | 題材: {r['theme']}")
            lines.append(f"    股性: {r['stock_type']} | 門派: {r['school']}")
            lines.append(f"    基本面: {eps_str} {pe_str} | 評分{r['base_score']}/10 | {r['base_reason']}")
            
            kd = r["kd"]
            if kd:
                lines.append(f"    KD: K={kd['k']} D={kd['d']} ({kd['zone']}) | 金叉={kd['golden_now']} 金叉中={kd['in_golden']}")
                lines.append(f"    價格: {kd['last_price']} | 60日區間: {kd['low_60']}~{kd['high_60']} (在{kd['price_pos']}%)")
                lines.append(f"    技術評分: {r['tech_score']}/10 | {r['tech_reason']}")
            
            lines.append(f"    KD策略: K={r['best_params']['k']} {bt} {st}")
            lines.append(f"    回測: +{r['best_params']['pnl']:.2f}% | {r['best_params']['trades']}筆")
            
            if kd and kd["can_buy"]:
                lines.append(f"    🚨 進場建議: 買{kd['last_price']}附近，停損-7%")
            elif kd and kd["golden_now"]:
                lines.append(f"    🔔 剛金叉! 建議: 在{kd['last_price']*0.97:.0f}~{kd['last_price']:.0f}區間進")
            elif kd and kd["in_golden"] and kd["k"] < 50:
                lines.append(f"    🔔 低檔金叉持續, 可掛{kd['last_price']*0.97:.0f}買")
            elif kd and not kd["in_golden"] and kd["k"] < 30:
                lines.append(f"    🔔 K={kd['k']}極低檔! 等金叉後進場")
            else:
                lines.append(f"    💤 等待訊號")
    
    # Top 5
    top5 = sorted_r[:5]
    lines.append(f"\n{'='*75}")
    lines.append(f"  🏆 Top 5 綜合推薦")
    lines.append(f"{'='*75}")
    for rank, r in enumerate(top5, 1):
        kd = r["kd"]
        k_str = f"K={kd['k']} D={kd['d']}" if kd else "無KD"
        lines.append(f"  #{rank} {r['name']}({r['sid']}) {r['total_score']}分 | {k_str} | {r['action']}")
    
    report = "\n".join(lines)
    print(f"\n\n{report}")
    return report


def main():
    parser = argparse.ArgumentParser(description="小龍蝦三合一選股引擎")
    parser.add_argument("--stock", nargs="*", help="指定股票代號，例如 3042 2337")
    parser.add_argument("--save", action="store_true", default=True, help="儲存報表")
    args = parser.parse_args()
    
    if args.stock:
        stock_list = [s for s in args.stock if s]
    else:
        stock_list = get_all_sids()
    
    print(f"\n{'='*75}")
    print(f"  🦞 小龍蝦三合一選股引擎 v1")
    print(f"  分析股票: {len(stock_list)} 檔")
    print(f"  mx-search(基本面) → mx-xuangu(KD技術) → mx-data(資金過濾)")
    print(f"{'='*75}")
    
    # 先抓新聞
    print(f"\n{'='*75}")
    print(f"  📡 正在掃描鉅亨網即時新聞...")
    print(f"{'='*75}")
    news_list = fetch_latest_news()
    news_report = print_news_report(news_list)
    if news_report:
        print(news_report)
    
    # 跑引擎
    results = run_engine(stock_list)
    report = print_report(results)
    
    # 合併報表
    report = news_report + "\n" + report
    
    # 儲存
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_path = os.path.join(base, "triple_engine_report.txt")
    json_path = os.path.join(base, "triple_engine_report.json")
    
    def clean(obj):
        if isinstance(obj, dict): return {k: clean(v) for k,v in obj.items()}
        elif isinstance(obj, list): return [clean(v) for v in obj]
        elif isinstance(obj, (np.integer,)): return int(obj)
        elif isinstance(obj, (np.floating,)): return float(obj)
        elif hasattr(obj, 'dtype') and obj.dtype == np.bool_: return bool(obj)
        elif isinstance(obj, (bool, type(None), str, int, float)): return obj
        return str(obj)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean(results), f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 報表已儲存:")
    print(f"  📄 {report_path}")
    print(f"  📊 {json_path}")


if __name__ == "__main__":
    main()
