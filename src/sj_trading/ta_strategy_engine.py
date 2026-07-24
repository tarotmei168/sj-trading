#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════╗
║  ta_strategy_engine.py  —  量化策略核心引擎  ║
║  0 Token 本地高速運算                         ║
║  資料: Shioaji 60天1分K → 30分K              ║
║  計算: TA-Lib STOCH / MACD / RSI            ║
║  輸出: today_signal.json + 早報 HTML         ║
╚═══════════════════════════════════════════════╝

執行流程:
  1. Shioaji 登入
  2. 爬 TWSE T86 投信買超排行（查昨天）
  3. 費半SOX + 台指期夜盤（yfinance）
  4. 美股收盤漲跌 + 台美產業聯動警報
  5. 鉅亨網新聞（台股/美股/科技/總經）
  6. 未來14天關鍵事件
  7. 下載 32 檔標的 60 天 1分K（分段14天）
  8. 合併 30分K，過濾台股交易時段 09:00~13:30
  9. TA-Lib 計算: STOCH() + MACD() + RSI()
  10. 輸出 today_signal.json + web/index.html + 根目錄 index.html
"""
import sys, os, json, re, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from calc_tech import calc_STOCH, calc_RSI, calc_MACD, calc_RSI_last

# ═══════════════════════════ 路徑 ═══════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
DB_DIR = os.path.join(BASE_DIR, 'database', '30min_60d')
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

sys.path.insert(0, SCRIPT_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))
from download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download

import shioaji as sj

# ═══════════════════════════ 股票清單 ═══════════════════════════
CORE_19 = [
    ('2436','偉詮電'), ('2337','旺宏'), ('5351','鈺創'),
    ('3673','TPK-KY'), ('3711','日月光'), ('4958','臻鼎-KY'),
    ('3042','晶技'), ('2454','聯發科'), ('2317','鴻海'),
    ('8150','南茂'), ('2330','台積電'), ('0050','元大台灣50'),
]
CORE_IDS = [s[0] for s in CORE_19]
CORE_NAMES = {s[0]: s[1] for s in CORE_19}

# KD 參數
KD_PARAMS = {
    "2436":5, "2337":21, "5351":14, "3673":14, "3711":21,
    "4958":21, "3042":14, "2454":21, "2317":14, "8150":21,
    "2330":9, "0050":9,
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 證交所 Session（連線重用，提高 T86 成功率）
_TWSE_SESSION = None
def _get_twse_session():
    global _TWSE_SESSION
    if _TWSE_SESSION is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.twse.com.tw/zh/page/trading/fund/T86.html",
            "X-Requested-With": "XMLHttpRequest",
        })
        _TWSE_SESSION = s
    return _TWSE_SESSION

# ═══════════════════════════ 星期對照 ═══════════════════════════
WEEKDAY_NAMES = ['一','二','三','四','五','六','日']

# ═══════════════════════════ 1. T86 投信買超 ═══════════════════════════
def fetch_trust_top20():
    """
    從 TWSE T86 爬投信買超排行前20名
    策略: 7/23 16:00 前查 7/22, 16:00 後查今天
    用 requests.Session + 完整 HTTP 標頭
    嘗試過去 5 個交易日, 每個日期重試 3 次
    回傳 [(代號, 名稱, 投信買超張數), ...]
    """
    print("🌐 爬取 TWSE T86 投信買超排行...")
    url = "https://www.twse.com.tw/fund/T86"
    stock_list = []
    session = _get_twse_session()
    now = datetime.now()

    # 7/23 16:00 前查昨天(7/22), 16:00後查今天(7/23)
    if now.hour < 16:
        target_date = now - timedelta(days=1)
    else:
        target_date = now
    # 跳過週末
    while target_date.weekday() >= 5:
        target_date -= timedelta(days=1)

    dates_to_try = []
    for i in range(5):
        d = target_date - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        dates_to_try.append(d.strftime("%Y%m%d"))

    print(f"  🎯 目標日期: {dates_to_try[0]}（今日{now.hour}時，{'盤後' if now.hour>=16 else '盤前'}查{'今天' if now.hour>=16 else '昨天'}）")

    for date_str in dates_to_try:
        for attempt in range(3):
            try:
                resp = session.get(url, params={"response": "json", "date": date_str, "selectType": "ALL"},
                                   timeout=20)
                if resp.status_code != 200:
                    time.sleep(2)
                    continue
                d = resp.json()
                if d.get("stat") != "OK" or not d.get("data"):
                    time.sleep(2)
                    continue
                for row in d["data"]:
                    code = row[0].strip()
                    name = row[1].strip()
                    if not re.match(r'^\d{4}$', code):
                        continue
                    # 欄位10 = 投信買賣超股數
                    try:
                        trust_net = int(row[10].replace(",", "")) if len(row) > 10 and row[10].strip() else 0
                    except:
                        trust_net = 0
                    if trust_net > 0:
                        stock_list.append((code, name, trust_net))
                if stock_list:
                    break
            except Exception as e:
                print(f"  ⚠️ T86 {date_str} 第{attempt+1}次失敗: {e}")
                time.sleep(2)
                continue
        if stock_list:
            print(f"  ✅ T86 {date_str} 成功: {len(stock_list)} 檔 (selectType=ALL)")
            break

    if not stock_list:
        print("⚠️ T86 連續 5 日無資料（非盤後時段或假日）")
        return []

    stock_list.sort(key=lambda x: x[2], reverse=True)
    stocks = stock_list[:20]
    print(f"✅ TWSE T86 投信買超前20名")
    for c, n, v in stocks:
        print(f"   {c:6s} {n}   買超 {v:,} 張")
    return stocks


# ═══════════════════════════ 2. 美股費半 + 台指期 ═══════════════════════════
def get_sox_index():
    """抓費城半導體 SOX 收盤"""
    try:
        import yfinance as yf
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            t = yf.Ticker("^SOX")
            df = t.history(period="5d")
        if df is not None and len(df) >= 2:
            closes = df["Close"].values
            change = (closes[-1] / closes[-2] - 1) * 100
            return {"close": round(closes[-1], 2), "change": round(change, 2)}
    except:
        pass
    return None

def get_taiwan_futures():
    """台指期夜盤 — yfinance"""
    try:
        import yfinance as yf
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            t = yf.Ticker('TX00.TW')
            df = t.history(period='3d', interval='1d')
        if df is not None and len(df) >= 2:
            closes = df['Close'].values
            close_val = round(float(closes[-1]), 2)
            change = round((closes[-1] / closes[-2] - 1) * 100, 2)
            return {"close": close_val, "change": change}
        df = t.history(period='2d', interval='1h')
        if df is not None and len(df) >= 2:
            closes = df['Close'].values
            close_val = round(float(closes[-1]), 2)
            change = round((closes[-1] / closes[-2] - 1) * 100, 2)
            return {"close": close_val, "change": change}
    except:
        pass
    return None


# ═══════════════════════════ 3. 台美產業聯動（架構表驅動）══════════════════════════=
def get_linkage_alerts():
    """
    從 us_tw_mapping_matrix LINKAGE_40 抓台美連動警報
    策略:
      - 以 us_sym 去重，合併多個產業群的台股清單
      - 美股波動≥2%才發警報
      - 顯示該美股連動的「所有」台股名稱（不限核心持股）
      - 但只優先列出在核心持股內的名稱，其餘標示產業群
    """
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, "src", "sj_trading"))
        from us_tw_mapping_matrix import LINKAGE_40
    except:
        return []

    # 合併：us_sym -> {name, groups:[], all_tw:{code:name}}
    us_map = {}
    for gid, info in LINKAGE_40.items():
        for us_sym, us_name in info["us"]:
            sym = us_sym.upper()
            if sym not in us_map:
                us_map[sym] = {"name": us_name, "groups": [], "all_tw": {}}
            us_map[sym]["groups"].append(info.get("sector", ""))
            for c, n in info["tw"]:
                us_map[sym]["all_tw"][c] = n

    alerts = []
    seen_symbols = set()  # 避免同一美股代號重複抓 yfinance
    for us_sym, meta in us_map.items():
        if us_sym in seen_symbols:
            continue
        seen_symbols.add(us_sym)
        try:
            import yfinance as yf
            import io, contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                t = yf.Ticker(us_sym)
                df = t.history(period="5d")
            if df is not None and len(df) >= 2:
                closes = df["Close"].values
                change = (closes[-1] / closes[-2] - 1) * 100
                close = round(closes[-1], 2)
                if abs(change) >= 2:
                    # 找出核心持股內的台股
                    matched_core = {c: n for c, n in meta["all_tw"].items() if c in CORE_NAMES}
                    # 找出潛力股內的台股
                    matched_pot = {c: n for c, n in meta["all_tw"].items() if c not in CORE_NAMES}
                    sector_str = "/".join(list(dict.fromkeys(meta["groups"]))[:2])
                    direction = "暴漲" if change > 0 else "暴跌"
                    level = "🔴🔴" if abs(change) >= 4 else "🔴"
                    alerts.append({
                        "symbol": us_sym,
                        "name": meta["name"],
                        "change": round(change, 2),
                        "close": close,
                        "level": level,
                        "direction": direction,
                        "sector": sector_str,
                        "tw_core": [f"{n}({c})" for c, n in sorted(matched_core.items())],
                        "tw_others": [n for c, n in sorted(matched_pot.items())][:3],
                    })
        except:
            continue

    alerts.sort(key=lambda x: abs(x["change"]), reverse=True)
    return alerts


# ═══════════════════════════ 4. 未來14天關鍵事件 ═══════════════════════════
KNOWN_EVENTS_2026 = {
    "2026-07-10": [("除權息", "2317鴻海除息4.0元", "🔥重要")],
    "2026-07-15": [("台指期", "台指期月結算大震盪日", "🔥🔥重要")],
    "2026-07-16": [("總經", "🇺🇸 美國6月CPI消費者物價指數", "🔥🔥🔥關鍵")],
    "2026-07-17": [("總經", "🇺🇸 美國6月PPI", "重要")],
    "2026-07-20": [("法說", "🔥 2330台積電法說會（Q2財報+Q3展望）", "🔥🔥🔥關鍵")],
    "2026-07-21": [("法說", "🔥 2454聯發科法說會", "🔥重要")],
    "2026-07-22": [("法說", "2317鴻海法說會", "重要")],
    "2026-07-23": [("法說", "1301台塑法說會｜2308台達電法說會", "重要")],
    "2026-07-27": [("除權息", "🔥🔥🔥 2330台積電除息3.5元（加權蒸發28點）", "🔥🔥🔥關鍵")],
    "2026-07-28": [("總經", "🔥🔥🔥 FOMC利率決策會議（7/28~7/29）", "🔥🔥🔥關鍵"),
                   ("投信", "投信季底作帳最後一週", "🔥重要")],
    "2026-07-29": [("總經", "🔥🔥🔥 FOMC利率公佈", "🔥🔥🔥關鍵")],
    "2026-07-30": [("總經", "🇺🇸 美國Q2 GDP初值", "🔥🔥重要"),
                   ("投信", "投信季底結帳倒數2天", "🔥重要")],
    "2026-07-31": [("投信", "🔥🔥🔥 投信季底結帳日", "🔥🔥🔥關鍵"),
                   ("總經", "🇺🇸 美國6月PCE核心通膨", "🔥🔥🔥關鍵")],
    "2026-08-05": [("總經", "🇺🇸 美國7月ISM服務業PMI", "🔥重要")],
    "2026-08-07": [("總經", "🔥🔥🔥 美國7月非農就業+失業率", "🔥🔥🔥關鍵")],
    "2026-08-10": [("財報", "📅 全市場7月營收公告截止", "🔥重要")],
    "2026-08-13": [("總經", "🔥🔥🔥 美國7月CPI", "🔥🔥🔥關鍵")],
    "2026-08-20": [("總經", "FOMC 7月會議紀要公布", "注意")],
    "2026-08-27": [("總經", "🔥 傑克森霍爾全球央行年會（鮑爾談話）", "🔥重要")],
    "2026-09-16": [("總經", "🔥🔥🔥🔥 FOMC利率決策（含點陣圖）", "🔥🔥🔥🔥關鍵")],
    "2026-09-30": [("投信", "🔥🔥🔥 投信Q3季底結帳最後交易日", "🔥🔥🔥關鍵")],
}

def get_quadruple_witching(year, month):
    """回傳該月第3個星期五的日期，僅對 3/6/9/12 月有效"""
    if month not in (3, 6, 9, 12):
        return None
    first_day = datetime(year, month, 1)
    days_ahead = 4 - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_fri = first_day + timedelta(days=days_ahead)
    third_fri = first_fri + timedelta(weeks=2)
    return third_fri

def get_events():
    """未來14天事件"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today + timedelta(days=14)
    events = []

    # 從已知事件表
    for date_str, event_list in KNOWN_EVENTS_2026.items():
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if today <= d <= cutoff:
            for etype, name, impact in event_list:
                events.append({"date": date_str, "days": (d - today).days, "type": etype, "name": name, "impact": impact})

    # 四巫日
    for m in (3, 6, 9, 12):
        qw = get_quadruple_witching(today.year, m)
        if qw and today <= qw <= cutoff:
            # 標示為台指期月結算
            is_dup = False
            for e in events:
                if "月結算" in e["name"] and e["date"] == qw.strftime("%Y-%m-%d"):
                    is_dup = True
                    break
            if not is_dup:
                events.append({"date": qw.strftime("%Y-%m-%d"), "days": (qw - today).days,
                               "type": "台指期", "name": "美股四巫日（結算日）波動加劇", "impact": "🔥🔥重要"})

    events.sort(key=lambda x: x["days"])
    return events


