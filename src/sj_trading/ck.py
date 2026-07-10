import sys, urllib.request, json, os
sys.stdout.reconfigure(encoding='utf-8')
H = {'User-Agent': 'Mozilla/5.0'}

for sid in ['2337','2436','5351','8150']:
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20260703&stockNo={sid}'
    req = urllib.request.Request(url, headers=H)
    raw = urllib.request.urlopen(req, timeout=10).read()
    d = json.loads(raw)
    data = d.get('data', [])
    fields = d.get('fields', [])
    print(f'{sid}: fields={fields}')
    print(f'  count={d.get("total",0)} last={data[-1] if data else "N/A"}')

url2 = 'https://www.twse.com.tw/fund/T86?response=json&date=20260703&selectType=ALL'
req2 = urllib.request.Request(url2, headers=H)
raw2 = urllib.request.urlopen(req2, timeout=10).read()
d2 = json.loads(raw2)
print(f'\nT86 fields={d2.get("fields",[])} count={d2.get("total",0)}')
for row in d2.get('data', []):
    if '2337' in str(row):
        print(f'Wanghong 2337: {row}')
        break

url4 = 'https://www.twse.com.tw/fund/T89?response=json&date=20260703&stockNo=2337'
req4 = urllib.request.Request(url4, headers=H)
raw4 = urllib.request.urlopen(req4, timeout=10).read()
d4 = json.loads(raw4)
print(f'\nT89 fields={d4.get("fields",[])} count={d4.get("total",0)}')
if d4.get('data'):
    print(f'first: {d4["data"][0]}')
    print(f'last: {d4["data"][-1]}')

# Try fetching more historical data (older date)
url5 = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20240101&stockNo=2337'
req5 = urllib.request.Request(url5, headers=H)
raw5 = urllib.request.urlopen(req5, timeout=10).read()
d5 = json.loads(raw5)
data5 = d5.get('data', [])
print(f'\n2024 Jan 2337: count={d5.get("total",0)} first={data5[0] if data5 else "N/A"} last={data5[-1] if data5 else "N/A"}')

print('\nDone')
