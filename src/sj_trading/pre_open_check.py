"""偉詮電2436 + 鴻海2317 開盤前預覽"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def compute_kd(closes, highs, lows, kp):
    n = len(closes)
    k = np.full(n, 50.0)
    d = np.full(n, 50.0)
    for i in range(kp, n):
        lo = min(lows[i-kp+1:i+1])
        hi = max(highs[i-kp+1:i+1])
        rsv = 50.0
        if hi != lo:
            rsv = (closes[i] - lo) / (hi - lo) * 100
        k[i] = (2/3)*k[i-1] + (1/3)*rsv
        d[i] = (2/3)*d[i-1] + (1/3)*k[i]
    return k, d

def compute_rsi(closes, period=14):
    n = len(closes)
    rsi = np.full(n, 50.0)
    if n < period+1:
        return rsi
    for i in range(period, n):
        gains = sum(closes[j]-closes[j-1] for j in range(i-period+1, i+1) if closes[j] > closes[j-1])
        losses = sum(closes[j-1]-closes[j] for j in range(i-period+1, i+1) if closes[j] < closes[j-1])
        ag = gains/period; al = losses/period
        if al == 0: rsi[i] = 100.0
        else: rsi[i] = 100.0 - 100.0/(1.0 + ag/al)
    return rsi

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

for sid, name, kp in [('2436','偉詮電',3), ('2317','鴻海',5)]:
    print(f'\n{"="*55}')
    print(f'  {name}({sid}) — K={kp}')
    print(f'{"="*55}')
    
    contract = api.Contracts.Stocks[sid]
    end = datetime.now()
    start = end - timedelta(days=25)
    kbars = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    
    closes = list(kbars.Close)
    highs = list(kbars.High)
    lows = list(kbars.Low)
    ts = list(kbars.ts)
    
    df = pd.DataFrame({'datetime':pd.to_datetime(ts),'close':closes,'high':highs,'low':lows})
    df.set_index('datetime',inplace=True)
    df_30 = df.resample('30min').agg({'close':'last','high':'max','low':'min'}).dropna()
    df_30 = df_30.between_time('09:00','13:30')
    
    c30 = df_30['close'].values; h30 = df_30['high'].values; l30 = df_30['low'].values
    k30, d30 = compute_kd(c30, h30, l30, kp)
    rsi30 = compute_rsi(c30)
    
    last = df_30.iloc[-1]
    print(f'  最新收盤: {last["close"]:.2f}')
    print(f'  30分K KD: K={k30[-1]:.1f} D={d30[-1]:.1f}')
    print(f'  14期RSI:  {rsi30[-1]:.1f}')
    print(f'  KD狀態: {"金叉🟢" if k30[-1] > d30[-1] else "死叉🔴"}')
    print(f'  RSI位階: {"超跌💎" if rsi30[-1] < 30 else "高檔鈍化🔥" if rsi30[-1] > 70 else "常態⚪"}')
    
    # 最近5根K棒
    print(f'\n  最近5根30分K:')
    for i in range(-5, 0):
        idx = df_30.index[i]
        print(f'    {idx.strftime("%m/%d %H:%M")} O:{df_30.iloc[i]["close"]:.1f} K:{k30[i]:.1f} D:{d30[i]:.1f} RSI:{rsi30[i]:.1f}')
    
    # K線斜率（最近3根不含當根）
    if len(k30) >= 6:
        recent_k = k30[-4:-1]
        slope = np.polyfit(np.arange(3), recent_k, 1)[0]
        print(f'  K線斜率(近3根不含當根): {slope:+.2f}')

api.logout()
print('\n✅ 完成')
