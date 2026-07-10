"""鸿海 2317 大单流向检查"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj

api = sj.Shioaji(simulation=True)
api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])

sid='2317'; name='鸿海'
c = api.Contracts.Stocks[sid]
snaps = api.snapshots([c])
if snaps:
    s = snaps[0]
    print(f'{name}({sid}) @{s.close}')
    print(f'成交量: {s.total_volume} 张')
    print(f'成交金额: {s.total_amount/100000000:.2f}亿')
    print(f'外盘量(buy): {s.buy_volume} 张')
    print(f'内盘量(sell): {s.sell_volume} 张')
    
    # 估算大戶流入
    # 外盘成交额 = 总成交额 * (外盘量/(外盘量+内盘量))
    total_vol = s.buy_volume + s.sell_volume
    if total_vol > 0:
        buy_ratio = s.buy_volume / total_vol * 100
        sell_ratio = s.sell_volume / total_vol * 100
        # 大戶(單筆>=100萬)在旺宏這價位約>=68張
        # 鴻海245元，100萬/245000 = 約4張就是大戶
        print(f'\n--- 大戶估算 (單筆>=100萬=約4張) ---')
        print(f'外盘(买方)占比: {buy_ratio:.1f}%')
        print(f'内盘(卖方)占比: {sell_ratio:.1f}%')
        if buy_ratio > 55:
            print(f'>>> 大戶偏多買入! 有魚出價! 🐋')
        elif sell_ratio > 55:
            print(f'>>> 大戶偏多賣出! 🐻')
        else:
            print(f'>>> 買賣平衡')

api.logout()