# ═══════════════════════════ 5. 新聞引擎 ═══════════════════════════
# 中國新聞過濾
CHINA_FILTER = ['中國', '北京', '上海', '深圳', '港股', 'A股', '陸股', '滬指', '深指',
                '中概', '人民幣', '習近平', '長鑫', '長江存儲', '華為', '中芯',
                '茅台', '恆生', '上證']

def should_filter_out(title):
    for kw in CHINA_FILTER:
        if kw in title:
            return True
    return False

KEYWORD_RULES = [
    (['漲價', '調漲', '漲價效應'], '⭐漲價'),
    (['缺料', '缺貨', '供不應求', '產能吃緊'], '⭐缺貨'),
    (['營收創高', '營收新高', '創新高', '歷史新高', '同期新高'], '⭐營收創高'),
    (['EPS', '每股盈餘'], '⭐EPS'),
    (['股利', '股息', '殖利率', '現金股利'], '⭐股利'),
    (['三率三升', '毛利率', '營益率', '淨利率'], '⭐三率三升'),
    (['訂單能見度', '訂單滿載', '接單', '滿手訂單'], '⭐訂單'),
    (['虧轉盈', '轉虧為盈', '轉機', '虧損縮小'], '⭐轉機'),
    (['擴產', '擴廠', '新產能', '量產'], '⭐擴產'),
    (['川普', '特朗普', 'trump', 'Trump'], '🔴政治'),
    (['關稅', 'tariff', '關稅壁壘'], '🔴關稅'),
    (['制裁', '封鎖', '禁令', 'ban'], '🔴制裁'),
    (['聯準會', 'Fed', '鮑爾', 'Powell', '升息', '降息'], '🔴FED'),
    (['記憶體', 'DRAM', 'NAND', 'SK海力士', '美光', '長約'], '🔴記憶體'),
    (['晶片', 'chip', '半導體', '台積電', 'TSMC'], '🟠半導體'),
    (['AI', '人工智能', '人工智慧'], '🟠AI'),
    (['法說', '法說會'], '🟠法說'),
    (['營收', '財報'], '🟠財報'),
    (['除息', '除權'], '🟠除息'),
    (['外銷訂單', '出口創高', '出口年增'], '🟠出口/外銷'),
]

