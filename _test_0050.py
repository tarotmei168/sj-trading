import sys, requests
sys.path.insert(0, 'src/sj_trading')
from calc_tech import read_local_csv
data = read_local_csv('0050')
if data:
    print('本機有資料:', len(data))
else:
    print('本機無資料')
# 試 FinMind
url = 'https://api.finmindtrade.com/api/v4/data'
params = {'dataset': 'TaiwanStockPrice', 'data_id': '0050', 'start_date': '2026-05-01', 'end_date': '2026-07-21'}
resp = requests.get(url, params=params, timeout=10)
r = resp.json()
if r.get('status') == 200 and r.get('data'):
    items = r['data']
    print(f'FinMind 有 {len(items)} 筆')
    print('最後:', [(d['date'], d['close']) for d in items[-5:]])
else:
    print('FinMind 抓不到')
