# -*- coding: utf-8 -*-
"""快速查 FinMind 日K + KD + 支撐"""
import urllib.request, json
import numpy as np
from datetime import datetime, timedelta

def fetch_kline(sid, years=3):
    end = datetime.now()
    start = end - timedelta(days=years*365)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (
        sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status")==200 and j.get("data"):
            return j["data"]
    except:
        pass
    return None

def calc_kd(c, h, l):
    n = len(c)
    k = np.zeros(n); d = np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-9+1)
        hh=np.max(h[ps:i+1]); ll=np.min(l[ps:i+1])
        rsv=(c[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(2/3)*k[i-1]+(1/3)*rsv
        d[i]=(2/3)*d[i-1]+(1/3)*k[i]
    return k, d

targets = [('2317','鸿海'),('3231','纬创'),('2382','广达'),('2451','创见'),('3017','奇鋐')]
print()
print("FinMind 纯净日K (与三竹对齐)")
print("=" * 60)

for sid, name in targets:
    raw = fetch_kline(sid)
    if not raw or len(raw) < 30:
        print("%s %s: 无资料" % (sid, name))
        continue
    
    c = np.array([float(d["close"]) for d in raw], dtype=float)
    h = np.array([float(d["max"]) for d in raw], dtype=float)
    l = np.array([float(d["min"]) for d in raw], dtype=float)
    v = np.array([int(d.get("Trading_Volume",0)) for d in raw], dtype=float)
    k, d = calc_kd(c, h, l)
    
    kd_str = "K>D多头" if k[-1] > d[-1] else "K<D空头"
    if k[-1] > d[-1] and k[-2] <= d[-2]: kd_str = "K>D多头 GC!"
    if k[-1] < d[-1] and k[-2] >= d[-2]: kd_str = "K<D空头 DC!"
    
    # 支撑
    low20 = min(l[-20:])
    avg20 = round(np.mean(c[-20:]), 1)
    ma20 = round(np.mean(c[-20:]), 1)
    
    buckets = {}
    for i in range(-20, 0):
        bk = round(c[i]/5)*5
        buckets[bk] = buckets.get(bk,0) + v[i]
    vol_cluster = max(buckets, key=buckets.get) if buckets else c[-1]
    
    cur = c[-1]
    hit = []
    if cur <= low20 * 1.03: hit.append("low20")
    if cur <= avg20 * 1.03: hit.append("avg20")
    if cur <= ma20 * 1.03: hit.append("ma20")
    if cur <= vol_cluster * 1.03: hit.append("volCluster")
    
    print()
    print("%s %s" % (sid, name))
    print("  收%.1f | K=%.1f D=%.1f %s" % (cur, k[-1], d[-1], kd_str))
    print("  支撑: %.0f(20日低) %.0f(20日均) %.0f(量密集) %.0f(MA20)" % (low20, avg20, vol_cluster, ma20))
    if hit:
        print("  ✅ 已触及支撑: %s" % ", ".join(hit))
    print("  挂单建议: 买 %.0f 挂著等" % low20)
