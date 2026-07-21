"""
測試證交所/櫃買公開資料來源
"""
import requests, json, csv, io
from datetime import datetime, timedelta

print("="*60)
print("1. 證交所 除權息預告表")
print("="*60)
# 證交所除權息
url = 'https://www.twse.com.tw/exchangeReport/TWT48U'
params = {'response': 'json', 'strDate': '20260701', 'endDate': '20260831'}
try:
    r = requests.get(url, params=params, timeout=10).json()
    if r.get('stat') == 'OK' and r.get('data'):
        print(f'  共 {len(r["data"])} 筆')
        for row in r['data'][:5]:
            print(f'    {row[0]} {row[1]} {row[3]} 股利={row[4]}')
    else:
        print(f'  回傳: {r.get(\"stat\", \"?\")}')
except Exception as e:
    print(f'  失敗: {e}')

print()
print("="*60)
print("2. 櫃買 除權息預告表")
print("="*60)
url = 'https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_ex_right/daily_trading_ex_right_result.php'
params = {'l': 'zh-tw', 'd': '2026/07', 'stk': '', 's': '0,asc,0'}
try:
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get('aaData'):
        print(f'  共 {len(data[\"aaData\"])} 筆')
        for row in data['aaData'][:5]:
            print(f'    {row}')
    else:
        print(f'  無資料')
except Exception as e:
    print(f'  失敗: {e}')

print()
print("="*60)
print("3. 證交所 法說會公告")
print("="*60)
url = 'https://mops.twse.com.tw/mops/web/ajax_t108sb16'
payload = {
    'encodeURLComponent': 'true',
    'step': '1',
    'firstin': 'true',
    'off': '1',
    'keyword4': '',
    'code1': '',
    'TYPEK': 'all',
    'year': '2026',
    'month': '7',
}
try:
    r = requests.post(url, data=payload, timeout=15)
    # 證交所回傳是HTML表格
    if r.status_code == 200:
        text = r.text[:2000]
        print(text[:1000])
except Exception as e:
    print(f'  失敗: {e}')

print()
print("="*60)
print("4. 證交所 重大訊息")
print("="*60)
url = 'https://mops.twse.com.tw/mops/web/ajax_t05st01'
payload = {
    'encodeURLComponent': 'true',
    'step': '1',
    'firstin': 'true',
    'off': '1',
    'keyword4': '2330',
    'code1': '',
    'TYPEK': 'sii',
    'year': '2026',
    'month': '7',
}
try:
    r = requests.post(url, data=payload, timeout=15)
    if r.status_code == 200:
        print(f'  長度: {len(r.text)}')
        print(r.text[:800])
except Exception as e:
    print(f'  失敗: {e}')

print()
print("="*60)
print("5. 總經行事曆 - Federal Reserve")
print("="*60)
# FOMC 行事曆用已知固定日期 + 美國經濟數據也是已知排程
print("  FOMC: 固定每年8次會議，日期全年已知")
print("  非農/NFP: 每月第一個星期五")
print("  CPI: 每月中旬")
print("  PCE: 每月底")

print()
print("="*60)
print("6. FinMind 月營收 (已確認可用)")
print("="*60)
url = 'https://api.finmindtrade.com/api/v4/data'
params = {'dataset': 'TaiwanStockMonthRevenue', 'data_id': '2330', 'start_date': '2026-01-01', 'end_date': '2026-07-21'}
r = requests.get(url, params=params, timeout=10).json()
if r.get('status') == 200 and r.get('data'):
    for d in r['data'][-3:]:
        print(f'  {d[\"revenue_year\"]}/{d[\"revenue_month\"]}: 營收={d[\"revenue\"]:,}')
