import sys, os
BASE_DIR = r'C:\Users\User\.openclaw\workspace\sj-trading'
SCRIPT_DIR = os.path.join(BASE_DIR, 'src', 'sj_trading')
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

# Patch to debug
from calc_tech import read_local_csv, calc_RSI

for sid in ['2330']:
    data = read_local_csv(sid)
    print(f'{sid}: data type={type(data)}, len={len(data) if data else "None"}')
    if data and len(data) >= 25:
        print(f'  first row keys: {list(data[0].keys())[:10]}')
        print(f'  last close: {data[-1]["close"]}')
        print(f'  has K col: {"K" in data[0]}')
        # Simulate get_tech_batch logic
        import numpy as np
        closes = np.array([d['close'] for d in data], dtype=float)
        has_kd = 'K' in data[0] and 'D' in data[0]
        print(f'  has_kd_col={has_kd}')
        if has_kd:
            k = float(data[-1]['K'])
            d = float(data[-1]['D'])
            print(f'  K={k}, D={d}')
            rsi_val = calc_RSI(closes.tolist())
            print(f'  RSI={rsi_val}')