def tag_title(title):
    tags = []
    for keywords, tag in KEYWORD_RULES:
        for kw in keywords:
            if kw in title:
                tags.append(tag)
                break
    return tags

def fetch_news_category(cat_id, limit=10):
    """鉅亨網 API 抓新聞"""
    url = f'https://news.cnyes.com/api/v3/news/category/{cat_id}?limit={limit}&page=1'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', {}).get('data', [])
        result = []
        for item in items:
            title = item.get('title', '').strip()
            if not title or should_filter_out(title):
                continue
            result.append({
                'title': title[:80],
                'date': str(item.get('publishedAt', ''))[:10],
                'tags': tag_title(title),
            })
        return result
    except:
        return []

def get_all_news():
    """抓所有分類新聞"""
    print("📰 鉅亨網新聞...")
    categories = [
        ('us_stock', '🇺🇸 美股/國際'),
        ('tw_stock', '📊 台股重點'),
        ('tech',     '🔬 科技脈動'),
        ('tw_macro', '🇹🇼 台灣總經'),
    ]
    all_news = {}
    total = 0
    for cat_id, cat_label in categories:
        news = fetch_news_category(cat_id, 10)
        all_news[cat_id] = {'label': cat_label, 'items': news}
        tagged = sum(1 for n in news if n['tags'])
        total += len(news)
        print(f'  {cat_label}: {len(news)} 則 (含關鍵字{tagged})')
    return {'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'), 'categories': all_news}


