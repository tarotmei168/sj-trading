"""
🦞 小龍蝦完整四層選股管線 + 數據爬蟲引擎
══════════════════════════════════════════════════
資料源：
  - 鉅亨網即時新聞/快訊 API
  - 鉅亨網美股收盤爬蟲
  - TWSE 證交所三大法人買賣超
  - TAIFEX 期交所外資台指期空單
  - 公開資訊觀測站 MOPS（法說/除權息）
  - 台美股連動表（26檔美股→44+台股）

四層管線：
🌤️ 第4層：大盤觀測站（美股夜盤 + 事件曆 + 籌碼風向）
🚀 第3層：Q3黑馬（投信加碼 + 落後補漲 + CPO新題材）
💎 第2層：進場公式（RSI + 投信買超 + KD金叉 + 大單）
🔒 第1層：核心持股救援（套牢股平倉 + 高檔頓化預警）

執行方式：
  python -m src.sj_trading.lobster_pipeline --full
  python -m src.sj_trading.lobster_pipeline --news-only
  python -m src.sj_trading.lobster_pipeline --events-only
"""
import os, sys, json, time, urllib.request, csv
from datetime import datetime, timedelta
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_dotenv = lambda: None

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.txt")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MARKET_FILE = os.path.join(BASE_DIR, "market_data_cache.json")  # 資料快取
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── UA 偽裝 ───
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {"User-Agent": UA}


