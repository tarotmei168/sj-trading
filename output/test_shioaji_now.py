import sys, os
sys.path.insert(0, r'src\sj_trading')
from dotenv import load_dotenv; load_dotenv(r'.env')
import shioaji as sj
from datetime import datetime, timedelta, timezone
from collections import Counter

api = sj.Shioaji(simulation=False)
api.login(api_key=os.environ.get('SJ_API_KEY',''), secret_key=os.environ.get('SJ_SEC_KEY',''), fetch_contract=True)
print('ok')

contract = api.Contracts.Stocks['2634']
# 抓前3天
end = datetime.now()
start = end - timedelta(days=5)
kb = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
print(f'2634 5d: {len(kb.ts)} entries')
hc = Counter()
for i in range(len(kb.ts)):
    t = datetime.fromtimestamp(kb.ts[i]/1e9, tz=timezone.utc) + timedelta(hours=8)
    hc[t.hour] += 1
print('hour:', sorted(hc.items()))

# check if we have market hours data (09-13)
mkt = sum(v for h,v in hc.items() if (h==9) or (h>=10 and h<=13))
print(f'market hours entries: {mkt}')
api.logout()
