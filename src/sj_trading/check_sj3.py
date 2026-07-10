"""
永豐API正確日KD - 30天版
"""
import os
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
from datetime import datetime, timedelta
import numpy as np

api = sj.Shioaji(simulation=True)
api.login(api_key=***, secret_key=os.environ['SJ_SEC_KEY'])

end = datetime.now()
start = end - timedelta(days=30)

for sid in ['2317','3231','2382']:
    contract = api.Contracts.Stocks[sid]
    kbar = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    
    c_list = list(kbar.Close)
    h_list = list(kbar.High)
    l_list = list(kbar.Low)
    t_list = list(kbar.ts)
    
    daily = {}
    for i in range(len(c_list)):
        d = datetime.fromtimestamp(t_list[i]/1e9).strftime('%Y%m%d')
        if d not in daily:
            daily[d] = [c_list[i], h_list[i], l_list[i]]
        else:
            daily[d][0] = c_list[i]
            daily[d][1] = max(daily[d][1], h_list[i])
            daily[d][2] = min(daily[d][2], l_list[i])
    
    days = sorted(daily.keys())
    dc = np.array([daily[d][0] for d in days], dtype=float)
    dh = np.array([daily[d][1] for d in days], dtype=float)
    dl = np.array([daily[d][2] for d in days], dtype=float)
    
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
        'K>D多頭' if k[-1]>d[-1] else 'K<D空頭'))
    print("  日期   收盤    K    D")
    for i in range(-10, 0):
        print("  %s %5.0f %5.1f %5.1f %s" % (
            days[i][4:6]+'/'+days[i][6:], dc[i], k[i], d[i],
            'K>D' if k[i]>d[i] else 'K<D'))

api.logout()
