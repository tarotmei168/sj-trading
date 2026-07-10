# -*- coding: utf-8 -*-
"""测试：全市场日K + 5档3年数据"""
import urllib.request, json, os, csv
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
os.makedirs(DB, exist_ok=True)

UA = "Mozilla/5.0"

def fetch_day(date_str):
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&start_date=%s&end_date=%s" % (date_str, date_str)
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    resp = urllib.request.urlopen(req, timeout=60)
    j = json.loads(resp.read().decode("utf-8"))
    return j.get("data", []) if j.get("status")==200 else []

def fetch_stock_3y(sid):
    end = datetime.now()
    start = end - timedelta(days=3*365)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    resp = urllib.request.urlopen(req, timeout=15)
    j = json.loads(resp.read().decode("utf-8"))
    return j.get("data", []) if j.get("status")==200 else []

print("="*60)
print("  核心引擎测试")
print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
print("="*60)

# 1. 全市场7/6日K
print("\n[1] 全市场日K 2026/07/06:")
data = fetch_day("2026-07-06")
if data:
    print("  %d 笔" % len(data))
    # 存檔
    path = os.path.join(DB, "market_daily_20260706.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stock_id","open","high","low","close","volume"])
        for d in data:
            w.writerow([d["stock_id"], d["open"], d["max"], d["min"], d["close"], d.get("Trading_Volume",0)])
    print("  已储存: %s" % path)
else:
    print("  失败，改抓7/3")
    data = fetch_day("2026-07-03")
    if data:
        print("  7/3: %d 笔" % len(data))

# 2. 5档3年数据
print("\n[2] 3年日K下载:")
for sid in ["2317","3231","2382","2451","3017"]:
    d = fetch_stock_3y(sid)
    if d and len(d) > 100:
        c = d[-1]["close"]
        print("  %s: %d笔 收%s ✅" % (sid, len(d), c))
        path = os.path.join(DB, "%s_3y.csv" % sid)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date","open","high","low","close","volume"])
            for r in d:
                w.writerow([r["date"], r["open"], r["max"], r["min"], r["close"], r.get("Trading_Volume",0)])
    else:
        print("  %s: 无资料 ❌" % sid)

print("\n✅ 测试完成")
