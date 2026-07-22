"""Update 3y_kd DB with live prices via Shioaji snapshots, then re-run TA-Lib"""
import sys, os, shioaji as sj
import pandas as pd, numpy as np, talib
from datetime import datetime

sys.path.insert(0, r'src\sj_trading')
from dotenv import load_dotenv; load_dotenv(r'.env')

DB = r'database\3y_kd'

api = sj.Shioaji(simulation=False)
api.login(api_key=os.environ.get('SJ_API_KEY',''), secret_key=os.environ.get('SJ_SEC_KEY',''), fetch_contract=True)

# Get live prices for all core stocks
codes = ['2436','2337','5351','3673','3711','4958','3042','2454','2317','8150','2330']
contracts = [api.Contracts.Stocks[c] for c in codes]
snaps = api.snapshots(contracts)
live = {s.code: s for s in snaps}

for sid in codes:
    f = os.path.join(DB, f'{sid}_kd.csv')
    if not os.path.isfile(f):
        continue
    df = pd.read_csv(f)
    if len(df) < 30:
        continue
    
    s = live.get(sid)
    if not s or s.close is None:
        continue
    
    live_px = round(float(s.close), 1)
    live_chg = round(float(s.change_price), 2)
    live_chg_pct = round(float(s.change_rate), 2)
    
    # Replace last bar's close with live price
    df.loc[df.index[-1], 'close'] = live_px
    
    # Recalculate K/D with TA-Lib
    k, d = talib.STOCH(df['high'].values, df['low'].values, df['close'].values,
                        fastk_period=9, slowk_period=3, slowd_period=3)
    df['K'] = k
    df['D'] = d
    
    # Save back
    df.to_csv(f, index=False, encoding='utf-8-sig')
    k_last = round(float(k[-1]), 1) if not np.isnan(k[-1]) else 50.0
    print(f'{sid} live={live_px} chg={live_chg}({live_chg_pct}%) KD={k_last}/{round(float(d[-1]),1)}')

api.logout()
print('Done')