# ═══════════════════════════ 6. Shioaji 登入 + 資料下載 ═══════════════════════════
def login_shioaji():
    return _shioaji_login()

def download_60d_1min(api, sid):
    return _shioaji_download(api, sid, lookback_days=60, seg_days=30)

def merge_30min(df):
    """1分K -> 30分K，過濾台股交易時段 09:00~13:30"""
    if df is None or df.empty:
        return None
    d = df.set_index("datetime")
    o = pd.DataFrame({"open": d["open"].resample("30min").first()})
    o["high"] = d["high"].resample("30min").max()
    o["low"] = d["low"].resample("30min").min()
    o["close"] = d["close"].resample("30min").last()
    o["volume"] = d["volume"].resample("30min").sum()
    o = o.dropna().reset_index()
    o["h"] = o["datetime"].dt.hour
    o["m"] = o["datetime"].dt.minute
    o = o[((o["h"] == 9) & (o["m"] >= 0)) |
          ((o["h"] >= 10) & (o["h"] <= 12)) |
          ((o["h"] == 13) & (o["m"] <= 30))]
    o = o.drop(columns=["h", "m"]).reset_index(drop=True)
    if len(o) < 25:
        return None
    return o

def calc_talib(sid, df30):
    """
    TA-Lib 全指標計算:
      - STOCH → KD
      - MACD → MACD + MACD_hist
      - RSI → RSI
    數據防呆:
      - K>50 絕不判定低檔金叉
      - K>80 強制標示高檔過熱
    """
    close = np.array(df30["close"], dtype=float)
    high = np.array(df30["high"], dtype=float)
    low = np.array(df30["low"], dtype=float)
    vol = np.array(df30["volume"], dtype=float)

    k_arr, d_arr = calc_STOCH(high, low, close)
    k_last = float(k_arr[-1]) if not np.isnan(k_arr[-1]) else 50.0
    d_last = float(d_arr[-1]) if not np.isnan(d_arr[-1]) else 50.0
    k_prev = float(k_arr[-2]) if len(k_arr) >= 2 and not np.isnan(k_arr[-2]) else k_last
    gap = k_last - d_last
    golden = k_last >= d_last
    k_trend_up = k_last > k_prev
    k5 = [float(k_arr[i]) if not np.isnan(k_arr[i]) else 50 for i in range(-5, 0)]
    d5 = [float(d_arr[i]) if not np.isnan(d_arr[i]) else 50 for i in range(-5, 0)]

    macd_arr, sig_arr, hist_arr = calc_MACD(close)
    h_last = float(hist_arr[-1]) if not np.isnan(hist_arr[-1]) else 0
    h5 = [float(hist_arr[i]) if not np.isnan(hist_arr[i]) else 0 for i in range(-5, 0)]
    h_prev = h5[-2] if len(h5) >= 2 else h_last
    max_abs = max([abs(x) for x in h5] + [0.1])
    svg_bars = _macd_sparkline(h5, max_abs)
    direction = "擴大" if abs(h_last) > abs(h_prev) else "縮小"
    flip_warn = ""
    if len(h5) >= 3 and h_last < 0:
        all_shrinking = all(abs(h5[i]) >= abs(h5[i+1]) for i in range(len(h5)-1))
        if all_shrinking and h_last > -1.0:
            flip_warn = '🔥翻紅'
    macd_s = f"{svg_bars}<span style=\"font-size:17px;font-weight:bold;\">Hist:{h_last:.1f}</span><br><span style=\"font-size:14px;color:var(--text-muted)\">{direction}{' | '+flip_warn if flip_warn else ''}</span>"

    rsi_val = calc_RSI_last(close)
    low_30d = round(float(np.min(low[-30:])), 1) if len(low) >= 30 else None

    v5 = float(np.mean(vol[-5:]))
    v20 = float(np.mean(vol[-20:-5])) if len(vol) >= 25 else v5
    vr = v5 / v20 if v20 > 0 else 1.0
    vol_note = "放量🟢" if vr > 1.5 else ("量縮🔴" if vr < 0.8 else "平量⚪")

    px = round(close[-1], 1)
    chg = 0
    chg_pct = 0.0
    if len(close) >= 2:
        chg = round(px - close[-2], 2)
        chg_pct = round(((px / close[-2]) - 1) * 100, 2)
    if chg > 0:
        chg_s = f'▲ {abs(chg):.2f} (+{chg_pct:.2f}%)'
    elif chg < 0:
        chg_s = f'▼ {abs(chg):.2f} ({chg_pct:.2f}%)'
    else:
        chg_s = '▸ 0.00 (0.00%)'

    # 防呆
    k_threshold = 30
    low_golden = False
    high_overheat = False
    if k_last > 80 and golden:
        high_overheat = True
    elif golden and gap < 5 and k_last < k_threshold and k_trend_up:
        low_golden = True

    kd_svg = _kd_sparkline(k5, d5)
    if low_golden:
        kd_label = f"🏹 低檔金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif high_overheat:
        kd_label = f"⚠️ 高檔過熱 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif golden and gap < 3:
        kd_label = f"🟡 逼近金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif golden:
        kd_label = f"🟢 金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif not golden and gap > -3:
        kd_label = f"🟡 逼近死叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    else:
        kd_label = f"🔴 死叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    kd_s = f"{kd_svg}<br><span style=\"font-size:15px;\">{kd_label}</span>"

    if low_golden and rsi_val < 40:
        strategy = "🟢🟢 低檔金叉進場"
    elif low_golden:
        strategy = "🟢 低檔金叉留意"
    elif high_overheat:
        strategy = "⚠️ 高檔勿追"
    elif golden and rsi_val < 50:
        strategy = "🟡 金叉觀察"
    elif not golden and gap < -3:
        strategy = "🔴 死叉避開"
    elif rsi_val > 70:
        strategy = "⚠️ 過熱"
    elif rsi_val < 30 and golden:
        strategy = "🟢 超賣金叉"
    else:
        strategy = "➖ 觀望"

    return {
        "sid": sid, "price": px, "chg": chg, "chg_pct": chg_pct, "chg_s": chg_s,
        "k": round(k_last, 1), "d": round(d_last, 1), "gap": round(gap, 1),
        "golden": golden, "k_trend_up": k_trend_up,
        "low_golden": low_golden, "high_overheat": high_overheat,
        "kd_s": kd_s, "macd_s": macd_s, "rsi": rsi_val,
        "low_30d": low_30d, "vol_note": vol_note, "strategy": strategy,
        "latest_ts": str(df30["ts"].iloc[-1]) if "ts" in df30.columns else "—",
    }

