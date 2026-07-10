"""
測試永豐API KD數據 - 簡化版
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

import shioaji as sj
from datetime import datetime, timedelta
import numpy as np

api = sj.Shioaji(simulation=True)
api.login(
    api_key=os.environ['SJ_API_KEY'],
    secret_key=os.environ['SJ_SEC_KEY']
)

def calc_kd(kbars, kp=9, dp=3):
    close = np.array(kbars.Close, dtype=float)
    high = np.array(kbars.High, dtype=float)
    low = np.array(kbars.Low, dtype=float)
    n = len(close)
    k = np.zeros(n); d = np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-kp+1)
        hh=np.max(high[ps:i+1]); ll=np.min(low[ps:i+1])
        rsv=(close[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(dp-1)/dp * k[i-1] + (1/dp)*rsv
        d[i]=(dp-1)/dp * d[i-1] + (1/dp)*k[i]
    return k, d, close

end = datetime.now()
start = end - timedelta(days=20)

for sid in ['2317','3231','2382']:
    contract = api.Contracts.Stocks[sid]
    kbars = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    k, d, close = calc_kd(kbars)
    
    print("%s  K=%.1f  D=%.1f  C=%.1f  %s" % (
        sid, k[-1], d[-1], close[-1], 
        'K>D多頭' if k[-1]>d[-1] else 'K<D空頭'))
    
    # 近5天
    for i in range(-5, 0):
        ts = datetime.fromtimestamp(kbars.ts[i]/1e9)
        print("  %s  L%.0f  C%.0f  K%.1f D%.1f %s" % (
            ts.strftime('%m/%d'), kbars.Low[i], close[i], k[i], d[i],
            'K>D' if k[i]>d[i] else 'K<D'))

api.logout()
