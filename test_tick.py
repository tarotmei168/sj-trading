"""測試 Shioaji Tick 訂閱功能"""
from dotenv import load_dotenv
import os, shioaji as sj, time
from datetime import datetime

load_dotenv()
api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

# 初始化合約
contracts = api.Contracts
contract = contracts.Stocks['2330']
print(f'合約: {contract.code} {contract.name}')

# 試訂閱 tick - 不給參數試試
try:
    api.subscribe(contract, quote_type='tick')
    print('Subscribe tick OK (default version)')
except Exception as e:
    print(f'Subscribe error (default): {e}')

try:
    api.subscribe(contract, quote_type='tick', version='v1')
    print('Subscribe tick OK (v1)')
except Exception as e:
    print(f'Subscribe error (v1): {e}')

try:
    api.subscribe(contract, quote_type='bidask')
    print('Subscribe bidask OK')
except Exception as e:
    print(f'Subscribe bidask error: {e}')

time.sleep(2)
api.logout()
print('Done')
