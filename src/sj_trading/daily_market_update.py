# -*- coding: utf-8 -*-
"""
 ============================================================
  Data: Daily Market Database Full Update
 ============================================================
  Schedule: 16:30 Mon-Fri after market close
  Tasks:
    1. Download institutional trust buying/selling -> SITC_Accumulation.csv
    2. Download fundamentals (revenue/EPS/PE) -> Fundamentals_Database.csv
    3. Generate potential candidates based on post-market TWSE T86 trust buy scan -> Potential_Candidates.txt
    4. AI產業聯想（DeepSeek自我思考）
 ============================================================
"""
import sys, os, json, urllib.request, csv, time
from datetime import datetime, timedelta
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SITC_FILE = os.path.join(OUTPUT_DIR, "SITC_Accumulation.csv")
FUND_FILE = os.path.join(OUTPUT_DIR, "Fundamentals_Database.csv")
CANDIDATE_FILE = os.path.join(OUTPUT_DIR, "Potential_Candidates.txt")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
HEADERS = {"User-Agent": UA}
NOW = datetime.now()
DATE_STR = NOW.strftime("%Y-%m-%d")
TIME_TAG = NOW.strftime("%m/%d %H:%M")

# Watchlist (~60 stocks covering all themes + trust accumulation picks)
WATCH_STOCKS = [
    ("3443","Creative"), ("2454","MediaTek"), ("3661","Alchip"), ("3035","Faraday"),
    ("6643","M31"), ("3529","eMemory"), ("3228","GoldenTek"),
    ("2337","Macronix"), ("2344","Winbond"), ("2408","Nanya"),
    ("5351","Etron"), ("6770","Powerchip"),
    ("3711","ASE"), ("3131","GrandProcess"), ("3583","Scientech"),
    ("6187","WanRun"), ("5469","JinnPeng"), ("3042","TXC"),
    ("2382","Quanta"), ("3231","Wistron"), ("2317","HonHai"), ("2308","Delta"),
    ("3017","AsiaVital"), ("3324","ShuangHong"), ("2421","JianZhun"),
    ("4958","ZhenDing"), ("3008","Largan"),
    ("2327","Yageo"), ("2436","WeiQuan"), ("3673","TPK-KY"),
    ("8150","NanMao"), ("2303","UMC"),
]

KEYWORD_FILTERS = [
    "ASIC", "IP", "AI", "machine", "robot",
    "server", "packaging", "CPO", "optical", "CoWoS",
    "HBM", "DDR5", "cooling",
]


