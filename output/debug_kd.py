import requests, json, numpy as np, talib
from datetime import datetime, timedelta

url = 'https://api.finmindtrade.com/api/v4/data'
params = {
    'dataset': 'TaiwanStockPrice',
    'data_id': '2454',
    'start_date': (datetime.now()-timedelta(days=90)).strftime('%Y-%m-%d'),
    'end_date': datetime.now().strftime('%Y-%m-%d'),
}
resp = requests.get(url, params=params, timeout=10)
d = resp.json()
items = d['data']
print(f"Total days: {len(items)}")
for r in items[-5:]:
    print(f"{r['date']} close={r['close']} max={r['max']} min={r['min']}")

closes = np.array([r['close'] for r in items], dtype=float)
highs = np.array([r['max'] for r in items], dtype=float)
lows = np.array([r['min'] for r in items], dtype=float)
k, d_line = talib.STOCH(highs, lows, closes, fastk_period=9, slowk_period=3, slowd_period=3)
print(f'\n最後10筆K/D:')
for i in range(-10, 0):
    print(f'  K={k[i]:.1f} D={d_line[i]:.1f}')
print(f'\n最後K值: {k[-1]:.1f}, D值: {d_line[-1]:.1f}, 是否金叉: {k[-1]>=d_line[-1]}')
