import os, sys
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
import numpy as np
from datetime import datetime

ak = os.environ.get('SJ_API_KEY', '')
sk = os.environ.get('SJ_SEC_KEY', '')
api = sj.Shioaji(simulation=True)
api.login(api_key=ak, secret_key=sk)

now = datetime.now()
start = datetime(now.year, now.month, now.day, 8, 45)

targets = {'2317':'HH','3231':'WC','2382':'GD','2451':'CJ','5351':'YC'}

for sid, sname in targets.items():
    contract = api.Contracts.Stocks[sid]
    kbars = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=now.strftime('%Y-%m-%d'))
    if not hasattr(kbars, 'Close') or len(kbars.Close) == 0:
        print(f"{sid}: no data")
        continue
    
    interval = 15  # 15分K
    bars = []; cur = None
    for i in range(len(kbars.Close)):
        t = datetime.fromtimestamp(kbars.ts[i]/1e9)
        slot = t.hour*60 + t.minute
        slot_n = (slot // interval) * interval
        key = t.strftime('%Y%m%d') + f'{slot_n:03d}'
        c = float(kbars.Close[i]); h = float(kbars.High[i]); l = float(kbars.Low[i]); v = float(kbars.Volume[i])
        if cur is None or cur[0] != key:
            if cur: bars.append(cur)
            cur = [key, t, c, h, l, v, v]
        else:
            cur[3] = max(cur[3], h); cur[4] = min(cur[4], l); cur[5] = c; cur[6] += v
    if cur: bars.append(cur)
    
    cls = np.array([b[2] for b in bars], dtype=float)
    his = np.array([b[3] for b in bars], dtype=float)
    los = np.array([b[4] for b in bars], dtype=float)
    n = len(cls); k=np.zeros(n); d=np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-9+1); hh=np.max(his[ps:i+1]); ll=np.min(los[ps:i+1])
        rsv=(cls[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(2/3)*k[i-1]+(1/3)*rsv; d[i]=(2/3)*d[i-1]+(1/3)*k[i]
    
    action = ''
    if k[-1] > d[-1] and k[-2] <= d[-2]: action = 'GC!'
    elif k[-1] < d[-1] and k[-2] >= d[-2]: action = 'DC!'
    
    kd_str = 'K>D' if k[-1] > d[-1] else 'K<D'
    print(f"{sid} {sname} C{cls[-1]:.0f} K{k[-1]:.1f} D{d[-1]:.1f} {kd_str} {action}")
    for j in range(-5, 0):
        print(f"  {bars[j][1].strftime('%H:%M')} C{cls[j]:.0f} K{k[j]:.1f} D{d[j]:.1f} {'K>D' if k[j]>d[j] else 'K<D'}")

api.logout()
