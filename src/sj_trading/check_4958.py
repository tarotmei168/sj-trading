"""检查 4958 臻鼎KY 即时状态"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def compute_kd(closes, highs, lows, kp=3):
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

sid = '4958'; name = '臻鼎KY'
c = api.Contracts.Stocks[sid]

print(f'=== {name}({sid}) 即时 {'{:>}'.format(datetime.now().strftime("%H:%M"))} ===')
snaps = api.snapshots([c])
if snaps:
    s = snaps[0]
    print(f'  收盘: {s.close}  涨跌: {s.change_price:+.2f} ({s.change_rate:+.2f}%)')
    print(f'  开:{s.open} 高:{s.high} 低:{s.low} 量:{s.total_volume}')

end = datetime.now()
start = end - timedelta(days=25)
kbars = api.kbars(contract=c, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
df = pd.DataFrame({'datetime':pd.to_datetime(kbars.ts),'close':kbars.Close,'high':kbars.High,'low':kbars.Low})
df.set_index('datetime',inplace=True)
df_30 = df.resample('30min').agg({'close':'last','high':'max','low':'min'}).dropna()
df_30 = df_30.between_time('09:00','13:30')

c30 = df_30['close'].values; h30 = df_30['high'].values; l30 = df_30['low'].values
k30, d30 = compute_kd(c30, h30, l30)

print(f'\n  30分K KD状态:')
print(f'  最新: K={k30[-1]:.1f} D={d30[-1]:.1f}  {\"金叉🟢\" if k30[-1] > d30[-1] else \"死叉🔴\"}')
print(f'  前根: K={k30[-2]:.1f} D={d30[-2]:.1f}')
print(f'  再前: K={k30[-3]:.1f} D={d30[-3]:.1f}')
if k30[-2] >= d30[-2] and k30[-1] < d30[-1]:
    print(f'  ⚠️ 這根剛死亡交叉！')
elif k30[-2] <= d30[-2] and k30[-1] > d30[-1]:
    print(f'  ⚠️ 這根剛黃金交叉！')

api.logout()
