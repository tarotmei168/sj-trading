import json, os

with open(os.path.expanduser("~/.openclaw/workspace/sj-trading/src/backtest_6m_v4.json"), "r") as f:
    data = json.load(f)

# 取前10賣交易明細比較精彩的
highlight = ["4958", "3037", "3189", "2330", "6139", "2454", "8046", "3711"]

for sid in highlight:
    v = data[sid]
    b = v["best"]
    bt = f"買<{b['buy']}" if b["buy"] else "買不限"
    st = f"賣>{b['sell']}" if b["sell"] else "賣不限"
    print(f"\n{'='*65}")
    print(f"  {v['name']}({sid}) | K={b['k']} {bt} {st} | 總報酬+{b['pnl']:.2f}% | {b['trades']}筆")
    print(f"{'='*65}")
    print(f"  {'買入時間':<20} {'買入價':<10} {'賣出時間':<22} {'賣出價':<10} {'獲利%':<10}")
    print(f"  {'-'*70}")
    for t in v["trades"]:
        bp = f"{t['buy_price']:.2f}"
        sp = f"{t['sell_price']:.2f}" if "持有中" not in str(t['sell_date']) else "持有中"
        sd = t['sell_date']
        pct = f"{t['profit_pct']:+.2f}%"
        print(f"  {t['buy_date']:<20} {bp:<10} {sd:<22} {sp:<10} {pct:<10}")
