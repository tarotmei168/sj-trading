import requests
from datetime import datetime, timedelta
url = 'https://www.twse.com.tw/fund/T86'
t = datetime.now().strftime('%Y%m%d')
y = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
for dt in [t, y]:
    r = requests.get(url, params={'response':'json','date':dt}, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
    d = r.json()
    stat = d.get('stat', '?')
    rows = len(d.get('data', []))
    title = d.get('title', '')
    print(f'{dt}: stat={stat} rows={rows} title={title}')
