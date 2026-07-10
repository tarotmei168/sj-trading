import sys, urllib.request, json, os
sys.stdout.reconfigure(encoding='utf-8')
H = {'User-Agent': 'Mozilla/5.0'}

# T89 - 個股三大法人每日買賣超
# 格式: 年(西元) 月 日 股票代號
for date_str in ['20260703', '20260601', '20260101']:
    url = f'https://www.twse.com.tw/fund/T89?response=json&date={date_str}&stockNo=2337'
    req = urllib.request.Request(url, headers=H)
    raw = urllib.request.urlopen(req, timeout=10).read()
    text = raw.decode('utf-8', errors='replace')
    print(f'\n=== T89 date={date_str} ===')
    print(text[:500])

# 試試不同 date 格式
print('\n=== Trying different endpoints ===')
import time
tomorrow = '20260707'  # future date to get full month
url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20260601&stockNo=2337'
req = urllib.request.Request(url, headers=H)
raw = urllib.request.urlopen(req, timeout=10).read()
d = json.loads(raw)
print(f'June 2026: count={d.get("total",0)}')
if d.get('data'):
    print(f'  first={d["data"][0]}')
    print(f'  last={d["data"][-1]}')

# 試試 2025
url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20250701&stockNo=2337'
req = urllib.request.Request(url, headers=H)
raw = urllib.request.urlopen(req, timeout=10).read()
d = json.loads(raw)
print(f'July 2025: count={d.get("total",0)}')
if d.get('data'):
    print(f'  first={d["data"][0]}')
    print(f'  last={d["data"][-1]}')

# 檢查最多可以回推到多遠
print('\n=== Testing date range ===')
for year in [2023, 2022, 2021, 2020]:
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={year}0701&stockNo=2337'
    try:
        req = urllib.request.Request(url, headers=H)
        raw = urllib.request.urlopen(req, timeout=10).read()
        d = json.loads(raw)
        print(f'{year}: count={d.get("total",0)}')
    except Exception as e:
        print(f'{year}: ERROR {e}')

print('\nDone')
