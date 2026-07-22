import requests
from datetime import datetime, timedelta

today = datetime.now().strftime('%Y%m%d')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

# T85 needs date parameter
url = 'https://www.twse.com.tw/fund/T85'
for dt in [today, yesterday]:
    try:
        r = requests.get(url, params={'response':'json','date':dt}, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        d = r.json()
        print(f'T85({dt}): stat={d.get("stat","?")} rows={len(d.get("data",[]))} title={d.get("title","")}')
        if d.get('data'):
            for row in d['data'][:3]:
                print(f'  {row}')
    except Exception as e:
        print(f'T85({dt}): {e}')

# FinMind institutional investors
print()
url2 = 'https://api.finmindtrade.com/api/v4/data'
params = {
    'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
    'start_date': yesterday,
    'end_date': today,
}
try:
    r = requests.get(url2, params=params, timeout=10)
    d = r.json()
    print(f'FinMind: stat={d.get("status","?")} rows={len(d.get("data",[]))}')
    if d.get('data'):
        for row in d['data'][:5]:
            print(f'  {row}')
except Exception as e:
    print(f'FinMind: {e}')
