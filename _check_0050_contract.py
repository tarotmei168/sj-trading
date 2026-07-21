import os
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
try:
    c = api.Contracts.Stocks['0050']
    print(f'Stocks 0050: {c}')
except Exception as e:
    print(f'Stocks fail: {e}')
try:
    etf = api.Contracts.ETF
    print(f'ETF has 0050: {hasattr(etf, "0050")}')
except Exception as e:
    print(f'ETF fail: {e}')
api.logout()