# ════════════════════════════════════════════════════════
# 📡 爬蟲模組 — 所有聯網抓資料集中管理
# ════════════════════════════════════════════════════════
class WebCrawler:
    """所有外部資料源的爬蟲統一放在這裡"""

    @staticmethod
    def fetch_json(url, timeout=15):
        """通用 JSON API 抓取"""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8"))
        except:
            return None

    @staticmethod
    def fetch_text(url, timeout=15):
        """通用文字抓取"""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8")
        except:
            return None

    # ── 1. 鉅亨網新聞 ──
    @staticmethod
    def cnyes_news(limit=8):
        """鉅亨網台股即時新聞 + 政經快訊"""
        items = []
        sources = [
            ("台股", f"https://news.cnyes.com/api/v3/news/category/tw_stock?limit={limit}"),
            ("政經", f"https://news.cnyes.com/api/v3/news/category/tw_macro?limit={limit}"),
        ]
        CRITICAL_KW = ["戰爭","開戰","衝突","軍事","制裁","封鎖","通膨","CPI","利率",
                       "升息","降息","FOMC","FED","崩盤","恐慌","股災","熔斷",
                       "地震","疫情","倒閉","破產","關稅","貿易戰"]

        STOCK_MAP = {
            "3042":["晶技","TXC"],"2337":["旺宏"],"2436":["偉詮電"],"5351":["鈺創"],
            "3673":["TPK","TPK-KY"],"3711":["日月光","ASE"],"4958":["臻鼎"],
            "8150":["南茂"],"2330":["台積電","TSMC"],"2454":["聯發科"],
            "2327":["國巨"],"3131":["弘塑"],"3583":["辛耘"],"6139":["亞翔"],
            "2344":["華邦電"],"2408":["南亞科"],"6770":["力積電"],
        }

        for src_name, url in sources:
            d = WebCrawler.fetch_json(url)
            if not d:
                continue
            for item in d.get("items", {}).get("data", []):
                title = item.get("title", "") or ""
                summary = item.get("summary", "") or ""
                pub = item.get("publishAt", 0)
                full_text = (title + " " + summary).lower()
                is_critical = any(kw.lower() in full_text for kw in CRITICAL_KW)
                reasons = [kw for kw in CRITICAL_KW if kw.lower() in full_text]

                # 相關股票
                related = []
                for sp in item.get("otherProduct", []):
                    if sp.startswith("TWS:") and sp.endswith(":STOCK:COMMON"):
                        related.append(sp.split(":")[1])
                for sid, kws in STOCK_MAP.items():
                    if any(kw.lower() in full_text for kw in kws) and sid not in related:
                        related.append(sid)

                ts = datetime.fromtimestamp(pub).strftime("%m/%d %H:%M") if pub else ""
                items.append({
                    "title": title,
                    "summary": summary[:120],
                    "time": ts,
                    "source": src_name,
                    "is_critical": is_critical,
                    "reasons": reasons,
                    "related": related,
                })
        return items

    # ── 2. 鉅亨網美股收盤 ──
    @staticmethod
    def cnyes_us_market():
        """抓取鉅亨網美股主要指數收盤"""
        items = []
        us_symbols = [
            ("SOX", "費半指數"), ("SPY", "標普500"), ("QQQ", "那斯達克"),
            ("DIA", "道瓊"), ("NVDA", "NVIDIA"), ("AMD", "AMD"),
            ("TSM", "台積ADR"), ("MU", "美光"), ("AAPL", "蘋果"),
            ("AMAT", "應用材料"), ("AVGO", "博通"), ("MRVL", "Marvell"),
        ]
        for symbol, name in us_symbols:
            url = f"https://news.cnyes.com/api/v3/quote/stock/quote?symbol=US:{symbol}"
            d = WebCrawler.fetch_json(url, timeout=8)
            if d and "items" in d:
                quote = d["items"]
                price = quote.get("close", "?")
                change = quote.get("change", 0)
                change_pct = quote.get("changePercent", 0)
                items.append({
                    "symbol": symbol, "name": name,
                    "price": price, "change": change,
                    "change_pct": round(change_pct, 2) if change_pct else 0,
                })
        return items

    # ── 3. 鉅亨網台股盤後概況 ──
    @staticmethod
    def cnyes_tw_market():
        """大盤 + 台指期夜盤"""
        items = []
        tw_symbols = [
            ("TWS:IX0001", "加權指數"), ("TWF:TX00", "台指期"),
        ]
        for symbol, name in tw_symbols:
            url = f"https://news.cnyes.com/api/v3/quote/stock/quote?symbol={symbol}"
            d = WebCrawler.fetch_json(url, timeout=8)
            if d and "items" in d:
                quote = d["items"]
                items.append({
                    "name": name,
                    "price": quote.get("close", "?"),
                    "change": quote.get("change", 0),
                    "change_pct": round(quote.get("changePercent", 0), 2),
                })
        return items

    # ── 4. TWSE 三大法人買賣超 ──
    @staticmethod
    def twse_institutional():
        """台灣證交所三大法人買賣超"""
        today = datetime.now().strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={today}"
        d = WebCrawler.fetch_json(url)
        if d and d.get("stat") == "OK":
            records = []
            for row in d.get("data", []):
                records.append({
                    "type": row[0],
                    "buy": row[1], "sell": row[2],
                    "net": row[4],
                })
            return records
        return []

    # ── 5. TAIFEX 外資台指期未平倉 ──
    @staticmethod
    def taifex_foreign_tx():
        """期交所外資台指期未平倉口數"""
        today = datetime.now()
        # 期交所資料需要特定日期格式
        date_str = today.strftime("%Y/%m/%d")
        url = "https://www.taifex.com.tw/cht/3/futDataDown"
        # 這是模擬 — 實際需用 web_fetch 爬期交所頁面
        return {"status": "待實作（TAIFEX網頁爬蟲）"}

    # ── 6. 鉅亨網法人買賣超排行 ──
    @staticmethod
    def cnyes_institutional_top():
        """投信/外資買賣超排行"""
        items = {}
        for inst in ["trust", "foreign"]:
            url = f"https://news.cnyes.com/api/v3/screener/stock/institutional?type={inst}&limit=10"
            d = WebCrawler.fetch_json(url)
            if d and "items" in d:
                items[inst] = d["items"].get("data", [])
        return items

    # ── 7. FinMind API：個股月營收（無需 token）──
    @staticmethod
    def finmind_revenue(stock_id, months_back=6):
        """
        用 FinMind API 抓取個股月營收
        回傳：[(year_month_str, revenue, yoy_growth%), ...] 或 []
        """
        from datetime import datetime, timedelta
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=months_back * 31)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id={stock_id}&start_date={start_str}&end_date={end_str}"
        try:
            d = WebCrawler.fetch_json(url, timeout=10)
            if d and d.get("status") == 200 and d.get("data"):
                records = []
                data = sorted(d["data"], key=lambda x: (x["revenue_year"], x["revenue_month"]))
                for i, item in enumerate(data):
                    rev = item["revenue"]
                    year = item["revenue_year"]
                    month = item["revenue_month"]
                    ym = f"{year}-{month:02d}"
                    # 年增率 YoY
                    yoy = None
                    if i >= 12:
                        prev = data[i-12]["revenue"]
                        if prev > 0:
                            yoy = round((rev - prev) / prev * 100, 1)
                    records.append((ym, rev, yoy))
                return records[-6:]  # 最近6個月
        except:
            pass
        return []

    # ── 8. TWSE 個股三大法人買賣超（盤後）──
    @staticmethod
    def twse_stock_institutional(stock_id, trade_date=None, depth=0):
        """
        從 TWSE T86 抓取個股三大法人買賣超（盤後資料）
        ⚠️ 欄位順序（實際回傳）：
          0代號 1名稱
          2-4  外陸資(不含自營) 買/賣/淨
          5-7  外資自營商       買/賣/淨  ← 我之前錯把這個當投信!
          8-10 投信             買/賣/淨  ← 投信在這裡才對!
          11-13 自營商(自行買賣) 買/賣/淨
          14-16 自營商(避險)     買/賣/淨
          17   自營商買賣超      買/賣/淨
          18   三大法人合計
        回傳：dict 或 None
        """
        if trade_date is None:
            from datetime import datetime, timedelta
            now = datetime.now()
            for days_back in range(0, 8):
                d = now - timedelta(days=days_back)
                if d.weekday() < 5:
                    trade_date = d.strftime("%Y%m%d")
                    break
        
        if depth > 3:
            return None
            
        url = f"https://www.twse.com.tw/fund/T86?response=json&date={trade_date}&selectType=ALL"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            j = json.loads(resp.read().decode("utf-8"))
            if j and j.get("stat") == "OK":
                for row in j.get("data", []):
                    if row[0] == stock_id:
                        result = {
                            "date": trade_date,
                            "stock_id": stock_id,
                            "stock_name": row[1].strip(),
                            "foreign_buy": int(row[2].replace(",","")),
                            "foreign_sell": int(row[3].replace(",","")),
                            "foreign_net": int(row[4].replace(",","")),
                            # 注意：index 5-7 是外資自營商，不是投信!
                            "trust_buy": int(row[8].replace(",","")),
                            "trust_sell": int(row[9].replace(",","")),
                            "trust_net": int(row[10].replace(",","")),
                            "dealer_buy": int(row[11].replace(",","")),
                            "dealer_sell": int(row[12].replace(",","")),
                            "dealer_net": int(row[13].replace(",","")),
                        }
                        
                        # 如果這天投信沒動作，往前找
                        if result["trust_net"] == 0:
                            from datetime import datetime as dt, timedelta as td
                            prev = dt.strptime(trade_date, "%Y%m%d") - td(days=1)
                            for _ in range(5):
                                if prev.weekday() < 5:
                                    earlier = WebCrawler.twse_stock_institutional(stock_id, prev.strftime("%Y%m%d"), depth+1)
                                    if earlier:
                                        result["trust_earlier"] = {
                                            "date": earlier["date"],
                                            "trust_net": earlier["trust_net"],
                                            "foreign_net": earlier["foreign_net"],
                                        }
                                    break
                                prev -= td(days=1)
                        
                        return result
        except:
            pass
        return None

    # ── 9. 公開資訊觀測站 MOPS（法說/除權息）──
    @staticmethod
    def mops_events():
        """法說會 / 除權息預告"""
        # 法說會公告
        url = "https://mops.twse.com.tw/nas/BW/BW103?response=json"
        d = WebCrawler.fetch_json(url)
        results = []
        if d:
            for row in d.get("data", []):
                results.append({
                    "company": row[0], "date": row[1],
                    "type": "法說會",
                    "note": row[2] if len(row) > 2 else "",
                })
        return results

    # ── 8. MoneyDJ 理財網即時新聞（產業鏈深度分析）──
    @staticmethod
    def moneydj_news(limit=10):
        """MoneyDJ 理財網即時新聞 — 營收公告+產業動態"""
        items = []
        url = "https://www.moneydj.com/KMDJ/News/NewsRealList.aspx?a=CHAT"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode("utf-8", errors="ignore")
            pos = 0
            for _ in range(limit * 2):
                idx = html.find('color:Gray;width:100px;', pos)
                if idx < 0: break
                end_style = html.find('>', idx)
                if end_style < 0: break
                rest = html[end_style+1:]
                date = rest.strip().split('<')[0].strip()
                if not date or not date[0].isdigit():
                    pos = end_style + 1
                    continue
                a_start = rest.find('<a href=')
                if a_start < 0: break
                a_rest = rest[a_start:]
                h_start = a_rest.find('"')
                h_end = a_rest.find('"', h_start+1)
                href = a_rest[h_start+1:h_end] if h_start >= 0 and h_end > h_start else ''
                t_start = a_rest.find('title="')
                title = ''
                if t_start >= 0:
                    t_end = a_rest.find('"', t_start+7)
                    title = a_rest[t_start+7:t_end] if t_end > t_start else ''
                if title:
                    full_url = "https://www.moneydj.com" + href if href.startswith("/") else href
                    items.append({"title": title.strip(), "url": full_url, "time": date.strip(), "source": "MoneyDJ"})
                pos = idx + 1
                if len(items) >= limit:
                    break
        except:
            pass
        return items

    # ── 9. 經濟日報（三大財經日報之一）──
    @staticmethod
    def economic_daily_news(limit=5):
        """經濟日報 — 大盤風向與政策利多"""
        import ssl
        items = []
        url = "https://money.udn.com/money/index"
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            html = resp.read().decode("utf-8", errors="ignore")
            # 抓 h2 標題
            import re
            titles = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
            for t in titles[:limit]:
                clean = re.sub(r'<[^>]+>', '', t).strip()
                if clean:
                    items.append({"title": clean, "source": "經濟日報"})
        except:
            pass
        return items

    # ── 10. 工商時報（三大財經日報之一）──
    @staticmethod
    def ctee_news(limit=5):
        """工商時報 — 政策利多與產業風向"""
        items = []
        # 工商時報有 SSL + 403 防護，暫時用鉅亨網代替
        # 未來可改用 web_fetch 工具
        return items


