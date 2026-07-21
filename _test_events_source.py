import requests, json

print("=== FinMind 除權息 ===")
for sid in ['2330', '2454', '2317', '3711', '3042', '4958']:
    url = 'https://api.finmindtrade.com/api/v4/data'
    params = {'dataset': 'TaiwanStockDividend', 'data_id': sid, 'start_date': '2026-06-01', 'end_date': '2026-09-30'}
    try:
        r = requests.get(url, params=params, timeout=10).json()
        if r.get('status') == 200 and r.get('data'):
            last = r['data'][-1]
            d = last.get('cash_ex_rights_date', '?')
            amt = last.get('cash_dividend', '?')
            print(f'  {sid}: {d} 股利={amt}')
        else:
            print(f'  {sid}: 無')
    except Exception as e:
        print(f'  {sid}: {e}')

print()
print("=== FinMind 法說/股東會 ===")
# 試 TaiwanStockHolidayCalendar 看有無
url = 'https://api.finmindtrade.com/api/v4/data'
params = {'dataset': 'TaiwanStockHolidayCalendar', 'start_date': '2026-07-01', 'end_date': '2026-08-31'}
try:
    r = requests.get(url, params=params, timeout=10).json()
    if r.get('status') == 200 and r.get('data'):
        print(f'  交易日曆: {len(r["data"])} 筆')
        for d in r['data'][:3]:
            print(f'    {json.dumps(d, ensure_ascii=False)}')
except Exception as e:
    print(f'  失敗: {e}')

print()
print("=== FinMind Shareholding (大股東/法人) ===")
url = 'https://api.finmindtrade.com/api/v4/data'
params = {'dataset': 'TaiwanStockHoldingSharesPer', 'data_id': '2330', 'start_date': '2026-07-01', 'end_date': '2026-07-21'}
try:
    r = requests.get(url, params=params, timeout=10).json()
    if r.get('status') == 200 and r.get('data'):
        print(f'  2330: {len(r["data"])} 筆')
except Exception as e:
    print(f'  失敗: {e}')

print()
print("=== 試看看 FinMind TaiwanStockMonthRevenue ===")
url = 'https://api.finmindtrade.com/api/v4/data'
params = {'dataset': 'TaiwanStockMonthRevenue', 'data_id': '2330', 'start_date': '2026-06-01', 'end_date': '2026-07-21'}
try:
    r = requests.get(url, params=params, timeout=10).json()
    if r.get('status') == 200 and r.get('data'):
        print(f'  2330 營收: {len(r["data"])} 筆, 最近={r["data"][-1]}')
except Exception as e:
    print(f'  失敗: {e}')
