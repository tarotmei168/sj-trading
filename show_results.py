import json
with open('advanced_results.json','r',encoding='utf-8') as f:
    d = json.load(f)
for sid, v in d.items():
    b = v['best']
    bt = str(b['buy']) if b['buy'] else '不限'
    st = str(b['sell']) if b['sell'] else '不限'
    vol = f"量>{b['vol_min']}" if b['use_vol'] else "無量"
    wr = round(b['wins']/max(b['trades'],1)*100, 1)
    print(f"{v['name']}({sid}): K={b['k']} 買{bt} 賣{st} {vol} -> {b['pnl']}點 | {b['trades']}筆 | 勝率{wr}%")
