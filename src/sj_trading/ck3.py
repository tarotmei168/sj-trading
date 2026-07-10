import sys, urllib.request, json, os
sys.stdout.reconfigure(encoding='utf-8')
H = {'User-Agent': 'Mozilla/5.0'}

# 試試不同的個股三大法人 API
tests = [
    ('T86 selectType=股票代碼', 
     'https://www.twse.com.tw/fund/T86?response=json&date=20260703&selectType=2337'),
    ('STOCK_DAY_ALL (三大法人版)', 
     'https://www.twse.com.tw/fund/STOCK_DAY_ALL?response=json&date=20260703'),
]

for name, url in tests:
    print(f'\n=== {name} ===')
    try:
        req = urllib.request.Request(url, headers=H)
        raw = urllib.request.urlopen(req, timeout=10).read()
        d = json.loads(raw)
        print(f'stat={d.get("stat","?")} total={d.get("total",0)}')
        print(f'fields={d.get("fields",[])}')
        if d.get('data'):
            for row in d['data']:
                if '2337' in str(row):
                    print(f'合晶/旺宏: {row}')
                    break
            print(f'第一筆: {d["data"][0]}')
            print(f'最後一筆: {d["data"][-1]}')
    except Exception as e:
        print(f'ERROR: {e}')

# 另外試試兩年前三大法人
print('\n=== 2024 三大法人全市場 ===')
url = 'https://www.twse.com.tw/fund/T86?response=json&date=20240703&selectType=ALL'
req = urllib.request.Request(url, headers=H)
raw = urllib.request.urlopen(req, timeout=10).read()
d = json.loads(raw)
print(f'total={d.get("total",0)}')

# 結論
print('\n=== 可用資料源總結 ===')
print('1. STOCK_DAY: 個股日K線 (2020至今)')
print('   - 日期, 張數, 金額, 開高低收, 漲跌, 筆數')
print('2. T86: 三大法人買賣超 (全市場, 單日)')
print('   - 外資/投信/自營商 買進/賣出/買賣超 股數')
print('   - 只能用 selectType=ALL 拉全市場，再濾出個股')
print('3. 個股三大法人歷史: T86 每天拉全市場再濾個股')
print('   - 可以每天爬一次存起來')
print('')
print('回測方案: 用 STOCK_DAY 抓日K線算KD')
print('用 T86 抓每日三大法人買賣超')
