#!/usr/bin/env python3
"""Test FinMind API - institutional investors buy/sell"""
import sys, json, requests
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://api.finmindtrade.com/api/v4/data'

# 1. Check what data_id values look like  
params = {
    'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
    'data_id': '2330',
    'start_date': '2026-07-03',
    'end_date': '2026-07-08',
}
r = requests.get(url, params=params, timeout=15)
data = r.json()
print(f'Status: {data.get("status")}')
print(f'Msg: {data.get("msg")}')
if data.get('status') == 200:
    records = data.get('data', [])
    print(f'Records for 2330: {len(records)}')
    if records:
        print(json.dumps(records[0], indent=2, ensure_ascii=False))
        print(f'Keys: {list(records[0].keys())}')
        dates = set(r['date'] for r in records)
        print(f'Dates: {sorted(dates)}')
else:
    err = data.get('msg', 'unknown')
    print(f'Error: {err}')
    
    # Try without token - maybe needs token
    # Try the alternative dataset name
    params2 = {
        'dataset': 'TaiwanStockInstitutionalInvestors',
        'data_id': '2330',
        'start_date': '2026-07-03',
        'end_date': '2026-07-08',
    }
    r2 = requests.get(url, params=params2, timeout=15)
    data2 = r2.json()
    print(f'\nAlt dataset Status: {data2.get("status")}')
    if data2.get('status') == 200:
        records2 = data2.get('data', [])
        print(f'Records: {len(records2)}')
        if records2:
            print(json.dumps(records2[0], indent=2, ensure_ascii=False))
