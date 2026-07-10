# -*- coding: utf-8 -*-
"""
蝝楊?仕銝?嚗inMind API嚗?銝姘摰撠?嚗?+ ?芸??舀?蝺?+ ?漱????
"""
import os, sys, json, urllib.request
from datetime import datetime, timedelta
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NOW = datetime.now()

TARGET_STOCKS = {
    "2481":"撘瑁?","6435":"憭找葉","5425":"?啣?","5289":"摰?",
    "3260":"憡?","8033":"?瑁?","6207":"?瑞?",
    "2317":"暾餅絲","3231":"蝺臬","2382":"撱??",
    "3017":"憟?","2451":"?菔?","3042":"?嗆?",
    "3443":"?菜?","3661":"銝","3035":"?箏?",
    "2454":"?舐蝘?,"3711":"?交???,
    "2337":"?箏?","2344":"?舫??,"2408":"??蝘?,
    "3006":"?嗉悸蝘?,"2059":"撌?","2467":"敹?",
    "3090":"?仿鞎?,"6139":"鈭?","2449":"鈭砍??餃?",
    "8150":"??","2327":"?楊","6213":"?航?",
    "2428":"?","6282":"摨瑁?",
}

def fetch_kline(sid, years=3):
    start = (NOW - timedelta(days=years*365)).strftime("%Y-%m-%d")
    end = NOW.strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (sid, start, end)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status")==200 and j.get("data"):
            return j["data"]
    except:
        pass
    return None

def calc_kd(arr_c, arr_h, arr_l, kp=9, dp=3):
    n = len(arr_c)
    k = np.zeros(n); d = np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1, n):
        ps = max(0, i-kp+1)
        hh = np.max(arr_h[ps:i+1]); ll = np.min(arr_l[ps:i+1])
        rsv = (arr_c[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i] = (dp-1)/dp * k[i-1] + (1/dp)*rsv
        d[i] = (dp-1)/dp * d[i-1] + (1/dp)*k[i]
    return k, d

def analyze(sid, sname, raw_data):
    dates = [d["date"] for d in raw_data]
    c = np.array([float(d["close"]) for d in raw_data], dtype=float)
    h = np.array([float(d["max"]) for d in raw_data], dtype=float)
    l = np.array([float(d["min"]) for d in raw_data], dtype=float)
    v = np.array([int(d.get("Trading_Volume",0)) for d in raw_data], dtype=float)
    
    k, d = calc_kd(c, h, l)
    
    # ?舀?
    days = 20
    recent_low = min(l[-days:])
    recent_avg = np.mean(c[-days:])
    ma20 = np.mean(c[-20:]) if len(c)>=20 else c[-1]
    
    # ?漱????嚗?20?伐?
    vol_buckets = {}
    for i in range(-days, 0):
        bucket = round(c[i]/5)*5
        vol_buckets[bucket] = vol_buckets.get(bucket,0) + v[i]
    vol_cluster = max(vol_buckets, key=vol_buckets.get) if vol_buckets else recent_low
    
    supports = [
        ("餈?0?交?雿?, round(recent_low,1)),
        ("餈?0?亙???, round(recent_avg,1)),
        ("?漱????", round(vol_cluster,1)),
        ("??MA20", round(ma20,1)),
    ]
    
    cur_price = c[-1]
    hit = [name for name, price in supports if cur_price <= price*1.03]
    
    return {
        "sid": sid, "name": sname, "price": round(cur_price,1),
        "date": dates[-1], "k": round(k[-1],1), "d": round(d[-1],1),
        "k_up": k[-1] > d[-1],
        "gc": bool(k[-1]>d[-1] and k[-2]<=d[-2]) if len(k)>=2 else False,
        "dc": bool(k[-1]<d[-1] and k[-2]>=d[-2]) if len(k)>=2 else False,
        "supports": supports, "hit_support": hit,
        "vol_cluster": round(vol_cluster,1),
    }

print("="*70)
print("  FinMind 蝝楊?仕銝? + ?芸??舀?蝺?)
print("  %s" % NOW.strftime('%Y-%m-%d %H:%M'))
print("="*70)

all_results = {}
for sid, sname in TARGET_STOCKS.items():
    print("  %s %s..." % (sid, sname), end=" ", flush=True)
    raw = fetch_kline(sid)
    if raw is None or len(raw) < 30:
        print("??)
        continue
    print("%d蝑? % len(raw))
    r = analyze(sid, sname, raw)
    all_results[sid] = r

# 頛詨?勗?
print()
print("="*70)
print("  ?? ?急??摰?勗?")
print("="*70)

for sid in sorted(all_results.keys()):
    r = all_results[sid]
    kd_str = "K>D憭" if r["k_up"] else "K<D蝛粹"
    if r["gc"]: kd_str += " 潃???
    if r["dc"]: kd_str += " ??甇餃?"
    hit_str = " 潃?? if r["hit_support"] else ""
    print()
    print("  %s %s %s ??.0f K=%.1f D=%.1f%s" % (
        sid, r["name"], kd_str, r["price"], r["k"], r["d"], hit_str))
    print("    ?舀?: %s" % " | ".join(["%s%.0f"%(n,p) for n,p in r["supports"]]))
    if r["hit_support"]:
        print("    ??閫詨?: %s" % ", ".join(r["hit_support"]))

# 摮?
out = os.path.join(OUTPUT_DIR, "support_analysis.json")
with open(out, "w", encoding="utf-8") as f:
    simple = {k: {kk:vv for kk,vv in v.items() if kk!="supports"} for k,v in all_results.items()}
    # json.dump(simple, f, ensure_ascii=False, indent=2)
print("\n  ? 撌脣摮? %s" % out)

# 摮SV蝯血?皜祉
csv_path = os.path.join(OUTPUT_DIR, "FinMind_DailyK_3years.csv")
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    import csv
    w = csv.writer(f)
    w.writerow(["stock_id","date","open","high","low","close","volume"])
    for sid in TARGET_STOCKS:
        raw = fetch_kline(sid)
        if raw:
            for d in raw:
                w.writerow([sid, d["date"], d["open"], d["max"], d["min"], d["close"], d.get("Trading_Volume",0)])
print("  ? ?仕??鞈?: %s" % csv_path)