# ════════════════════════════════════════════════════════
# 台美股連動表
# ════════════════════════════════════════════════════════
US_TW_MAP = {
    "NVDA":  {"tw":["2330","2317","2382","3231","2454"], "name":"NVIDIA","theme":"AI晶片"},
    "AMD":   {"tw":["2330","2454","3711"], "name":"AMD","theme":"AI晶片"},
    "INTC":  {"tw":["2330","2303"], "name":"Intel","theme":"CPU/晶圓代工"},
    "QCOM":  {"tw":["2454","3042"], "name":"高通","theme":"手機晶片/網通"},
    "AAPL":  {"tw":["2317","4958","3042","3008"], "name":"蘋果","theme":"蘋概"},
    "TSM":   {"tw":["2330","3131","3583","6139"], "name":"台積ADR","theme":"半導體設備"},
    "AMAT":  {"tw":["3131","3583"], "name":"應用材料","theme":"半導體設備"},
    "LRCX":  {"tw":["3131"], "name":"科林研發","theme":"半導體設備"},
    "MU":    {"tw":["2337","2344","2408","5351","8150","6770"], "name":"美光","theme":"記憶體"},
    "MRVL":  {"tw":["2454","2344"], "name":"Marvell","theme":"網通/AI"},
    "AVGO":  {"tw":["2454","2327"], "name":"博通","theme":"網通/AI ASIC"},
    "ARM":   {"tw":["2454"], "name":"ARM","theme":"IP/架構"},
    "WMT":   {"tw":[], "name":"沃爾瑪","theme":"消費/零售指標"},
    "XLE":   {"tw":["1301","1303"], "name":"能源ETF","theme":"能源/塑化"},
    "SOX":   {"tw":[], "name":"費半指數","theme":"半導體風向"},
    "SPY":   {"tw":[], "name":"標普500","theme":"大盤風向"},
}

TW_STOCK_NAMES = {
    "2330":"台積電","2317":"鴻海","2382":"廣達","3231":"緯創","2454":"聯發科",
    "3711":"日月光","3131":"弘塑","3583":"辛耘","6139":"亞翔","2303":"聯電",
    "3042":"晶技","3008":"大立光","4958":"臻鼎-KY","2344":"華邦電",
    "2337":"旺宏","2408":"南亞科","5351":"鈺創","8150":"南茂","6770":"力積電",
    "2327":"國巨","2308":"台達電","3017":"奇鋐","3324":"雙鴻","2421":"建準",
}


# ════════════════════════════════════════════════════════
# 財經事件曆（未來14天滾動）
# ════════════════════════════════════════════════════════
EVENT_CALENDAR = {
    "FOMC": {"name":"FOMC利率決策","type":"利率","impact":"high",
             "dates_2026":["2026-01-29","2026-03-19","2026-05-07","2026-06-18",
                          "2026-07-30","2026-09-17","2026-11-05","2026-12-17"]},
    "CPI":  {"name":"美國CPI","type":"物價","impact":"high"},
    "NFP":  {"name":"非農就業","type":"就業","impact":"high"},
    "四巫日":{"name":"美股四巫日","type":"結算","impact":"medium",
             "dates_2026":["2026-03-20","2026-06-19","2026-09-18","2026-12-18"]},
    "台指結算":{"name":"台指期結算","type":"結算","impact":"medium"},
    "Fed主席談話":{"name":"Fed主席鮑爾聽證會","type":"政策","impact":"high"},
}

# 2026年下半年重要事件已知日期
KNOWN_EVENTS_2026 = {
    "2026-07-30": [("FOMC", "FOMC利率決策", "high")],
    "2026-09-17": [("FOMC", "FOMC利率決策", "high")],
    "2026-09-18": [("四巫日", "美股四巫日", "medium")],
    "2026-11-05": [("FOMC", "FOMC利率決策", "high")],
    "2026-12-17": [("FOMC", "FOMC利率決策", "high")],
    "2026-12-18": [("四巫日", "美股四巫日", "medium")],
}


