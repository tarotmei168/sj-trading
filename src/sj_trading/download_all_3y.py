# -*- coding: utf-8 -*-
"""下載所有監控標的3年日K（FinMind - 與三竹對齊）"""
import urllib.request, json, os, csv
from datetime import datetime, timedelta

UA = "Mozilla/5.0"
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
os.makedirs(DB, exist_ok=True)

STOCKS = {
    # ── 核心持股 11 檔 ──
    "2436":"伟诠电","2337":"旺宏","5351":"钰创",
    "3673":"TPK","3711":"日月光","4958":"臻鼎",
    "3042":"晶技","2454":"联发科","2317":"鸿海",
    "8150":"南茂","2330":"台积电",
    # ── 潛力股 / 輔助觀察（全市場有可能進投信掃描 TOP40 的）──
    "1303":"南亚","1216":"统一","6505":"台塑化","1402":"远东新",
    "2313":"华通","3037":"欣兴","8046":"南电","6213":"联茂",
    "2449":"京元电子","2409":"友达","2474":"可成","2412":"中华电",
    "3702":"大联大","2633":"台湾高铁","2912":"统一超",
    "3189":"景硕","2441":"超丰","5434":"崇越",
    "3532":"台胜科","8039":"台虹","5876":"上海商银",
    "3706":"神达","2542":"兴富发","5871":"中租-KY",
    "2880":"华南金","2881":"富邦金","2884":"玉山金",
    "2886":"兆丰金","2887":"台新新光金","2889":"台新金",
    "2890":"永丰金","2892":"第一金","2855":"统一证",
    # ── 舊 watchlist（保留相容性）──
    "3231":"纬创","2382":"广达","2451":"创见","3017":"奇鋐",
    "3443":"创意","3661":"世芯","3035":"智原","2344":"华邦电","2408":"南亚科",
    "6139":"亚翔","2327":"国巨","2481":"强茂","6435":"大中","5425":"台半",
    "5289":"宜鼎","3260":"威刚","8033":"雷虎","6207":"雷科",
    "2059":"川湖","2467":"志圣","3090":"日电贸",
    "3006":"晶豪科","2383":"台光电","2428":"兴勤","6282":"康舒",
    "6770":"力积电",
}

def fetch(sid):
    end = datetime.now(); start = end - timedelta(days=3*365)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    resp = urllib.request.urlopen(req, timeout=15)
    j = json.loads(resp.read().decode("utf-8"))
    return j.get("data",[]) if j.get("status")==200 else []

# ── 自動從投信掃描補下載 ──
TRUST_SCAN = os.path.join(BASE, "output", "trust_scan_latest.json")
if os.path.exists(TRUST_SCAN):
    try:
        with open(TRUST_SCAN, "r", encoding="utf-8") as f:
            scan = json.load(f)
        for h in scan.get("trust_top40", []):
            sid = h["sid"]
            if sid not in STOCKS:
                STOCKS[sid] = h.get("name", "?")
        print("  [自動] 從 trust_scan_latest.json 補了 %d 檔潛力股" % sum(1 for h in scan.get("trust_top40",[]) if h["sid"] not in STOCKS))
    except Exception as e:
        print("  [自動] 讀取 trust_scan_latest.json 失敗: %s" % str(e)[:40])

print("="*60)
print("  下载 %d 档 3年日K (FinMind)" % len(STOCKS))
print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
print("="*60)

ok = 0; fail = 0
for sid, name in STOCKS.items():
    data = fetch(sid)
    if data and len(data) > 50:
        path = os.path.join(DB, "%s_3y.csv" % sid)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date","open","high","low","close","volume"])
            for r in data:
                w.writerow([r["date"], r["open"], r["max"], r["min"], r["close"], r.get("Trading_Volume",0)])
        ok += 1
        print("  %s %s: %d笔 收%s ✅" % (sid, name, len(data), data[-1]["close"]), flush=True)
    else:
        fail += 1
        print("  %s %s: 无资料 ❌" % (sid, name), flush=True)

print()
print("完成: %d/%d ✅, 失败 %d" % (ok, len(STOCKS), fail))
print("储存位置: %s" % DB)
