"""檢查 TWSE 歷史資料格式"""
import sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8')
H = {'User-Agent': 'Mozilla/5.0'}

# 1. 日K線
print('=== 1. TWSE 日K線 (STOCK_DAY) ===')
for sid in ['2337', '2436', '5351', '8150']:
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20260703&stockNo={sid}'
    req = urllib.request.Request(url, headers=H)
    raw = urllib.request.urlopen(req, timeout=10).read()
    d = json.loads(raw)
    data = d.get('data', [])
    print(f'{sid}: {d.get("fields",[])}')
    print(f'  筆數={d.get("total",0)} 最後一筆={data[-1] if data else "N/A"}')

# 2. 三大法人買賣超
print('\n=== 2. TWSE 三大法人買賣超 ===')
url2 = 'https://www.twse.com.tw/fund/T86?response=json&date=20260703&selectType=ALL'
req2 = urllib.request.Request(url2, headers=H)
raw2 = urllib.request.urlopen(req2, timeout=10).read()
d2 = json.loads(raw2)
print(f'欄位: {d2.get("fields",[])}')
print(f'筆數: {d2.get("total",0)}')
# 找旺宏
for row in d2.get('data', []):
    if '2337' in str(row):
        print(f'旺宏: {row}')
        break

# 3. 個股三大法人歷史（每日）
print('\n=== 3. 個股三大法人明細 ===')
url3 = f'https://www.twse.com.tw/fund/T86?response=json&date=20260703&selectType=2337'
req3 = urllib.request.Request(url3, headers=H)
raw3 = urllib.request.urlopen(req3, timeout=10).read()
d3 = json.loads(raw3)
print(f'stat={d3.get("stat","?")}  total={d3.get("total",0)}')
if d3.get('data'):
    print(f'第一筆: {d3[\"data\"][0]}')

# 4. 試試個股三大法人每日 (T89)
print('\n=== 4. 三大法人買賣超個股 (T89) ===')
url4 = 'https://www.twse.com.tw/fund/T89?response=json&date=20260703&stockNo=2337'
req4 = urllib.request.Request(url4, headers=H)
raw4 = urllib.request.urlopen(req4, timeout=10).read()
d4 = json.loads(raw4)
print(f'stat={d4.get("stat","?")} fields={d4.get("fields",[])} total={d4.get("total",0)}')
if d4.get('data'):
    print(f'第一筆: {d4[\"data\"][0]}')
    print(f'最後一筆: {d4[\"data\"][-1]}')

print('\n✅ 查詢完成')
