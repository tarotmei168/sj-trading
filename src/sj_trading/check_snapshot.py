"""測試 snapshots 和歷史 KBars 的大戶資料"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
import json

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

# 1. Snapshots 可以一次拉多檔
contracts = [api.Contracts.Stocks[sid] for sid in ['2330', '2454', '2317']]
snaps = api.snapshots(contracts)
print(f"=== Snapshots {len(snaps)} 檔 ===")
for s in snaps:
    print(f"  {s.code}: close={s.close} vol={s.volume} buy_v={s.buy_volume} sell_v={s.sell_volume} total_v={s.total_volume}")

# 2. KBars 歷史資料 - 看看能不能拉日K算大戶均量
print("\n=== KBars 歷史(日K) ===")
try:
    from datetime import datetime, timedelta
    end = datetime.now()
    start = end - timedelta(days=10)
    kbars = api.kbars(contract=contracts[0], start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    print(f"  KBars keys: {kbars.keys}")
    print(f"  len: {len(kbars.ts)}")
    print(f"  Volume 樣本: {list(kbars.Volume[:5])}")
    print(f"  Close 樣本: {list(kbars.Close[:5])}")
except Exception as e:
    print(f"  ❌ {e}")

# 3. 檢查 contracts 是否有每日行情摘要
print("\n=== Contracts 資訊 ===")
c = contracts[0]
print(f"  {c.code}: category={c.category} reference={c.reference} limit_up={c.limit_up} limit_down={c.limit_down}")

api.logout()
