"""
永豐API正確日KD - 比對大戶投/三竹
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
from datetime import datetime, timedelta
import numpy as np

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

end = datetime.now()
start = end - timedelta(days=90)

for sid in ['2317','3231','2382','3017','2451']:
    contract = api.Contracts.Stocks[sid]
    # 分段抓，避開30天限制
    all_kbars = []
    seg_end = end
    for seg in range(3):
        seg_start = seg_end - timedelta(days=29)
        try:
            kb = api.kbars(contract=contract, start=seg_start.strftime('%Y-%m-%d'), end=seg_end.strftime('%Y-%m-%d'))
            if hasattr(kb, 'Close') and len(kb.Close) > 0:
                all_kbars.append(kb)
        except:
            pass
        seg_end = seg_start - timedelta(days=1)
    
    # 合併
    if not all_kbars:
        print('%s: 無資料' % sid)
        continue
    
    import pandas as pd
    closes = np.concatenate([kb.Close for kb in all_kbars])
    highs_arr = np.concatenate([kb.High for kb in all_kbars])
    lows_arr = np.concatenate([kb.Low for kb in all_kbars])
    ts_arr = np.concatenate([kb.ts for kb in all_kbars])
    
    # 每日取最後一筆
    daily = {}
    for i in range(len(closes)):
        d = datetime.fromtimestamp(ts_arr[i]/1e9).strftime('%Y%m%d')
        c = float(closes[i]); h = float(highs_arr[i]); l = float(lows_arr[i])
        if d not in daily:
            daily[d] = {'close':c, 'high':h, 'low':l}
        else:
            daily[d]['close'] = c
            daily[d]['high'] = max(daily[d]['high'], h)
            daily[d]['low'] = min(daily[d]['low'], l)
    
    # 每日取最後一筆（當日收盤）
    daily = {}  # date_str -> {close, high, low}
    for i in range(len(kbars.Close)):
        d = datetime.fromtimestamp(kbars.ts[i]/1e9).strftime('%Y%m%d')
        c = float(kbars.Close[i])
        h = float(kbars.High[i])
        l = float(kbars.Low[i])
        if d not in daily:
            daily[d] = {'close':c, 'high':h, 'low':l}
        else:
            daily[d]['close'] = c
            daily[d]['high'] = max(daily[d]['high'], h)
            daily[d]['low'] = min(daily[d]['low'], l)
    
    sorted_days = sorted(daily.keys())
    dc = np.array([daily[d]['close'] for d in sorted_days], dtype=float)
    dh = np.array([daily[d]['high'] for d in sorted_days], dtype=float)
    dl = np.array([daily[d]['low'] for d in sorted_days], dtype=float)
    
    # KD 9/3（標準）
    n = len(dc)
    k = np.zeros(n); d = np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-9+1)
        hh=np.max(dh[ps:i+1]); ll=np.min(dl[ps:i+1])
        rsv=(dc[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(2/3)*k[i-1]+(1/3)*rsv
        d[i]=(2/3)*d[i-1]+(1/3)*k[i]
    
    print("%s 收%.0f K=%.1f D=%.1f %s" % (
        sid, dc[-1], k[-1], d[-1],
        'K>D✅' if k[-1]>d[-1] else 'K<D'))
    
    for i in range(-10, 0):
        dd = sorted_days[i]
        print("  %s  C%.0f H%.0f L%.0f K%.1f D%.1f %s" % (
            dd[4:6]+'/'+dd[6:], dc[i], dh[i], dl[i], k[i], d[i],
            'K>D' if k[i]>d[i] else 'K<D'))

api.logout()
