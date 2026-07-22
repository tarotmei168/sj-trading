import requests
from datetime import datetime
today = datetime.now().strftime('%Y%m%d')

# Try TWSE other endpoints for 投信
endpoints = [
    f'https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={today}',
    f'https://www.twse.com.tw/fund/MI_QFIIS?response=json&date={today}',
    f'https://www.twse.com.tw/fund/FIIT8?response=json&date={today}',
    f'https://www.twse.com.tw/fund/FIIT8?response=json&date={today}&selectType=T',
]
for u in endpoints:
    try:
        r = requests.get(u, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        ct = r.headers.get('Content-Type','')
        name = u.split('?')[0].split('/')[-1]
        if 'json' in ct:
            d = r.json()
            print(f'{name}: stat={d.get("stat","?")} rows={len(d.get("data",[]))}')
        else:
            print(f'{name}: not json ({ct[:30]}) len={len(r.text)}')
    except Exception as e:
        name = u.split('?')[0].split('/')[-1]
        print(f'{name}: {e}')

# Also check: fund Daily 三大法人買賣超金額
url = f'https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={today}'
try:
    r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
    d = r.json()
    if d.get('data'):
        for row in d['data']:
            print(f'BFI82U row: {row}')
except Exception as e:
    print(f'BFI82U detail: {e}')
