import sys, os
sys.path.insert(0, r'src\sj_trading')
from download_3y_intraday_kd_v2 import login, download_stock
import pandas as pd
import numpy as np
import talib

api = login()
print('login ok')

sid = '0050'
existing = None
f = r'database\3y_kd\0050_kd.csv'
if os.path.isfile(f):
    try:
        existing = pd.read_csv(f, parse_dates=['datetime'])
        print(f'existing: {len(existing)} rows')
    except:
        pass

df_1min = download_stock(api, sid, lookback_days=365*3, seg_days=100, existing_df=existing)
if df_1min is None or len(df_1min) < 100:
    print('not enough data')
else:
    df2 = df_1min.set_index('datetime')
    ohlc = pd.DataFrame({'open': df2['open'].resample('30min').first()})
    ohlc['high'] = df2['high'].resample('30min').max()
    ohlc['low'] = df2['low'].resample('30min').min()
    ohlc['close'] = df2['close'].resample('30min').last()
    ohlc['volume'] = df2['volume'].resample('30min').sum()
    ohlc = ohlc.dropna().reset_index()
    ohlc['hour'] = ohlc['datetime'].dt.hour
    ohlc['minute'] = ohlc['datetime'].dt.minute
    ohlc = ohlc[((ohlc['hour']==9)&(ohlc['minute']>=0))|(ohlc['hour']>=10)&(ohlc['hour']<=12)|(ohlc['hour']==13)&(ohlc['minute']<=30)]
    ohlc = ohlc.drop(columns=['hour','minute']).reset_index(drop=True)
    ohlc['datetime'] = ohlc['datetime'].astype(str)
    k,d = talib.STOCH(ohlc['high'].values, ohlc['low'].values, ohlc['close'].values, fastk_period=9, slowk_period=3, slowd_period=3)
    ohlc['K'] = k; ohlc['D'] = d
    ohlc.to_csv(f, index=False, encoding='utf-8-sig')
    print('saved', len(ohlc), 'rows')
    print('last K=', round(ohlc.iloc[-1]['K'],1), 'D=', round(ohlc.iloc[-1]['D'],1))

api.logout()
