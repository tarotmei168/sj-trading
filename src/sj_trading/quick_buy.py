import os
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

# 核心持股排第一
stocks = [
    ('2436','weiquan'), ('2337','wanghong'), ('5351','yuchuang'),
    ('3673','TPK'), ('3711','riyueguang'), ('4958','zhending'), ('3042','jingji'),
    # ASIC
    ('3443','chuangyi'), ('2454','lianfake'), ('3661','shixin'), ('3035','zhiyuan'),
    # 投信布局
    ('2317','honghai'), ('3231','weichuang'), ('2382','guangda'),
    ('3017','qihong'), ('2451','chuanjian'),
]

print('\n=== 核心持股监控 15分K ===')
print('='*60)
print(f"{'代号':<6} {'名称':<6} {'现价':>6} {'K值':>6} {'D值':>6} {'状态':<8} {'讯号':<8}")
print('='*60)

for sid, sname in stocks:
    contract = api.Contracts.Stocks[sid]
    kbars = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=now.strftime('%Y-%m-%d'))
    if not hasattr(kbars, 'Close') or len(kbars.Close) == 0:
        print(f"{sid:<6} {sname:<6}  无数据")
        continue
    
    interval = 15
    bars = []; cur = None
    for i in range(len(kbars.Close)):
        t = datetime.fromtimestamp(kbars.ts[i]/1e9)
        slot = t.hour*60 + t.minute
        sn = (slot // interval) * interval
        key = t.strftime('%Y%m%d') + f'{sn:03d}'
        c = float(kbars.Close[i]); h = float(kbars.High[i]); l = float(kbars.Low[i])
        if cur is None or cur[0] != key:
            if cur: bars.append(cur)
            cur = [key, t, c, h, l, c]
        else:
            cur[3] = max(cur[3], h); cur[4] = min(cur[4], l); cur[5] = c
    
    if cur and (datetime.now() - cur[1]).seconds < 1800:  # 30分钟内
        bars.append(cur)
    
    if len(bars) < 9:
        print(f"{sid:<6} {sname:<6}  数据不足({len(bars)})")
        continue
    
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
    ov = ''
    if k[-1] < 25: ov = '超卖'
    elif k[-1] > 75: ov = '过热'
    print(f"{sid:<6} {sname:<6} {cls[-1]:>6.0f} {k[-1]:>6.1f} {d[-1]:>6.1f} {kd_str+' '+ov:<8} {action:<8}")

api.logout()
