import requests, json

print('=== 1. 證交所除權息 ===')
url = 'https://www.twse.com.tw/exchangeReport/TWT48U?response=json&strDate=20260701&endDate=20260831'
r = requests.get(url, timeout=15).json()
if r.get('stat') == 'OK' and r.get('data'):
    for row in r['data']:
        code = row[0]
        name = row[1]
        ex_date = row[3]
        cash = row[4]
        stock = row[5]
        if code in ['2330','2454','2317','3711','3042','4958','8150','2337','5351','2436','3673','0050','2382','3231','3443','3661','3035','3017','2451','2344','6770']:
            print(f'  {code} {name}: 除息{ex_date} 現金{cash} 股票{stock}')

print()
print('=== 2. FinMind 月營收公告截止日 ===')
print('  TWSE規定: 每月10日前公告上月營收')
print('  若遇假日順延')

print()
print('=== 3. 美國總經固定排程 ===')
# 這些都是固定可預測的
print('  FOMC: 1/29, 3/19, 5/7, 6/18, 7/30, 9/17, 11/5, 12/17')
print('  非農(NFP): 每月的第一個星期五')
print('  CPI: 每月13~15日左右')
print('  PCE: 每月最後一個週五左右')
print('  GDP: 1月/4月/7月/10月 下旬初值')

print()
print('=== 4. 投信季底作帳日 ===')
print('  投信季底結帳: 3/31, 6/30, 9/30, 12/31')
print('  投信作帳行情: 該月最後5~10個交易日')