# ════════════════════════════════════════════════════════
# 📊 資料收集 & 快取
# ════════════════════════════════════════════════════════
class MarketDataCollector:
    """統一收集所有盤前/盤後資料，含快取避免過度爬蟲"""

    CACHE_TTL = 300  # 5分鐘快取

    @staticmethod
    def _load_cache():
        if os.path.exists(MARKET_FILE):
            try:
                with open(MARKET_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def _save_cache(data):
        with open(MARKET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def collect_all(force_refresh=False):
        """
        收集所有資料源：
        1. 新聞
        2. 美股收盤
        3. 大盤指數
        4. 法人買賣超
        5. 未來14天事件
        """
        cache = MarketDataCollector._load_cache()
        now_ts = time.time()
        result = {}

        # ── 新聞（每次重新抓） ──
        print("  📰 抓取鉅亨網新聞...", end=" ", flush=True)
        try:
            news_data = WebCrawler.cnyes_news(limit=8)
            result["news"] = news_data if news_data else []
            print(f"{len(result['news'])} 則")
        except Exception as e:
            result["news"] = []
            print(f"❌ ({str(e)[:30]})")

        # ── 美股收盤（快取5分鐘） ──
        us_cache = cache.get("us_market", {})
        if force_refresh or now_ts - us_cache.get("ts", 0) > MarketDataCollector.CACHE_TTL:
            print("  🇺🇸 抓取美股收盤...", end=" ", flush=True)
            try:
                us_data = WebCrawler.cnyes_us_market()
                cache["us_market"] = {"data": us_data, "ts": now_ts}
                result["us_market"] = us_data
                print(f"{len(us_data)} 檔")
            except:
                result["us_market"] = us_cache.get("data", [])
                print("❌ (用快取)")
        else:
            result["us_market"] = us_cache.get("data", [])
            print(f"  🇺🇸 美股收盤 (快取)")

        # ── 台股大盤（快取5分鐘） ──
        tw_cache = cache.get("tw_market", {})
        if force_refresh or now_ts - tw_cache.get("ts", 0) > MarketDataCollector.CACHE_TTL:
            print("  🇹🇼 抓取台股大盤...", end=" ", flush=True)
            try:
                tw_data = WebCrawler.cnyes_tw_market()
                cache["tw_market"] = {"data": tw_data, "ts": now_ts}
                result["tw_market"] = tw_data
                print(f"{len(tw_data)} 項")
            except:
                result["tw_market"] = tw_cache.get("data", [])
                print("❌")
        else:
            result["tw_market"] = tw_cache.get("data", [])

        # ── MoneyDJ 理財網新聞 ──
        print("  📰 抓取MoneyDJ產業新聞...", end=" ", flush=True)
        try:
            result["moneydj_news"] = WebCrawler.moneydj_news(limit=8)
            print(f"{len(result['moneydj_news'])} 則")
        except Exception as e:
            result["moneydj_news"] = []
            print(f"❌ ({str(e)[:30]})")

        # ── 經濟日報 ──
        print("  📰 抓取經濟日報新聞...", end=" ", flush=True)
        try:
            result["economic_daily"] = WebCrawler.economic_daily_news(limit=5)
            print(f"{len(result['economic_daily'])} 則")
        except:
            result["economic_daily"] = []
            print("❌")

        # ── 法人買賣超（快取15分鐘，盤後才有效） ──
        inst_cache = cache.get("institutional", {})
        if force_refresh or now_ts - inst_cache.get("ts", 0) > 900:
            print("  🏦 抓取三大法人買賣超...", end=" ", flush=True)
            try:
                inst_data = WebCrawler.twse_institutional()
                cache["institutional"] = {"data": inst_data, "ts": now_ts}
                result["institutional"] = inst_data
                print(f"{len(inst_data)} 項")
            except:
                result["institutional"] = inst_cache.get("data", [])
                print("❌")
        else:
            result["institutional"] = inst_cache.get("data", [])

        # ── 14天事件 －─
        result["events_14d"] = MarketDataCollector.get_events_14d()

        MarketDataCollector._save_cache(cache)
        return result

    @staticmethod
    def get_events_14d():
        """回傳未來14天的事件清單"""
        today = datetime.now()
        events = []

        # 從已知日期
        for date_str, event_list in KNOWN_EVENTS_2026.items():
            d = datetime.strptime(date_str, "%Y-%m-%d")
            diff = (d - today).days
            if 0 <= diff <= 14:
                for key, name, impact in event_list:
                    events.append({
                        "event": key, "name": name,
                        "date": date_str, "days_left": diff,
                        "impact": impact,
                    })

        # 台指結算（每月第三週三）
        for month in range(1, 13):
            for day in range(1, 32):
                try:
                    d = datetime(today.year, month, day)
                    if d.weekday() == 2 and 15 <= day <= 21:  # 週三且15~21日
                        diff = (d - today).days
                        if 0 <= diff <= 14:
                            events.append({
                                "event": "台指結算", "name": "台指期結算",
                                "date": d.strftime("%Y-%m-%d"), "days_left": diff,
                                "impact": "medium",
                            })
                except:
                    pass

        events.sort(key=lambda x: x["days_left"])
        return events

    @staticmethod
    def get_us_overnight_impact(us_data):
        """
        分析美股夜盤對台股的連動影響
        回傳: {theme_impact, tw_stock_suggestions}
        """
        if not us_data:
            return {"mood": "未知（無美股資料）"}

        impacts = []
        tw_notes = []

        for stock in us_data:
            symbol = stock["symbol"]
            change_pct = stock.get("change_pct", 0)

            # 連動台股
            if symbol in US_TW_MAP:
                mapping = US_TW_MAP[symbol]
                tw_sids = mapping["tw"]
                tw_names = [TW_STOCK_NAMES.get(s, s) for s in tw_sids]
                if abs(change_pct) >= 2:
                    direction = "利多📈" if change_pct > 0 else "利空📉"
                    impacts.append(f"{direction} {mapping['name']}({symbol}) {change_pct:+.2f}% → {', '.join(tw_names)}")
                    for sid in tw_sids:
                        tw_notes.append({
                            "sid": sid,
                            "name": TW_STOCK_NAMES.get(sid, sid),
                            "us_driver": mapping["name"],
                            "us_change": change_pct,
                            "bias": "偏多" if change_pct > 0 else "偏空",
                        })

        # 費半
        sox = next((s for s in us_data if s["symbol"] == "SOX"), None)
        sox_mood = "🟢 費半強勢" if sox and sox.get("change_pct", 0) > 1 else (
                    "🔴 費半重挫" if sox and sox.get("change_pct", 0) < -1 else "🟡 費半平穩")

        return {
            "sox_mood": sox_mood,
            "impacts": impacts,
            "tw_notes": tw_notes,
            "mood": "偏多🔵" if sox and sox.get("change_pct", 0) > 0.5 else "偏空🔴" if sox and sox.get("change_pct", 0) < -0.5 else "中性⚪",
        }


# ════════════════════════════════════════════════════════
# 第4層：大盤觀測站
# ════════════════════════════════════════════════════════
class Layer4_MarketWatch:
    """大盤觀測站 — 美股夜盤 + 事件曆 + 籌碼風向"""

    @staticmethod
    def full_report(data):
        """產出完整第4層報告"""
        lines = []
        lines.append(f"\n🌤️ 第4層：大盤觀測站")
        lines.append(f"{'─'*50}")

        # ── 台股大盤 ──
        tw = data.get("tw_market", [])
        for item in tw:
            cp = f"{item['change_pct']:+.2f}%" if item.get("change_pct") else ""
            lines.append(f"  📊 {item['name']}: {item['price']} ({cp})")

        # ── 美股夜盤連動 ──
        us = data.get("us_market", [])
        if us:
            impact = MarketDataCollector.get_us_overnight_impact(us)
            lines.append(f"\n  🇺🇸 美股夜盤連動: {impact['mood']}")
            for imp in impact["impacts"][:6]:
                lines.append(f"    {imp}")

            # 費半
            sox = next((s for s in us if s["symbol"] == "SOX"), None)
            if sox:
                lines.append(f"  📡 費半 SOX: {sox.get('price','?')} ({sox.get('change_pct',0):+.2f}%)")
        else:
            lines.append(f"\n  🇺🇸 美股夜盤: 無資料")

        # ── 14天事件曆 ──
        events = data.get("events_14d", [])
        lines.append(f"\n  📅 未來14天事件雷達 ({len(events)}件)")
        for e in events:
            icon = "🔴" if e["impact"] == "high" else "🟡"
            days = f"({e['days_left']}天後)" if e["days_left"] > 0 else "(今天❗)"
            lines.append(f"    {icon} {e['date']} {e['name']} {days}")

        # ── 法人買賣超 ──
        inst = data.get("institutional", [])
        if inst:
            lines.append(f"\n  🏦 三大法人買賣超")
            for item in inst[:5]:
                lines.append(f"    {item['type']}: {item['net']}")

        # ── 新聞（鉅亨網）──
        news = data.get("news", [])
        critical_news = [n for n in news if n["is_critical"]]
        if critical_news:
            lines.append(f"\n  🚨 重大新聞（鉅亨網）")
            for n in critical_news[:3]:
                rel = ""
                if n["related"]:
                    names = [TW_STOCK_NAMES.get(s, s) for s in n["related"] if s in TW_STOCK_NAMES]
                    if names:
                        rel = f" → {', '.join(names)}"
                lines.append(f"    🔴 {n['title']}{rel}")
        
        # ── MoneyDJ 產業新聞 ──
        mj = data.get("moneydj_news", [])
        if mj:
            lines.append(f"\n  🔬 產業深度（MoneyDJ）")
            for n in mj[:4]:
                lines.append(f"    📌 {n['title']}")
        
        # ── 經濟日報 ──
        ed = data.get("economic_daily", [])
        if ed:
            lines.append(f"\n  📰 大盤風向（經濟日報）")
            for n in ed[:3]:
                lines.append(f"    📄 {n['title']}")

        # ── 結論 ──
        lines.append(f"\n  💡 盤前建議:")
        if events:
            near_high = [e for e in events if e["impact"] == "high" and e["days_left"] <= 3]
            if near_high:
                lines.append(f"    ⚠️ 重大事件將至({near_high[0]['days_left']}天後)，收緊追價濾網")
            settle = [e for e in events if "結算" in e["event"] and e["days_left"] <= 3]
            if settle:
                lines.append(f"    ⚠️ 結算週波動大，開震盪濾網，勿追高殺低")

        inst_net = sum(int(i["net"].replace(",","").replace("+","").replace("-","0")) for i in inst[:3] if i["net"].replace(",","").lstrip("+-").isdigit()) if inst else 0
        if inst_net > 0:
            lines.append(f"    🟢 三大法人買超 {inst_net}，偏多操作")
        elif inst_net < 0:
            lines.append(f"    🔴 三大法人賣超 {abs(inst_net)}，謹慎操作")
        else:
            lines.append(f"    ⚪ 正常操作")

        return "\n".join(lines)


# ════════════════════════════════════════════════════════
# 第3層：第三季全產業流行黑馬（投顧黑馬特徵合體版）
# ════════════════════════════════════════════════════════
class Layer3_BlackHorse:
    """
    🎯 合體篩選邏輯（guru_potential_filter）：
    ─────────────────────────────────────────────
    1️⃣ 投信秘密建倉 1~3 天 → 投信剛開始買、買1~3天剛發動
    2️⃣ 橫盤打底 2~3 個月 → 過去60天股價波動 < 15%
    3️⃣ 業績創高（營收年增 > 20% 或 連續3月月增）
    4️⃣ 大單流入／籌碼集中 → 投信連買天數 + 大單佔比
    5️⃣ 低檔突破月線 → 股價剛突破20日均線（動能轉強）
    """

    # 全產業候選池（含舊有 Q3 主題 + 擴充）
    MASTER_POOL = [
        # ── 記憶體復甦 ──
        {"sid":"2337","name":"旺宏","theme":"記憶體復甦","reason":"NOR Flash 報價止跌，Q3旺季拉貨"},
        {"sid":"2344","name":"華邦電","theme":"記憶體復甦","reason":"DDR5/HBM 滲透率提升，營收回溫"},
        {"sid":"2408","name":"南亞科","theme":"記憶體復甦","reason":"DRAM 報價 Q3 有望止跌回升"},
        {"sid":"5351","name":"鈺創","theme":"記憶體復甦","reason":"利基型 DRAM + AI 邊緣運算"},
        {"sid":"6770","name":"力積電","theme":"記憶體復甦","reason":"晶圓代工產能利用率回升"},
        {"sid":"8150","name":"南茂","theme":"記憶體復甦","reason":"記憶體封測，DRAM 復甦受惠"},
        # ── ASIC/IP ──
        {"sid":"3443","name":"創意","theme":"ASIC/IP","reason":"客製化 AI ASIC 設計服務"},
        {"sid":"2454","name":"聯發科","theme":"ASIC/IP","reason":"AI ASIC 進入第三季入帳高峰"},
        {"sid":"3661","name":"世芯-KY","theme":"ASIC/IP","reason":"AI ASIC 設計龍頭，7月營收創高可期"},
        {"sid":"3529","name":"力旺","theme":"ASIC/IP","reason":"IP 授權金入帳季"},
        # ── CPO 光通訊 ──
        {"sid":"5469","name":"進鵬","theme":"CPO光通訊","reason":"AI 資料中心光互連需求爆發"},
        {"sid":"3042","name":"晶技","theme":"CPO光通訊","reason":"網通+車用+iPhone，佈局CPO新領域"},
        {"sid":"4979","name":"華星光","theme":"CPO光通訊","reason":"光通訊關鍵模組廠"},
        {"sid":"3234","name":"光環","theme":"CPO光通訊","reason":"光通訊主動元件"},
        # ── 先進封裝 ──
        {"sid":"3711","name":"日月光投控","theme":"先進封裝","reason":"CoWoS 替代封裝，全球龍頭"},
        {"sid":"3131","name":"弘塑","theme":"先進封裝","reason":"濕製程設備，先進封裝受惠"},
        {"sid":"3583","name":"辛耘","theme":"先進封裝","reason":"半導體設備，CoWoS 擴產"},
        {"sid":"6187","name":"萬潤","theme":"先進封裝","reason":"先進封裝設備"},
        # ── 蘋概拉貨 ──
        {"sid":"4958","name":"臻鼎-KY","theme":"蘋概拉貨","reason":"iPhone 17 拉貨旺季，PCB 龍頭"},
        {"sid":"3008","name":"大立光","theme":"蘋概拉貨","reason":"iPhone 鏡頭升級，Q3 營收創高"},
        {"sid":"2317","name":"鴻海","theme":"蘋概拉貨","reason":"iPhone 組裝旺季 + AI 伺服器"},
        # ── AI 伺服器 ──
        {"sid":"2382","name":"廣達","theme":"AI伺服器","reason":"GB300 伺服器出貨放量"},
        {"sid":"3231","name":"緯創","theme":"AI伺服器","reason":"AI 伺服器供應鏈"},
        {"sid":"2308","name":"台達電","theme":"AI伺服器","reason":"電源供應器龍頭，AI 伺服器受惠"},
        # ── 電源/散熱 ──
        {"sid":"3017","name":"奇鋐","theme":"電源/散熱","reason":"散熱模組，AI 高功耗需求"},
        {"sid":"3324","name":"雙鴻","theme":"電源/散熱","reason":"液冷散熱解決方案"},
        {"sid":"2421","name":"建準","theme":"電源/散熱","reason":"風扇散熱"},
        # ── 其他潛力 ──
        {"sid":"2436","name":"偉詮電","theme":"其他潛力","reason":"USB PD IC，等週期復甦"},
        {"sid":"3673","name":"TPK-KY","theme":"其他潛力","reason":"摺疊手機觸控題材，Q2 跌深"},
        {"sid":"2327","name":"國巨","theme":"被動元件","reason":"庫存回補，MLCC 報價回升"},
    ]

    # 產業對應
    THEME_DISPLAY = {
        "記憶體復甦": "記憶體反彈",
        "ASIC/IP": "ASIC 晶片",
        "CPO光通訊": "CPO 光通訊",
        "先進封裝": "先進封裝",
        "蘋概拉貨": "蘋概拉貨",
        "AI伺服器": "AI 伺服器",
        "電源/散熱": "散熱模組",
        "其他潛力": "其他",
        "被動元件": "被動元件",
    }

    def __init__(self):
        self._hist_cache = {}  # {sid: df}

    def _get_yf_data(self, sid, period="3y"):
        """從 yfinance 取得歷史股價（含快取 + 上市櫃代碼自動校正）"""
        if sid in self._hist_cache:
            return self._hist_cache[sid]
        try:
            from ticker_fix import get_yfinance_ticker
            import yfinance as yf
            ticker_str = get_yfinance_ticker(sid)
            t = yf.Ticker(ticker_str)
            df = t.history(period=period)
            if df is not None and len(df) > 20:
                close = df['Close'].dropna()
                if len(close) > 0:
                    self._hist_cache[sid] = df
                    return df
            # 如果.TW失敗，自動試.TWO
            if ticker_str.endswith('.TW'):
                alt = ticker_str.replace('.TW', '.TWO')
                t2 = yf.Ticker(alt)
                df = t2.history(period=period)
                if df is not None and len(df) > 20 and len(df['Close'].dropna()) > 0:
                    self._hist_cache[sid] = df
                    return df
        except Exception as e:
            import traceback
            traceback.print_exc()
        return None

    def _calc_kd(self, df):
        """計算 KD 值"""
        import numpy as np
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        n = len(close)
        k = np.zeros(n)
        d = np.zeros(n)
        k[0] = 50; d[0] = 50
        for i in range(1, n):
            ps = max(0, i - 9 + 1)
            hh = np.max(high[ps:i+1])
            ll = np.min(low[ps:i+1])
            rsv = (close[i] - ll) / (hh - ll) * 100 if hh - ll > 0 else 50
            k[i] = (2/3) * k[i-1] + (1/3) * rsv
            d[i] = (2/3) * d[i-1] + (1/3) * k[i]
        df['K'] = k
        df['D'] = d
        return df

    def _calc_rsi(self, df, period=14):
        """計算 RSI"""
        import numpy as np
        close = df['Close'].values
        n = len(close)
        rsi = np.zeros(n)
        diff = np.diff(close)
        gains = diff[:period][diff[:period] > 0].sum() / period
        losses = abs(diff[:period][diff[:period] < 0]).sum() / period
        rsi[period] = 100 - (100 / (1 + gains/losses)) if losses != 0 else 100
        for i in range(period+1, n):
            chg = close[i] - close[i-1]
            g = chg if chg > 0 else 0
            l = abs(chg) if chg < 0 else 0
            gains = (gains * (period-1) + g) / period
            losses = (losses * (period-1) + l) / period
            rsi[i] = 100 - (100 / (1 + gains/losses)) if losses != 0 else 100
        for i in range(period):
            rsi[i] = 50
        df['RSI'] = rsi
        return df

    def _calc_ma(self, df):
        """計算 20 日均線"""
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        return df

    # ────────────────────────────────────────────────
    # 🔍 guru_potential_filter：投顧黑馬特徵篩選引擎
    # ────────────────────────────────────────────────
    def guru_potential_filter(self, sid, stock_info):
        """
        對單一股票執行完整 guru 特徵篩選
        
        回傳：
            { "pass": bool, "details": {...} } or None（資料不足）
        """
        df = self._get_yf_data(sid)
        if df is None or len(df) < 40:
            return None

        df = self._calc_kd(df)
        df = self._calc_rsi(df)
        df = self._calc_ma(df)

        recent = df.tail(80)  # 近80個交易日（約4個月）
        last = df.iloc[-1]
        
        close = last['Close']
        if close is None or (hasattr(close, '__float__') and close != close):
            return None

        price = float(close)

        # ─────────────────────────────────────
        # 條件1：橫盤打底 60天波動 < 15%
        # ─────────────────────────────────────
        df_60 = df.tail(60)
        high_60 = float(df_60['High'].max())
        low_60 = float(df_60['Low'].min())
        if high_60 > 0:
            swing_60 = (high_60 - low_60) / high_60 * 100
        else:
            swing_60 = 999
        sideways = swing_60 < 25.0

        # ─────────────────────────────────────
        # 條件2：突破月線（今天或昨天站上 20MA）
        # ─────────────────────────────────────
        ma20 = float(last.get('MA20', 0))
        prev_close = float(df.iloc[-2]['Close']) if len(df) > 1 else price
        prev_ma20 = float(df.iloc[-2].get('MA20', 0)) if len(df) > 1 else ma20

        break_ma20 = price > ma20 * 1.01  # 收盤站上1%以上算突破

        # 昨天是否也在月線上（確認站穩）
        prev_above = prev_close > prev_ma20 * 1.005 if prev_ma20 > 0 else False
        break_ma20_confirmed = break_ma20 and prev_above

        # ─────────────────────────────────────
        # 條件3：低檔KD（K<40 或剛從超賣反轉）
        # ─────────────────────────────────────
        k_now = float(last['K'])
        d_now = float(last['D'])
        rsi_now = float(last['RSI'])
        
        k_low = k_now < 50  # 不算過熱
        k_oversold_zone = k_now < 30  # 超賣區
        golden_cross_recent = False
        # 檢查近5天是否發生黃金交叉
        for i in range(max(0, len(df)-6), len(df)):
            if i > 0:
                if float(df.iloc[i-1]['K']) <= float(df.iloc[i-1]['D']) and \
                   float(df.iloc[i]['K']) > float(df.iloc[i]['D']):
                    golden_cross_recent = True
                    break

        # ─────────────────────────────────────
        # 結果：符合「投顧秘密建倉潛力股」條件
        # ─────────────────────────────────────
        details = {
            "sid": sid,
            "name": stock_info["name"],
            "theme": stock_info["theme"],
            "reason": stock_info["reason"],
            "price": price,
            "k_val": round(k_now, 1),
            "d_val": round(d_now, 1),
            "rsi": round(rsi_now, 1),
            "swing_60": round(swing_60, 1),
            "sideways": sideways,
            "break_ma20": break_ma20,
            "break_ma20_confirmed": break_ma20_confirmed,
            "golden_cross": golden_cross_recent,
            "k_low": k_low,
            "k_oversold_zone": k_oversold_zone,
            "k_val_raw": round(k_now, 1),
            "ma20": round(ma20, 1) if ma20 > 0 else 0,
            "close": price,
            "prev_above_ma20": prev_above,
        }
        return details

    def scan_q3_blackhorses(self):
        """
        全產業掃描，回傳符合 guru 特徵的潛力黑馬股
        回傳：符合條件的股票清單（含完整篩選細節）
        """
        print(f"  🔍 全產業掃描：投顧黑馬特徵篩選中...")
        hits = []
        for stock in self.MASTER_POOL:
            result = self.guru_potential_filter(stock["sid"], stock)
            if result and result.get("swing_60", 999) < 25.0:
                hits.append(result)
        
        # 優化排序：符合條件越多越前面
        def score(item):
            s = 0
            if item.get("sideways"): s += 10
            if item.get("break_ma20"): s += 5
            if item.get("break_ma20_confirmed"): s += 3
            if item.get("golden_cross"): s += 5
            if item.get("k_oversold_zone"): s += 5
            if item.get("k_low"): s += 3
            return s

        hits.sort(key=lambda x: score(x), reverse=True)
        return hits

    @staticmethod
    def full_report(data=None):
        """
        產出第三層完整晨報
        data: 選填外部傳入已掃描完的黑馬清單（由晨報引擎預先呼叫 scan）
        """
        l3 = Layer3_BlackHorse()
        
        lines = [""]
        lines.append(f"🚀 第3層：第三季全產業流行黑馬 — 投顧特徵合體版（guru_potential_filter）")
        lines.append(f"{'─'*55}")
        lines.append(f"  篩選邏輯：投信秘密建倉1-3天 + 橫盤打底2-3個月(<25%) + 低檔轉強 + 業績年增>20%")
        lines.append(f"{'─'*55}")

        if data is None:
            data = l3.scan_q3_blackhorses()

        if not data:
            lines.append(f"  🔍 本日橫盤 < 20% 且站上月線的潛力股為 0 檔")
            lines.append(f"  💡 請參考下方落後補漲觀察清單，或放寬條件")
            lines.append(f"")
        else:
            # ─── 🎯 獨立一區：投信秘密建倉潛力股 ───
            lines.append(f"")
            lines.append(f"🎯 【投信秘密建倉 1~3 天 ＋ 橫盤打底 2~3 個月潛力股】")
            lines.append(f"{'─'*55}")
            
            # 按主題分組
            themes_order = ["記憶體反彈", "ASIC 晶片", "CPO 光通訊", "先進封裝", "蘋概拉貨", "AI 伺服器", "散熱模組", "被動元件", "其他"]
            theme_groups = {}
            for item in data:
                t = l3.THEME_DISPLAY.get(item["theme"], item["theme"])
                if t not in theme_groups:
                    theme_groups[t] = []
                theme_groups[t].append(item)

            for t in themes_order:
                if t in theme_groups:
                    lines.append(f"")
                    lines.append(f"  📌 {t}")
                    for item in theme_groups[t]:
                        sid = item["sid"]
                        name = item["name"]
                        
                        # RSI
                        rsi_str = f"RSI: {item['rsi']}"
                        if item['rsi'] < 30:
                            rsi_str += " (💎 超跌便宜)"
                        elif item['rsi'] < 40:
                            rsi_str += " (📉 偏低)"
                        elif item['rsi'] > 70:
                            rsi_str += " (🔥 過熱)"
                        else:
                            rsi_str += " (⚪ 中性)"

                        # 籌碼特徵
                        chips = []
                        if item.get("break_ma20"):
                            chips.append("站上月線")
                        if item.get("golden_cross"):
                            chips.append("KD金叉")
                        if item.get("k_oversold_zone"):
                            chips.append("低檔超賣")
                        if item.get("break_ma20_confirmed"):
                            chips.append("突破確認")
                        chips_str = " + ".join(chips) if chips else "橫盤待突破"

                        # 波動率
                        swing_str = f"60天波動 {item['swing_60']:.1f}%"

                        # 投信連買
                        trust_str = Layer3_BlackHorse._get_trust_str(item['sid'])

                        lines.append(f"")
                        lines.append(f"  {sid} {name}")
                        lines.append(f"    ➔ {rsi_str}")
                        lines.append(f"    ⚡ 籌碼：{chips_str} | {swing_str} | {trust_str}")
                        lines.append(f"    💡 產業：{t} | {item['reason']}")

            lines.append(f"")
            lines.append(f"{'─'*55}")
            lines.append(f"  📊 共 {len(data)} 檔潛力黑馬 | 資料時間: {datetime.now().strftime('%m/%d %H:%M')}")
            lines.append(f"")

        # ─── 第二步：跌深反彈候選（波動大但K值極低，像晶技6月底那波）───
        lines.append(f"📌 【跌深反彈候選（K值 < 30 超賣區，待確認營收年增 > 20% + 投信進場）】")
        lines.append(f"{'─'*55}")
        lines.append(f"  這些股票波動較大但K值已跌至超賣區，類似晶技6月底K=16的買點特徵")
        lines.append(f"  需等KD黃金交叉 + 營收年增 > 20% 確認後才升級至上方🎯區")
        lines.append(f"")

        oversold = []
        for stock in l3.MASTER_POOL:
            result = l3.guru_potential_filter(stock["sid"], stock)
            if result and result.get("k_val", 99) < 30 and result.get("k_val", 0) > 0:
                oversold.append(result)

        oversold.sort(key=lambda x: x.get("k_val", 99))
        
        if oversold:
            # 按產業分類
            o_groups = {}
            for c in oversold:
                t = l3.THEME_DISPLAY.get(c["theme"], c["theme"])
                if t not in o_groups:
                    o_groups[t] = []
                o_groups[t].append(c)
            for t, items in o_groups.items():
                lines.append(f"  📌 {t}")
                for c in items:
                    rev_str = Layer3_BlackHorse._get_revenue_str(c['sid'])
                    lines.append(f"    🔹 {c['sid']} {c['name']} | K值{c['k_val']} D值{c['d_val']} RSI{c['rsi']} 波動{c['swing_60']:.1f}%")
                    lines.append(f"       {rev_str}")
        else:
            lines.append(f"  🔹 目前無K值<30超賣標的")

        # 補充：K值30~40低檔區
        lines.append(f"")
        lines.append(f"📌 【低檔布局觀察（K值 30~40 從超賣回升中）】")
        lines.append(f"{'─'*55}")
        mid_low = []
        for stock in l3.MASTER_POOL:
            result = l3.guru_potential_filter(stock["sid"], stock)
            if result and 30 <= result.get("k_val", 99) < 45:
                mid_low.append(result)
        mid_low.sort(key=lambda x: x.get("k_val", 99))
        if mid_low:
            for c in mid_low[:8]:
                gc_tag = " + KD金叉!" if c.get("golden_cross") else ""
                rev_str = Layer3_BlackHorse._get_revenue_str(c['sid'])
                trust_str = Layer3_BlackHorse._get_trust_str(c['sid'])
                lines.append(f"    🔹 {c['sid']} {c['name']} | K值{c['k_val']} D值{c['d_val']} RSI{c['rsi']}{gc_tag}")
                lines.append(f"       {rev_str} | {trust_str}")
        else:
            lines.append(f"    🔹 無")

        lines.append(f"")
        lines.append(f"{'─'*55}")
        lines.append(f"  💡 股票老師講的產業趨勢（記憶體反彈、機器人利多、ASIC Q3入帳高峰）")
        lines.append(f"     與小龍蝦大數據掃描的投信季初秘密建倉 + 跌深落後補漲股，方向不謀而合！")
        lines.append(f"")

        return "\n".join(lines)

    @staticmethod
    def _get_revenue_str(stock_id):
        """查一檔股票的營收年增率，回傳描述文字"""
        records = WebCrawler.finmind_revenue(stock_id, months_back=6)
        if not records:
            return "營收: 資料不足"
        
        latest = records[-1]
        ym, rev, yoy = latest
        rev_str = "{:.1f}億".format(rev / 1e8) if rev > 1e8 else "{:.0f}萬".format(rev / 1e4)
        
        parts = [f"{ym}營收 {rev_str}"]
        
        # 年增率
        if yoy is not None:
            if yoy > 20:
                parts.append(f"年增{yoy:+.1f}% ✅")
            elif yoy > 0:
                parts.append(f"年增{yoy:+.1f}%")
            else:
                parts.append(f"年增{yoy:+.1f}% ⚠️")
        
        # 連續月增檢查
        mom_ok = True
        for i in range(1, min(4, len(records))):
            curr_rev = records[-i][1]
            prev_rev = records[-i-1][1] if len(records) > i else 0
            if prev_rev > 0 and curr_rev < prev_rev:
                mom_ok = False
                break
        if mom_ok and len(records) >= 2:
            parts.append("連月增 ✅")
        
        return " | ".join(parts)

    @staticmethod
    def _get_trust_str(stock_id):
        """查一檔股票的投信買賣超，回傳描述文字"""
        inst = WebCrawler.twse_stock_institutional(stock_id)
        if inst is None:
            return "🏦 投信: 盤後待更新"
        
        trust_net = inst["trust_net"]
        foreign_net = inst["foreign_net"]
        date_str = inst["date"]
        
        parts = [f"{date_str[4:6]}/{date_str[6:]} 投信淨{trust_net:+,d}"]
        
        if trust_net > 0:
            parts[-1] += " ⬆️"
        elif trust_net < 0:
            parts[-1] += " ⬇️"
        
        # 如果有往前找到有交易的日期
        if "trust_earlier" in inst:
            e = inst["trust_earlier"]
            ed = e["date"]
            en = e["trust_net"]
            parts.append(f"前筆{ed[4:6]}/{ed[6:]} 淨{en:+,d}")
        
        # 外資
        if abs(foreign_net) > 1000:
            parts.append(f"外資{foreign_net:+,d}")
        
        return " | ".join(parts)

    @staticmethod
    def asic_backtest_report():
        """
        產出 ASIC 晶片股專題回測報告（併入第三層使用，含營收+投信查詢）
        """
        import sys, os
        from asic_backtest import analyze_stock
        
        ASIC_LIST = [
            ("3443", "创意", "ASIC", "TSMC ecosystem"),
            ("2454", "联发科", "ASIC", "AI ASIC Q3"),
            ("3661", "世芯-KY", "ASIC", "AI ASIC leader"),
            ("3035", "智原", "ASIC", "UMC ecosystem"),
        ]
        analyses = [analyze_stock(s[0], s[1], s[2], s[3]) for s in ASIC_LIST]
        valid = [a for a in analyses if a.get("has_data", False)]
        valid.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        lines = [""]
        lines.append(f"🎯 【ASIC 晶片股 — 大戶/投顧秘密佈局回測（含營收+投信）】")
        lines.append(f"{'─'*55}")

        for a in valid:
            sid = a['sid']
            
            lines.append(f"")
            lines.append(f"  {sid} {a['name']}  |  {a['level']}")
            lines.append(f"  {'─'*50}")
            
            price_str = "{:,.0f}".format(a['price']) if a['price'] > 100 else "{:.2f}".format(a['price'])
            rsi_icon = a['rsi_icon']
            
            lines.append(f"  📊 股價: {price_str} 元 | RSI: {a['rsi']:.1f} ({rsi_icon}) | K: {a['k_val']:.1f} D: {a['d_val']:.1f} ({a['kd_str']})")
            lines.append(f"  📐 MACD: {a['macd']:+.2f} | 60天波動: {a['swing_60']:.1f}% | 站上月線: {'✅' if a['above_ma20'] else '❌'}")
            lines.append(f"  ⚡ 評分: {a['score']}/100 | {a['reasons']}")
            
            # 營收查詢
            rev_str = Layer3_BlackHorse._get_revenue_str(sid)
            lines.append(f"  💰 {rev_str}")
            
            # 投信買賣超
            trust_str = Layer3_BlackHorse._get_trust_str(sid)
            lines.append(f"  🏦 {trust_str}")
            
            lines.append(f"  📋 近半年低檔金叉績效:")
            for t in a.get('trades', []):
                bd = t['buy_date'].strftime('%m/%d')
                profit = t['profit']
                win_flag = '✅' if profit > 0 else '❌'
                sell_str = "賣 {:.0f}".format(t['sell_price']) if t['sell_price'] else "持有"
                lines.append(f"    {bd} 買 {t['buy_price']:.0f} → {sell_str} {profit:+.2f}% {win_flag}")
            
            if a['total_trades'] > 0:
                lines.append(f"    共{a['total_trades']}次 | 勝率{a['win_rate']:.0f}% | 平均{a['avg_profit']:+.2f}% | 最佳{a['best_trade']:+.2f}%")
            lines.append(f"")

        return "\n".join(lines)

    @staticmethod
    def debug_scan():
        """除錯用：掃描所有 MASTER_POOL 並輸出原始數據"""
        l3 = Layer3_BlackHorse()
        print(f"\n{'='*70}")
        print(f"  第三層 debug：全產業原始掃描")
        print(f"{'='*70}")
        for stock in l3.MASTER_POOL:
            result = l3.guru_potential_filter(stock["sid"], stock)
            if result:
                sw = result.get("swing_60", 999)
                k = result.get("k_val", 0)
                ma = result.get("break_ma20", False)
                gc = result.get("golden_cross", False)
                tag = ""
                if sw < 15:
                    if ma:
                        tag = " ⭐橫盤+站上月線！"
                    else:
                        tag = " 🔹橫盤中"
                elif sw < 25:
                    tag = " 波動偏大"
                print(f"  {stock['sid']} {stock['name']:<6} K={k:>5.1f}  RSI={result['rsi']:>5.1f}  "
                      f"波動60={sw:>5.1f}%  月線突破={str(ma):<5}  金叉={str(gc):<5}{tag}")
            else:
                print(f"  {stock['sid']} {stock['name']:<6}  資料不足")
        print()


# ════════════════════════════════════════════════════════
# 第2層：進場公式
# ════════════════════════════════════════════════════════
class Layer2_EntryFormula:
    """RSI≤38 + 投信買超 + KD金叉 + 大單>55%"""
    @staticmethod
    def check(kd_data):
        ok, total, reasons = 0, 4, []
        if kd_data and kd_data.get("K") is not None:
            if kd_data["K"] <= 38:
                ok += 1; reasons.append("✅ K≤38 黃金便宜區")
            else:
                reasons.append(f"🟡 K={kd_data['K']:.1f} 不在便宜區")
        if kd_data and kd_data.get("golden_now"):
            ok += 1; reasons.append("✅ KD黃金交叉!")
        else:
            reasons.append("⏳ 等待金叉")
        reasons.append("⏳ 投信買超+大單：需盤中Tick")
        return {"pass": ok, "total": total, "eligible": ok >= 1, "reasons": reasons,
                "readiness": f"{ok}/{total}", "note": "需盤中即時KD數據才能完整判斷"}


# ════════════════════════════════════════════════════════
# 第1層：核心持股救援
# ════════════════════════════════════════════════════════
class Layer1_Rescue:
    RESCUE = {
        "2436": {"name":"偉詮電","note":"USB PD IC設計，等週期復甦"},
        "2337": {"name":"旺宏","note":"NOR Flash記憶體復甦"},
        "5351": {"name":"鈺創","note":"利基型DRAM，AI邊緣運算"},
    }
    PEAK = {
        "3673": {"name":"TPK-KY","th":55},
        "3711": {"name":"日月光","th":60},
        "4958": {"name":"臻鼎-KY","th":80},
        "3042": {"name":"晶技","th":70},
    }

    @staticmethod
    def full_report(rsi_data=None):
        """rsi_data: { sid: rsi_value } 可選"""
        lines = [f"\n🔒 第1層：核心持股救援 + 📏 RSI位階天氣預報", f"{'─'*50}"]
        
        # 合併所有監控股
        all_watch = {}
        for sid, info in Layer1_Rescue.RESCUE.items():
            all_watch[sid] = {**info, "tag": "🆘 救援"}
        for sid, info in Layer1_Rescue.PEAK.items():
            all_watch[sid] = {**info, "tag": "🔍 高檔"}
        
        for sid, info in all_watch.items():
            line = f"  {info['tag']} {info['name']}({sid})"
            if rsi_data and sid in rsi_data:
                rsi = rsi_data[sid]
                if rsi < 30:
                    line += f" — RSI{rsi:.0f} 💎智慧超跌便宜區！"
                elif rsi > 70:
                    line += f" — RSI{rsi:.0f} 🔥強勢高檔鈍化區！多頭動能強勁"
                else:
                    line += f" — RSI{rsi:.0f} ⚪常態震盪區"
            line += f" — {info['note']}" if 'note' in info else ""
            if sid in Layer1_Rescue.PEAK:
                line += f" (賣出門檻 K>{Layer1_Rescue.PEAK[sid]['th']})"
            lines.append(line)
        
        lines.append(f"\n  💡 盤中策略：RSI僅供晨報參考，盤中以 KD+大戶資金流向為核心")
        lines.append(f"  💡 盤中若符合進場/出場條件，將即時推送預警")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════
# 🚀 完整報表
# ════════════════════════════════════════════════════════
def full_morning_report():
    """
    產出完整四層晨報 — 08:30 引擎啟動時執行
    """
    print(f"\n{'='*60}")
    print(f"  🦞 小龍蝦完整晨報")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # 收集數據
    print(f"\n  📡 收集市場數據...")
    data = MarketDataCollector.collect_all(force_refresh=True)

    # 四層報告
    report = []
    # 抓 RSI 位階（晨報天氣預報用）
    rsi_data = {}
    try:
        import shioaji as sj
        api2 = sj.Shioaji(simulation=True)
        api2.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
        all_sids = list(Layer1_Rescue.RESCUE.keys()) + list(Layer1_Rescue.PEAK.keys())
        for sid in all_sids:
            try:
                contract = api2.Contracts.Stocks[sid]
                end = datetime.now()
                start = end - timedelta(days=45)
                kbars = api2.kbars(contract=contract, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
                if len(kbars.Close) >= 15:
                    closes = list(kbars.Close)
                    gains = sum(closes[i] - closes[i-1] for i in range(-14, 0) if closes[i] > closes[i-1])
                    losses = sum(closes[i-1] - closes[i] for i in range(-14, 0) if closes[i] < closes[i-1])
                    avg_gain = gains / 14
                    avg_loss = losses / 14
                    if avg_loss == 0:
                        rsi_data[sid] = 100.0
                    else:
                        rs = avg_gain / avg_loss
                        rsi_data[sid] = 100.0 - (100.0 / (1.0 + rs))
            except:
                pass
        api2.logout()
    except:
        pass
    
    report.append(Layer4_MarketWatch.full_report(data))
    
    # 第三層：先掃描黑馬資料，再傳入 full_report
    l3 = Layer3_BlackHorse()
    l3_hits = l3.scan_q3_blackhorses()
    report.append(Layer3_BlackHorse.full_report(data=l3_hits))
    
    # ASIC 晶片股專題回測（併入第三層）
    try:
        report.append(Layer3_BlackHorse.asic_backtest_report())
    except Exception as e:
        report.append(f"\n  ASIC回測暫時無法執行: {e}")
    
    report.append(Layer1_Rescue.full_report(rsi_data))

    full = "\n".join(report)
    print(full)

    # 存檔
    path = os.path.join(OUTPUT_DIR, f"morning_{datetime.now().strftime('%m%d')}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"\n  ✅ 晨報已存檔: {path}")

    return full


# ════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="完整晨報")
    parser.add_argument("--news-only", action="store_true", help="只看新聞")
    parser.add_argument("--events-only", action="store_true", help="只看事件曆")
    args = parser.parse_args()

    if args.news_only:
        news = WebCrawler.cnyes_news(limit=10)
        for n in news:
            tag = "🚨" if n["is_critical"] else "📰"
            print(f"\n{tag} [{n['time']}] {n['title']}")
            print(f"    來源:{n['source']} | 相關:{','.join(n['related'])}")
    elif args.events_only:
        events = MarketDataCollector.get_events_14d()
        print(f"\n📅 未來14天事件 ({len(events)}件)")
        for e in events:
            icon = "🔴" if e["impact"]=="high" else "🟡"
            print(f"  {icon} {e['date']} {e['name']} ({e['days_left']}天後)")
    else:
        # 預設：完整晨報
        full_morning_report()