# =========================================================
#  Step 1: Trust Buying Accumulation (SITC_Accumulation.csv)
# =========================================================
def update_sitc_accumulation():
    """Download TWSE institutional data and update accumulation CSV"""
    print("")
    print("=" * 60)
    print("  [Step 1] Trust Buying Accumulation Update")
    print("  %s" % TIME_TAG)
    print("=" * 60)

    accumulation = {}
    if os.path.exists(SITC_FILE):
        with open(SITC_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["stock_id"]
                if sid not in accumulation:
                    accumulation[sid] = []
                accumulation[sid].append({
                    "date": row["date"],
                    "trust_net": int(row["trust_net"]),
                    "foreign_net": int(row["foreign_net"]),
                })

    trade_date = None
    for days_back in range(0, 8):
        d = NOW - timedelta(days=days_back)
        if d.weekday() < 5:
            trade_date = d.strftime("%Y%m%d")
            break

    if trade_date is None:
        print("  No trading day found in last 7 days")
        return accumulation

    print("  Trading date: %s" % trade_date)
    url = "https://www.twse.com.tw/fund/T86?response=json&date=%s&selectType=ALL" % trade_date
    print("  Downloading...", end=" ", flush=True)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=30)
        j = json.loads(resp.read().decode("utf-8"))

        if j.get("stat") != "OK":
            print("FAILED: %s" % j.get("errMsg", "?"))
            return accumulation

        rows = j.get("data", [])
        print("%d records" % len(rows))

        watch_sids = [s[0] for s in WATCH_STOCKS]
        updated_count = 0
        
        # 🚀 全市場掃描：不只是 watchlist，是所有有投信買超的股票
        trust_hot_full = []  # 全市場投信買超資料
        for row in rows:
            sid = row[0]
            
            trust_net = int(row[10].replace(",", ""))
            foreign_net = int(row[4].replace(",", ""))
            name = row[1].strip()
            
            # 如果只看 watchlist 才過濾
            if sid in watch_sids:
                if sid not in accumulation:
                    accumulation[sid] = []
                existing_dates = [e["date"] for e in accumulation[sid]]
                if trade_date not in existing_dates:
                    accumulation[sid].append({
                        "date": trade_date,
                        "trust_net": trust_net,
                        "foreign_net": foreign_net,
                    })
                    updated_count += 1
            
            # 全市場：存到記憶體供分析
            if trust_net >= 200000:  # 只記買超>20萬的
                trust_hot_full.append((sid, name, trust_net, foreign_net))
        
        print("  Updated %d watchlist stocks" % updated_count)
        
        # 全市場 TOP 50 投信買超寫檔
        trust_hot_full.sort(key=lambda x: x[2], reverse=True)
        hot_path = os.path.join(OUTPUT_DIR, "trust_top50_today.txt")
        with open(hot_path, "w", encoding="utf-8") as f:
            f.write(f"投信買超TOP50（{trade_date}）\n")
            f.write("=" * 60 + "\n")
            f.write(f"{'代號':>6s} {'名稱':<10s} {'買超':>12s} {'外資':>12s}\n")
            f.write("-" * 45 + "\n")
            for sid, name, tn, fn in trust_hot_full[:50]:
                f.write(f"{sid:>6s} {name:<10s} {tn:>10,d} {fn:>10,d}\n")
        print("  Saved trust_top50_today.txt")
        
        # 用全市場資料更新生成候選清單的 threshold
        # 將暫時存入全域供 generate_candidates 使用
        global _LAST_TRUST_HOT_FULL
        _LAST_TRUST_HOT_FULL = trust_hot_full

    except Exception as e:
        print("FAILED: %s" % str(e)[:60])

    with open(SITC_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stock_id", "date", "trust_net", "foreign_net"])
        for sid, records in accumulation.items():
            for r in records:
                writer.writerow([sid, r["date"], r["trust_net"], r["foreign_net"]])

    print("  Saved: %s" % SITC_FILE)
    return accumulation


# =========================================================
#  Step 2: Fundamentals Database (Fundamentals_Database.csv)
# =========================================================
def update_fundamentals():
    """Download monthly revenue + latest price for all watch stocks"""
    print("")
    print("=" * 60)
    print("  [Step 2] Fundamentals Database Update")
    print("  %s" % TIME_TAG)
    print("=" * 60)

    fundamentals = {}
    if os.path.exists(FUND_FILE):
        with open(FUND_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fundamentals[row["stock_id"]] = row

    count = 0
    for sid, sname in WATCH_STOCKS:
        try:
            # Monthly revenue from FinMind API
            # ??撟渡??嗉???蝣箔?撟游???蝞?蝣綽??頝?3??隞乩?嚗?            start_3y = datetime.now() - timedelta(days=3*365)
            start_str = start_3y.strftime("%Y-%m-%d")
            url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=%s&start_date=%s&end_date=%s" % (sid, start_str, DATE_STR)
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=10)
            j = json.loads(resp.read().decode("utf-8"))

            revenue_data = ""
            yoy_growth = ""
            if j.get("status") == 200 and j.get("data"):
                data = sorted(j["data"], key=lambda x: (x["revenue_year"], x["revenue_month"]))
                if data:
                    latest = data[-1]
                    rev = latest["revenue"]
                    ym = "%d-%02d" % (latest["revenue_year"], latest["revenue_month"])
                    rev_str = "%.1fB" % (rev / 1e8) if rev > 1e8 else "%.0fW" % (rev / 1e4)
                    revenue_data = "%s %s" % (ym, rev_str)
                    if len(data) >= 13:
                        prev = data[-13]["revenue"]
                        if prev > 0:
                            yoy = (rev - prev) / prev * 100
                            yoy_growth = "%+.1f%%" % yoy

            # Price from yfinance
            price = ""
            change_pct = ""
            try:
                from ticker_fix import get_yfinance_ticker
                import yfinance as yf
                ticker_str = get_yfinance_ticker(sid)
                t = yf.Ticker(ticker_str)
                hist = t.history(period="5d")
                if hist is not None and len(hist) > 0:
                    close = float(hist['Close'].iloc[-1])
                    price = "%.0f" % close if close > 100 else "%.2f" % close
                    if len(hist) > 1:
                        prev_close = float(hist['Close'].iloc[-2])
                        cp = (close - prev_close) / prev_close * 100
                        change_pct = "%+.2f%%" % cp
            except:
                pass

            fundamentals[sid] = {
                "stock_id": sid, "stock_name": sname,
                "update_date": DATE_STR, "price": price,
                "change_pct": change_pct, "revenue": revenue_data,
                "yoy_growth": yoy_growth, "pe_ratio": "", "eps": "",
            }
            count += 1
            if count % 10 == 0:
                print("  ... %d/%d done" % (count, len(WATCH_STOCKS)))

        except:
            if sid in fundamentals:
                fundamentals[sid]["update_date"] = DATE_STR
            continue

    with open(FUND_FILE, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["stock_id", "stock_name", "update_date", "price",
                       "change_pct", "revenue", "yoy_growth", "pe_ratio", "eps"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for sid in sorted(fundamentals.keys()):
            writer.writerow(fundamentals[sid])

    print("  Saved %d stocks: %s" % (len(fundamentals), FUND_FILE))
    return fundamentals


# =========================================================
#  Step 3: Generate Potential Candidates
# =========================================================
# =========================================================
def generate_candidates(accumulation, fundamentals):
    """全市場投信掃描 + 黑馬輸出（給晨報用 JSON）。

    此流程以盤後16:30 TWSE T86 投信買超資料為核心，篩選出候補潛力股。
    產出 `Potential_Candidates.txt` 與 `trust_scan_latest.json`，供晨報與盤中監控使用。
    """
    print("")
    print("=" * 60)
    print("  [Step 3] 全市場投信連續買超掃描")
    print("  %s" % TIME_TAG)
    print("=" * 60)
    
    # 抓最近 5 個交易日的全市場投信資料
    trade_dates = []
    for db in range(1, 8):
        d = NOW - timedelta(days=db)
        if d.weekday() < 5:
            trade_dates.append(d.strftime("%Y%m%d"))
            if len(trade_dates) >= 5:
                break
    
    print("  掃描交易日: %s" % ", ".join(trade_dates))
    
    # 全市場連買分析
    all_data = {}
    all_name = {}
    
    for td in trade_dates:
        url = "https://www.twse.com.tw/fund/T86?response=json&date=%s&selectType=ALL" % td
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=15)
            j = json.loads(resp.read().decode("utf-8"))
            if j.get("stat") != "OK":
                continue
            for row in j.get("data", []):
                sid = row[0]
                name = row[1].strip()
                trust_net = int(row[10].replace(",", ""))
                foreign_net = int(row[4].replace(",", ""))
                all_name[sid] = name
                if sid not in all_data:
                    all_data[sid] = {"days": 0, "total_trust": 0, "total_foreign": 0}
                if trust_net > 0:
                    all_data[sid]["days"] += 1
                    all_data[sid]["total_trust"] += trust_net
                all_data[sid]["total_foreign"] += foreign_net
        except:
            pass
    
    watch_19 = ['2436','2337','5351','3673','3711','4958','3042','2454','2317',
                '3443','3661','3035','3231','2382','3017','2451','8150','2344','6770']
    
    # 篩選：連買 3+ 天，總額 > 50 萬
    black_horses = []
    for sid, d in all_data.items():
        if d["days"] >= 3 and d["total_trust"] >= 500000:
            black_horses.append({
                "sid": sid,
                "name": all_name.get(sid, "?"),
                "days": d["days"],
                "total_trust": d["total_trust"],
                "total_foreign": d["total_foreign"],
                "is_watch": sid in watch_19,
            })
    
    black_horses.sort(key=lambda x: x["total_trust"], reverse=True)
    
    # 同時看持股的被賣狀況
    watch_sold = []
    latest_td = trade_dates[0] if trade_dates else None
    if latest_td:
        url = "https://www.twse.com.tw/fund/T86?response=json&date=%s&selectType=ALL" % latest_td
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=15)
            j = json.loads(resp.read().decode("utf-8"))
            if j.get("stat") == "OK":
                for row in j.get("data", []):
                    sid = row[0]
                    if sid in watch_19:
                        tn = int(row[10].replace(",", ""))
                        fn = int(row[4].replace(",", ""))
                        if tn < 0:
                            watch_sold.append({"sid": sid, "name": row[1].strip(), "trust_net": tn, "foreign_net": fn})
        except:
            pass
    
    # 產出文字檔
    out_lines = []
    out_lines.append("=" * 60)
    out_lines.append("  ** 全市場投信連續買超掃描結果")
    out_lines.append("  %s" % TIME_TAG)
    out_lines.append("=" * 60)
    out_lines.append("")
    out_lines.append("  篩選條件: 連買 >= 3 天, 累計買超 > 50 萬")
    out_lines.append("  掃描區間: %s ~ %s" % (trade_dates[-1] if trade_dates else "?", trade_dates[0] if trade_dates else "?"))
    out_lines.append("  ")
    out_lines.append("  %6s %-10s %5s %12s %11s %s" % ("代號", "名稱", "連買", "累計買超", "外資", "標記"))
    out_lines.append("  " + "-" * 60)
    
    for h in black_horses[:40]:
        tag = ""
        if h["is_watch"]:
            tag = "【持股】"
        elif h["total_trust"] >= 5000000:
            tag = "***"
        elif h["total_trust"] >= 2000000:
            tag = "**"
        elif h["total_trust"] >= 1000000:
            tag = "*"
        out_lines.append("  %6s %-10s %2d天 %10d %+9d %s" % (
            h["sid"], h["name"], h["days"], h["total_trust"], h["total_foreign"], tag))
    
    if watch_sold:
        out_lines.append("")
        out_lines.append("  ** 持股中被投信賣超的：")
        out_lines.append("  " + "-" * 40)
        for s in sorted(watch_sold, key=lambda x: x["trust_net"]):
            out_lines.append("  %6s %-10s 賣超 %+d" % (s["sid"], s["name"], s["trust_net"]))
    
    out_lines.append("")
    out_lines.append("=" * 60)
    
    text = "\n".join(out_lines)
    with open(CANDIDATE_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print("  Saved: %s" % CANDIDATE_FILE)
    
    # 輸出 JSON 給晨報用
    json_out = {
        "update_time": TIME_TAG,
        "scan_dates": trade_dates,
        "trust_top40": [h for h in black_horses[:40]],
        "watch_sold": watch_sold,
    }
    json_path = os.path.join(OUTPUT_DIR, "trust_scan_latest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2)
    print("  Saved: %s" % json_path)
    
    return text


def run_full_update():
    """Execute full database update pipeline"""
    print("")
    print("=" * 60)
    print("  Lobster Full Market Database Update")
    print("  %s" % NOW.strftime('%Y-%m-%d %H:%M'))
    print("=" * 60)

    accumulation = update_sitc_accumulation()
    fundamentals = update_fundamentals()
    candidates_text = generate_candidates(accumulation, fundamentals)

    print("")
    print("=" * 60)
    print("  UPDATE COMPLETE")
    print("  Output files:")
    print("    %s" % SITC_FILE)
    print("    %s" % FUND_FILE)
    print("    %s" % CANDIDATE_FILE)
    print("=" * 60)

    return candidates_text


# ════════════════════════════════════════════════════════
#  🧠 AI 自我聯想模組（DeepSeek引擎）
# ════════════════════════════════════════════════════════

def ai_industry_theme(stock_id, stock_name, ds_key=None):
    """
    放棄外部新聞API，直接讓AI根據基本面進行產業聯想。
    回傳：一句話（15字內）的核心飆股題材，例如『CoWoS散熱獨家供應商』
    """
    if ds_key is None:
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not ds_key:
        return "AI聯想待設定"
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位精通台股高科技產業的頂級分析師。請用一句話（15字以內）點出該個股目前在市場上最核心的飆股題材或主力炒作關鍵字，例如『CoWoS散熱獨家供應商』或『USB-PD晶片大廠』。絕對不要廢話，直接回答題材內容。"},
                {"role": "user", "content": f"個股名稱：{stock_name}，代號：{stock_id}"}
            ],
            temperature=0.2,
            timeout=10
        )
        
        return response.choices[0].message.content.strip()[:20]
    except Exception as e:
        return f"AI離線({str(e)[:15]})"


def batch_ai_theme(all_results):
    """批量對所有監控標的做AI產業聯想"""
    print("\n" + "=" * 60)
    print("  🧠 AI產業聯想（DeepSeek自我思考）")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("=" * 60)
    
    # 核心18檔（第1層+第2層）
    stocks = [
        ("2436","偉詮電"),("2337","旺宏"),("5351","鈺創"),
        ("3673","TPK-KY"),("3711","日月光"),("4958","臻鼎-KY"),("3042","晶技"),
        ("2454","聯發科"),("2317","鴻海"),
        ("3443","創意"),("3661","世芯"),("3035","智原"),
        ("3231","緯創"),("2382","廣達"),("3017","奇鋐"),("2451","創見"),("8150","南茂"),
    ]
    
    themes = {}
    for sid, sname in stocks:
        theme = ai_industry_theme(sid, sname)
        themes[sid] = theme
        print("  %s %s → %s" % (sid, sname, theme))
    
    # 儲存
    path = os.path.join(OUTPUT_DIR, "ai_themes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"update_time": datetime.now().strftime("%Y-%m-%d %H:%M"), "themes": themes}, f, ensure_ascii=False, indent=2)
    print("  💾 已儲存: %s" % path)
    
    return themes


if __name__ == "__main__":
    text = run_full_update()
    print(text)
    
    # 跑AI產業聯想
    batch_ai_theme({})