def _kd_sparkline(k5, d5):
    svg_w = 200
    svg_h = 80
    pad = 5
    plot_w = svg_w - pad * 2
    plot_h = svg_h - pad * 2
    all_v = k5 + d5
    min_v = min(all_v) if all_v else 0
    max_v = max(all_v) if all_v else 100
    rng = max_v - min_v if max_v > min_v else 50
    def ypos(v):
        return pad + plot_h - ((v - min_v) / rng) * plot_h
    pts_k = []
    pts_d = []
    for i in range(5):
        x = pad + (plot_w / 4) * i
        pts_k.append(f"{x:.1f},{ypos(k5[i]):.1f}")
        pts_d.append(f"{x:.1f},{ypos(d5[i]):.1f}")
    return (
        f'<svg width="{svg_w}" height="{svg_h}" style="display:inline-block;vertical-align:middle;margin-right:6px;">'
        f'<polyline points="{" ".join(pts_k)}" fill="none" stroke="#4a9eff" stroke-width="2.5" stroke-linejoin="round" />'
        f'<polyline points="{" ".join(pts_d)}" fill="none" stroke="#ffa94d" stroke-width="2.5" stroke-linejoin="round" />'
        f'</svg>'
    )

def _macd_sparkline(h5, max_abs):
    bar_w = 28
    gap = 5
    svg_w = len(h5) * (bar_w + gap) + 8
    svg_h = 80
    zero_y = svg_h / 2
    scale = zero_y / max_abs * 0.85
    bars = []
    for i, v in enumerate(h5):
        x = i * (bar_w + gap) + 4
        h = abs(v) * scale
        if h < 2:
            h = 2
        if v >= 0:
            y = zero_y - h
            color = "#ff6b6b"
        else:
            y = zero_y
            color = "#2ed573"
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="2" />')
    line = f'<line x1="0" y1="{zero_y}" x2="{svg_w}" y2="{zero_y}" stroke="#555" stroke-width="1.5" />'
    return f'<svg width="{svg_w}" height="{svg_h}" style="display:inline-block;vertical-align:middle;margin-right:8px;overflow:visible;">{line}{"".join(bars)}</svg>'


# ═══════════════════════════ 7. 大盤20日線檢查 ═══════════════════════════
def check_market_below_20ma():
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        resp = requests.get(url, params={
            "dataset": "TaiwanStockPrice", "data_id": "TAIEX",
            "start_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
        }, timeout=10)
        d = resp.json()
        if d.get("status") != 200 or not d.get("data"):
            resp = requests.get(url, params={
                "dataset": "TaiwanStockPrice", "data_id": "0050",
                "start_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d"),
            }, timeout=10)
            d = resp.json()
        if d.get("status") != 200 or not d.get("data"):
            return False
        items = d["data"]
        closes = np.array([r["close"] for r in items], dtype=float)
        if len(closes) < 25:
            return False
        last = closes[-1]
        ma20 = np.mean(closes[-20:])
        if last < ma20:
            print(f"📉 大盤跌破20日線 ({last:.0f}<{ma20:.0f}) → 嚴格模式 K<30")
            return True
        print(f"📈 大盤站上20日線 ({last:.0f}>={ma20:.0f}) → 正常模式 K<35")
        return False
    except:
        return False


# ═══════════════════════════ 8. 批次處理 ═══════════════════════════
def analyze_stocks(api, stock_ids, strict_mode):
    kth = 30 if strict_mode else 35
    results = {}
    print(f"\n?? 60天30分K + TA-Lib {len(stock_ids)} 檔 (K<{kth} 低檔金叉)")
    for sid in stock_ids:
        name = CORE_NAMES.get(sid, sid)
        print(f"\n  {sid} {name} 下載 60天1分K...")
        df1 = download_60d_1min(api, sid)
        if df1 is None:
            print("  ?? 無資料")
            continue
        df30 = merge_30min(df1)
        if df30 is None:
            print("  ?? 30分K合併失敗")
            continue
        print(f"  -> {len(df30)}根30分K | last={str(df30.iloc[-1]["datetime"])[:19]} close={df30.iloc[-1]["close"]}")
        t = calc_talib(sid, df30)
        if t:
            t["name"] = name
            results[sid] = t
            print(f"     K:{t['k']:.1f}/D:{t['d']:.1f} RSI:{t['rsi']} MACD_hist:{t.get('macd_hist',0):.1f} | {t['strategy']}")
    return results

