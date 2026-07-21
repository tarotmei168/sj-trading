import sys, os
BASE_DIR = r'C:\Users\User\.openclaw\workspace\sj-trading'
SCRIPT_DIR = os.path.join(BASE_DIR, 'src', 'sj_trading')
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

from calc_tech import read_local_csv

for sid in ['2436','2337','5351','3673','3711','4958','3042','2454','2317','8150','2330']:
    data = read_local_csv(sid)
    if data:
        print(f'{sid}: {len(data)} rows, last={data[-1].get("close")}, K={data[-1].get("K","N/A")}')
    else:
        print(f'{sid}: None')
