"""確認 Tick callback 的完整結構"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

# 直接 subscribe 一檔看看
contract = api.Contracts.Stocks["2330"]
print(f"合約: {contract}")
print(f"合約類型: {type(contract)}")

# subscribe tick
api.subscribe(contract, quote_type='tick', version='v1')

import time

captured = []

def on_tick(exchange, tick):
    captured.append(tick)
    if len(captured) >= 2:
        api.logout()
    # 印出所有屬性
    print(f"\n=== Tick 完整結構 ===")
    print(f"類型: {type(tick)}")
    print(f"code: {tick.code}")
    print(f"close: {tick.close}")
    print(f"volume: {tick.volume}")
    for attr in dir(tick):
        if not attr.startswith('_') and attr not in ('dict', 'keys', 'to_dict', 'from_msgpack'):
            try:
                val = getattr(tick, attr)
                if not callable(val):
                    print(f"  {attr}: {val}")
            except:
                pass
    
    # 特別檢查大戶相關欄位
    print(f"\n=== 大戶相關欄位 ===")
    for attr in ['trade_bid_cnt', 'trade_ask_cnt', 'trade_bid_vol_sum', 'trade_ask_vol_sum',
                 'bid_side_total_cnt', 'ask_side_total_cnt', 'bid_side_total_vol', 'ask_side_total_vol',
                 'vol_sum', 'total_volume', 'total_amount',
                 'trade_bid_cnt', 'trade_ask_cnt', 'avg_price', 'pct_chg', 'price_chg']:
        try:
            val = getattr(tick, attr, 'N/A')
            print(f"  {attr}: {val}")
        except:
            print(f"  {attr}: ERROR")

api.set_on_tick_stk_v1_callback(on_tick)

# 等幾秒收資料
print("\n等待 Tick 數據中 (5秒)...")
time.sleep(5)

if not captured:
    print("現在非盤中，無即時 Tick 數據")
    # 試 snapshot
    print("\n== Snapshot 測試 == ")
    sn = api.snapshots([contract])
    if sn:
        s = sn[0]
        print(f"Snapshot: code={s.code} close={s.close} vol={s.volume}")
        for attr in ['buy_price', 'buy_volume', 'sell_price', 'sell_volume',
                     'total_amount', 'total_volume', 'volume_ratio']:
            try:
                print(f"  {attr}: {getattr(s, attr, 'N/A')}")
            except:
                pass

api.logout()
print("\n完成")