def save_signal_json(results):
    signals = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "stocks": {}
    }
    for sid, t in results.items():
        signals["stocks"][sid] = {
            "name": t.get("name", sid), "price": t["price"],
            "chg": t["chg"], "chg_pct": t["chg_pct"],
            "k": t["k"], "d": t["d"],
            "golden": t["golden"], "low_golden": t["low_golden"],
            "high_overheat": t["high_overheat"],
            "rsi": t["rsi"], "low_30d": t["low_30d"],
            "strategy": t["strategy"],
        }
    path = os.path.join(OUTPUT_DIR, "today_signal.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    print(f"\n📄 today_signal.json ({len(results)} 檔)")


# ═══════════════════════════ 9. HTML 輸出 ═══════════════════════════
def generate_html(core, pot, fubon_stocks, strict_mode, sox, txf, linkage_alerts, events, news_data):
    from datetime import datetime
    kth = 30 if strict_mode else 35
    mn = "📉 跌破20日線｜K<30" if strict_mode else "📈 站穩20日線｜K<35"
    td = datetime.now().strftime("%Y-%m-%d")
    nh = datetime.now().strftime("%H:%M")
    wd = WEEKDAY_NAMES[datetime.now().weekday()]

    # ── 美股費半區塊 ──
    sox_html = ""
    if sox:
        arrow = "🔺" if sox["change"] > 0 else "🔻" if sox["change"] < 0 else "➖"
        sox_icon = "🔥" if sox["change"] > 2 else ("⚠️" if sox["change"] < -2 else "➖")
        sox_html = f'''<div class="card info"><div class="card-title">🇺🇸 費城半導體（SOX）</div>
<div style="font-size:22px;font-weight:bold;text-align:center;">
  {sox["close"]:.0f} {arrow} {sox["change"]:+.2f}%
</div>
<div style="font-size:15px;text-align:center;color:var(--text-muted);">
  {sox_icon} 費半波動{abs(sox["change"]):.1f}% → {'🔥 直接影響台股半導體族群開盤' if abs(sox['change']) > 1.5 else '正常波動'}
</div></div>'''

    # ── 台指期夜盤 ──
    txf_html = ""
    if txf:
        arrow = "🔺" if txf["change"] > 0 else "🔻" if txf["change"] < 0 else "➖"
        hint = ""
        if txf["change"] > 0.5:
            hint = "夜盤上漲 → 今日台股有望跳空開高 ✅"
        elif txf["change"] < -0.5:
            hint = "夜盤下跌 → 今日台股可能開低洗盤 ⚠️"
        else:
            hint = "夜盤平穩 → 今日正常開盤 ➖"
        txf_html = f'''<div class="card" style="border-left-color: #00bcd4;"><div class="card-title">🇹🇼 台指期夜盤</div>
<div style="font-size:22px;font-weight:bold;text-align:center;">
  {txf["close"]:.0f} {arrow} {txf["change"]:+.2f}%
</div>
<div style="font-size:15px;text-align:center;color:var(--text-muted);">{hint}</div></div>'''

    # ── 台美聯動警報 ──
    linkage_html = ""
    if linkage_alerts:
        links = "".join(
            f'<div style="padding:3px 0;font-size:16px;">{a["level"]} {a["name"]} {a["direction"]} {a["change"]:+.2f}% — '
            f'<span style="color:var(--primary-gold);">{", ".join(a["tw_core"][:4]) if a["tw_core"] else a["sector"]}</span></div>'
            for a in linkage_alerts
        )
        linkage_html = f'<div class="card alert"><div class="card-title">🔗 台美產業聯動警報（美股波動≥2%）</div>{links}</div>'

    # ── 未來14天事件 ──
    events_html = ""
    if events:
        evs = "".join(
            f'<div style="padding:3px 0;font-size:16px;"><span style="color:var(--primary-gold);">{e["date"]}</span> {"今天" if e["days"]==0 else "明天" if e["days"]==1 else f"{e["days"]}天後"} | {e["name"]}</div>'
            for e in events[:12]
        )
        events_html = f'<div class="card" style="border-left-color: #9b59b6;"><div class="card-title">📅 未來14天關鍵事件</div>{evs}</div>'

    # ── 新聞 ──
    news_html = ""
    cats = news_data.get('categories', {})

    # 國際政治/總經重點
    political = []
    for cid in ['us_stock', 'tw_macro']:
        if cid in cats:
            political.extend((n, cid) for n in cats[cid]['items'] if n['tags'])
    if political:
        seen = set()
        html = '<div class="card alert"><div class="card-title">🌍 國際政治 × 總經大事</div>'
        count = 0
        for n, cid in political:
            key = n['title'][:20]
            if key not in seen:
                seen.add(key)
                tags = ' '.join(f'<span class="badge badge-red">{t}</span>' for t in n['tags'][:3])
                html += f'<div class="news-item">{tags} {n["title"]}</div>'
                count += 1
                if count >= 6:
                    break
        html += '</div>'
        news_html += html

    # 股價催化劑
    catalyst = []
    for cid in ['tw_stock', 'tech', 'tw_macro']:
        if cid in cats:
            catalyst.extend(n for n in cats[cid]['items'] if any(t.startswith('⭐') for t in n['tags']))
    if catalyst:
        seen = set()
        html = '<div class="card" style="border-left-color: #ffa502;"><div class="card-title">🔥 股價催化劑（漲價/缺料/營收創高/轉機）</div>'
        for n in catalyst[:6]:
            key = n['title'][:20]
            if key not in seen:
                seen.add(key)
                tags = ' '.join(f'<span class="badge badge-red">{t}</span>' for t in n['tags'][:3])
                html += f'<div class="news-item">{tags} {n["title"]}</div>'
        html += '</div>'
        news_html += html

    # 台股重點
    if 'tw_stock' in cats and cats['tw_stock']['items']:
        html = '<div class="card"><div class="card-title">📊 台股重點</div>'
        for n in cats['tw_stock']['items'][:5]:
            tags = ' '.join(f'<span class="badge badge-blue">{t}</span>' for t in n['tags'][:2])
            html += f'<div class="news-item">{tags} {n["title"]}</div>'
        html += '</div>'
        news_html += html

    # 科技新聞
    if 'tech' in cats and cats['tech']['items']:
        html = '<div class="card info"><div class="card-title">🔬 科技產業</div>'
        for n in cats['tech']['items'][:4]:
            tags = ' '.join(f'<span class="badge badge-blue">{t}</span>' for t in n['tags'][:2])
            html += f'<div class="news-item">{tags} {n["title"]}</div>'
        html += '</div>'
        news_html += html

    # ── 核心持股表格 ──
    cr = "".join(_row(s, n, core.get(s)) for s, n in CORE_19 if core.get(s))
    if not cr:
        cr = '<tr><td colspan="7" style="text-align:center;color:#666;">⏳ 讀取中</td></tr>'

    # ── 潛力股表格 ──
    pr = "".join(_pot_row(s[0], s[1], pot.get(s[0]), s[2] if len(s) >= 3 else 0) for s in fubon_stocks if s[0] not in CORE_IDS and pot.get(s[0]))
    if not pr:
        pr = '<tr><td colspan="8" style="text-align:center;color:#666;">⚠️ 無資料（盤後16:00後 T86 才更新）</td></tr>'

    # ── 買進訊號 ──
    buys = [(s, t) for s, t in sorted({**core, **pot}.items()) if t and t.get("low_golden")]
    ah = "".join(f'<div class="buy-signal">🔔 {t["name"]}({s}) K:{t["k"]:.0f}/D:{t["d"]:.0f} RSI:{t["rsi"]}</div>' for s, t in buys)
    if ah:
        ah = f'\n<div class="card buy"><div class="card-title" style="color:var(--green-go);">🔔 買進訊號（低檔金叉）</div>{ah}</div>'

    return f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>🦞 小龍蝦 | {td} 晨報</title>
<style>
:root{{--bg-dark:#121212;--card-bg:#1e1e1e;--primary-gold:#ffbe76;--red-alert:#ff6b6b;--green-go:#2ed573;--text-main:#e0e0e0;--text-muted:#a0a0a0;--border-color:#333;}}
*{{box-sizing:border-box;}} body{{font-family:-apple-system,"Segoe UI",Roboto,"Microsoft JhengHei",sans-serif;background:var(--bg-dark);color:var(--text-main);margin:0;padding:12px;font-size:18px;}}
.header{{text-align:center;padding:14px 0;border-bottom:3px solid var(--red-alert);margin-bottom:16px;}}
.header h1{{margin:0;font-size:22px;color:var(--red-alert);}}
.header p{{margin:6px 0 0;color:var(--text-muted);}}
.header .date-tag{{margin:4px 0 0;font-size:14px;color:#667788;}}
.card{{background:var(--card-bg);border-radius:8px;padding:15px;margin-bottom:15px;border-left:5px solid var(--primary-gold);}}
.card.alert{{border-left-color:var(--red-alert);}} .card.info{{border-left-color:#1e90ff;}} .card.buy{{border-left-color:var(--green-go);}}
.card-title{{font-size:20px;font-weight:bold;margin-bottom:12px;color:var(--primary-gold);}}
table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:18px;}}
th{{background:#2d2d2d;color:var(--primary-gold);padding:8px 6px;text-align:left;border-bottom:2px solid var(--border-color);}}
td{{padding:10px 6px;border-bottom:1px solid var(--border-color);vertical-align:middle;}}
.up{{color:var(--red-alert);font-weight:bold;}} .down{{color:var(--green-go);font-weight:bold;}}
.flip{{color:#ffd700;font-weight:bold;font-size:16px;}}
.buy-signal{{font-size:20px;font-weight:bold;padding:8px;margin:5px 0;background:#0d2a0d;border-radius:6px;border:1px solid var(--green-go);}}
.badge{{display:inline-block;font-size:13px;padding:1px 5px;margin:1px;border-radius:3px;white-space:nowrap;}}
.badge-red{{background:#5a1a1a;color:#ff6b6b;}} .badge-blue{{background:#1a2a4a;color:#4a9eff;}}
.news-item{{padding:5px 0;font-size:17px;border-bottom:1px solid #2a2a2a;line-height:1.4;}}
.news-item:last-child{{border-bottom:none;}}
.footer{{text-align:center;color:#445566;margin-top:30px;padding-top:15px;border-top:1px solid #333;}}
</style></head><body>
<div class="header"><h1>🦞 小龍蝦 | {td}（{wd}）晨報</h1>
<p>{mn} | TA-Lib STOCH(14,1,3) / MACD / RSI(14)</p>
<div class="date-tag">⏰ 更新：{td} {nh}｜30分K｜0 Token 本機運算</div></div>

{sox_html}{txf_html}
{linkage_html}
{events_html}
{news_html}
{ah}
<div class="card"><div class="card-title">🔒 核心持股（{len(CORE_19)}檔）[30分K]</div>
<table><thead><tr><th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{cr}</tbody></table></div>
<div class="card alert"><div class="card-title">🎯 潛力股候選（TWSE T86 投信買超）</div>
<table><thead><tr><th>股票</th><th>股價</th><th>投信買超</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{pr}</tbody></table></div>
<div class="footer">小龍蝦自動產出｜{td} {nh}｜ta_strategy_engine｜本機運算 0 Token</div>
</body></html>'''


def _pot_row(sid, sname, t, trust_amt):
    base = _row(sid, sname, t)
    trust_s = f'<div style="line-height:1.2"><b>{trust_amt:,}</b></div><div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">張</div>'
    cols = base.split("</td><td>")
    if len(cols) >= 7:
        return f"{cols[0]}</td><td>{cols[1]}</td><td>{trust_s}</td><td>" + "</td><td>".join(cols[2:])
    return base

def _row(sid, sname, t):
    px = t.get("price", 0)
    lo = t.get("low_30d")
    chg = t.get("chg_s", "")
    cls = "up" if t.get("chg", 0) > 0 else ("down" if t.get("chg", 0) < 0 else "")
    if cls:
        chg = f'<span class="{cls}">{chg}</span>'
    lo_s = str(lo) if lo else "—"
    if lo and px:
        d = round(((px / lo) - 1) * 100, 1)
        if d < 5:
            lo_s = f'<span style="color:var(--red-alert)">{lo} ⚠️</span>'
    sc = (f'<div style="line-height:1.2"><b>{sname}</b></div>'
          f'<div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">{sid}</div>')
    pc = (f'<div style="font-weight:bold;font-size:1.05em;line-height:1.2">{px}</div>'
          f'<div style="font-size:0.85em;line-height:1.2">{chg}</div>')
    return (f'<tr><td>{sc}</td><td>{pc}</td><td>{lo_s}</td>'
            f'<td>{t["kd_s"]}</td><td>{t["macd_s"]}</td><td>{t["rsi"]}</td><td>{t["strategy"]}</td></tr>\n')


# ═══════════════════════════ ⚙️ MAIN ═══════════════════════════
def main():
    print("=" * 60)
    print("  🦞 ta_strategy_engine — 量化核心引擎（完整版）")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    t0 = datetime.now()

    # ── 1. T86 投信買超 ──
    fubon_stocks = fetch_trust_top20()
    if not fubon_stocks:
        fubon_stocks = []

    # ── 2. 大盤檢查 ──
    strict_mode = check_market_below_20ma()

    # ── 3. 費半SOX ──
    print("\n📊 費半SOX + 台指期...")
    sox = get_sox_index()
    if sox:
        print(f"  費半SOX: {sox['close']:.0f} ({sox['change']:+.2f}%)")
    txf = get_taiwan_futures()
    if txf:
        print(f"  台指期夜盤: {txf['close']:.0f} ({txf['change']:+.2f}%)")

    # ── 4. 台美聯動 ──
    print("\n🔗 台美產業聯動...")
    linkage_alerts = get_linkage_alerts()
    print(f"  {'無顯著連動' if not linkage_alerts else f'{len(linkage_alerts)} 筆警報'}")

    # ── 5. 未來事件 ──
    print("\n📅 未來14天事件...")
    events = get_events()
    for e in events[:8]:
        days_str = "今天" if e["days"] == 0 else "明天" if e["days"] == 1 else f'{e["days"]}天後'
        print(f"  {e['date']} {days_str} | {e['name']}")

    # ── 6. 新聞 ──
    print()
    news_data = get_all_news()

    # ── 7. Shioaji 登入 ──
    print("\n🔌 Shioaji 登入...")
    api = login_shioaji()
    if api is None:
        print("❌ Shioaji 登入失敗，輸出簡化版報表")
        html = generate_html({}, {}, fubon_stocks, strict_mode, sox, txf, linkage_alerts, events, news_data)
        for p in [os.path.join(WEB_DIR, "index.html"), os.path.join(BASE_DIR, "index.html")]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)
        return

    try:
        # ── 8. 分析股票 ──
        all_ids = list(dict.fromkeys(CORE_IDS + [s[0] for s in fubon_stocks]))
        results = analyze_stocks(api, all_ids, strict_mode)

        core = {s: results[s] for s in CORE_IDS if s in results}
        pot = {s: results[s] for s in [s[0] for s in fubon_stocks]
               if s not in CORE_IDS and s in results}

        # ── 9. 輸出 JSON ──
        save_signal_json(results)

        # ── 10. 輸出 HTML ──
        html = generate_html(core, pot, fubon_stocks, strict_mode, sox, txf, linkage_alerts, events, news_data)
        for p in [os.path.join(WEB_DIR, "index.html"), os.path.join(BASE_DIR, "index.html")]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)

        # 買進提醒
        buys = [(s, t) for s, t in sorted(results.items()) if t and t.get("low_golden")]
        if buys:
            print("\n" + "!" * 50)
            print("  🟢🟢🟢 買進訊號 🟢🟢🟢")
            for s, t in buys:
                print(f"  🔔🔔🔔 {t['name']}({s}) [30分K] K:{t['k']:.0f} RSI:{t['rsi']}")
            print("!" * 50)
        else:
            print("\nℹ️  無低檔金叉")
    finally:
        try:
            api.logout()
        except:
            pass

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\n📄 HTML {len(html)//1024} KB | JSON saved")
    print(f"⏱️  {elapsed:.0f} 秒")
    print("📌 全部 30分K + SOX/台指 + 新聞/事件 | 0 Token 本機運算")


if __name__ == "__main__":
    main()
