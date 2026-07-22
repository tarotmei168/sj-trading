import sys, os, pandas as pd, numpy as np, talib
from datetime import datetime, timedelta
sys.path.insert(0, r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading')
from download_3y_intraday_kd_v2 import login, download_stock

api = login()
print('ok')

sid = '2454'
df_1min = download_stock(api, sid, lookback_days=60, seg_days=30)
if df_1min is None:
    print('fail')
    api.logout()
    sys.exit(1)

print(f'1min: {len(df_1min)} entries')
print(f'range: {df_1min["datetime"].min()} ~ {df_1min["datetime"].max()}')

df = df_1min.set_index('datetime')
ohlc = pd.DataFrame({'open':df['open'].resample('30min').first()})
ohlc['high'] = df['high'].resample('30min').max()
ohlc['low'] = df['low'].resample('30min').min()
ohlc['close'] = df['close'].resample('30min').last()
ohlc['volume'] = df['volume'].resample('30min').sum()
ohlc = ohlc.dropna().reset_index()
ohlc['h'] = ohlc['datetime'].dt.hour; ohlc['m'] = ohlc['datetime'].dt.minute
ohlc = ohlc[((ohlc['h']==9)&(ohlc['m']>=0))|((ohlc['h']>=10)&(ohlc['h']<=12))|((ohlc['h']==13)&(ohlc['m']<=30))]
ohlc = ohlc.drop(columns=['h','m']).reset_index(drop=True)
print(f'30min: {len(ohlc)} bars')
print(f'last: {ohlc.iloc[-1]["datetime"]} close={ohlc.iloc[-1]["close"]}')

c = ohlc['close'].values; h = ohlc['high'].values; l = ohlc['low'].values
k,d = talib.STOCH(h,l,c,fastk_period=14,slowk_period=1,slowd_period=3)
print(f'KD: K={k[-1]:.1f} D={d[-1]:.1f}')
rsi = talib.RSI(c,timeperiod=14)
print(f'RSI(14): {rsi[-1]:.2f}')
macd,sig,hist = talib.MACD(c,fastperiod=12,slowperiod=26,signalperiod=9)
print(f'MACD_hist: {hist[-1]:.2f}')

api.logout()
