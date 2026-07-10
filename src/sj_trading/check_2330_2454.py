import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def compute_kd(closes, highs, lows, kp):
    n = len(closes)
    k = np.full(n, 50.0); d = np.full(n, 50.0)
    for i in range(kp, n):
        lo = min(lows[i-kp+1:i+1]); hi = max(highs[i-kp+1:i+1])
        rsv = 50.0
        if hi != lo: rsv = (closes[i] - lo) / (hi - lo) * 100
        k[i] = (2/3)*k[i-1] + (1/3)*rsv
        d[i] = (2/3)*d[i-1] + (1/3)*k[i]
    return k, d

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

for sid, name, kp in [('2330','台積電',7),('2454','聯發科',5)]:
    c = api.Contracts.Stocks[sid]
    snaps = api.snapshots([c])
    if snaps:
        s = snaps[0]
        print(f'\n=== {name}({sid}) @{s.close} ({s.change_price:+.2f}) ===')
    
    end = datetime.now(); start = end - timedelta(days=25)
    kbars = api.kbars(contract=c, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    df = pd.DataFrame({'datetime':pd.to_datetime(kbars.ts),'close':kbars.Close,'high':kbars.High,'low':kbars.Low})
    df.set_index('datetime',inplace=True)
    df_30 = df.resample('30min').agg({'close':'last','high':'max','low':'min'}).dropna()
    df_30 = df_30.between_time('09:00','13:30')
    c30 = df_30['close'].values; h30 = df_30['high'].values; l30 = df_30['low'].values
    k30, d30 = compute_kd(c30, h30, l30, kp)
    print(f'30K KD: K{k30[-1]:.1f} D{d30[-1]:.1f}')
    print(f'prev: K{k30[-2]:.1f} D{d30[-2]:.1f}')
    if k30[-2] >= d30[-2] and k30[-1] < d30[-1]:
        print('>>> 刚死亡交叉')
    elif k30[-2] <= d30[-2] and k30[-1] > d30[-1]:
        print('>>> 刚黄金交叉!')
    elif k30[-1] > d30[-1]:
        print('金叉中')
    else:
        print('死叉中')

api.logout()
