import sys; sys.path.insert(0, 'src')
import os
from dotenv import load_dotenv
import shioaji as sj
from sj_trading.backtest_kd import fetch_kbars_daily, compute_kd, find_signals, backtest
import pandas as pd

load_dotenv()
api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

params = {
    '3711': ('日月光', 3, 40, 65),
    '4958': ('臻鼎KY', 3, 40, 65),
    '3042': ('晶技', 5, None, 70),
    '2337': ('旺宏', 5, None, 70),
    '2436': ('偉詮電', 5, None, 70),
    '3673': ('TPKKY', 5, None, 70),
}

for stock_id in params:
    name, k, bt, st = params[stock_id]
    daily = fetch_kbars_daily(api, stock_id, days=90)
    
    daily2 = compute_kd(daily, k_period=k)
    
    print(f'\n=== {name} ({stock_id}) K={k} ===', flush=True)
    print(f'最新價: {daily.iloc[-1]["close"]:.1f}', flush=True)
    print(f'最新K={daily2.iloc[-1]["K"]:.1f} D={daily2.iloc[-1]["D"]:.1f}', flush=True)
    
    # 無門檻交叉
    df_no = find_signals(daily2, k)
    sigs = df_no[df_no['signal'] != 0]
    if len(sigs) > 0:
        print(f'交叉訊號: {len(sigs)}個', flush=True)
        for idx, row in sigs.iterrows():
            act = 'BUY ' if row['signal'] == 1 else 'SELL'
            print(f'  {idx.strftime("%m/%d")} {act} K={row["K"]:.1f} D={row["D"]:.1f} @{row["close"]:.1f}', flush=True)
    else:
        print('無交叉訊號', flush=True)
    
    # 有門檻回測
    df_sig = find_signals(daily2, k, bt, st)
    trades, pnl, wins, losses = backtest(df_sig)
    closed = [t for t in trades if t['賣出'] != '持有中']
    print(f'回測: {len(closed)}筆, 勝{wins}敗{losses}, 損益{pnl:.1f}點', flush=True)
    for t in trades:
        if t['賣出'] != '持有中':
            print(f'  {t["買入"]}買@{t["買價"]} -> {t["賣出"]}賣@{t["賣價"]} {t["獲利%"]}%', flush=True)
        else:
            print(f'  {t["買入"]}買@{t["買價"]} -> 持有中', flush=True)

api.logout()
print('\nDONE', flush=True)
