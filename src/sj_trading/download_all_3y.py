# -*- coding: utf-8 -*-
"""下載所有監控標的3年日K（FinMind - 與三竹對齊）"""
import urllib.request, json, os, csv
from datetime import datetime, timedelta

UA = "Mozilla/5.0"
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
os.makedirs(DB, exist_ok=True)

STOCKS = {
    "2317":"鸿海","3231":"纬创","2382":"广达","2451":"创见","3017":"奇鋐",
    "3042":"晶技","3443":"创意","3661":"世芯","3035":"智原","2454":"联发科",
    "3711":"日月光","5351":"钰创","2337":"旺宏","2344":"华邦电","2408":"南亚科",
    "2436":"伟诠电","3673":"TPK","4958":"臻鼎","6139":"亚翔","8150":"南茂",
    "2327":"国巨","2481":"强茂","6435":"大中","5425":"台半",
    "5289":"宜鼎","3260":"威刚","8033":"雷虎","6207":"雷科",
    "2059":"川湖","2467":"志圣","3090":"日电贸",
    "3006":"晶豪科","2383":"台光电","8046":"南电","6213":"联茂",
    "2449":"京元电子","2428":"兴勤","6282":"康舒",
}

def fetch(sid):
    end = datetime.now(); start = end - timedelta(days=3*365)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    resp = urllib.request.urlopen(req, timeout=15)
    j = json.loads(resp.read().decode("utf-8"))
    return j.get("data",[]) if j.get("status")==200 else []

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
