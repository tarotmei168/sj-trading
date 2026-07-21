#!/usr/bin/env python3
"""Quick runner: import optimize_2337_finmind and run a smaller grid for faster results."""
import runpy
from datetime import datetime
print('Running quick optimization for 2337 at', datetime.now())
mod = runpy.run_path(r'c:\Users\User\.openclaw\workspace\sj-trading\optimize_2337_finmind.py')
# extract functions from mod
fetch_finmind_price = mod['fetch_finmind_price']
compute_indicators = mod['compute_indicators']
grid_search = mod['grid_search']
USER_COST = mod.get('USER_COST', 190.0)
TICKER = mod.get('TICKER', '2337')

# fetch data
end = datetime.now().strftime('%Y-%m-%d')
start = (datetime.now() - __import__('datetime').timedelta(days=365*2)).strftime('%Y-%m-%d')
df = fetch_finmind_price(TICKER, start, end)
if df is None or len(df) < 200:
    raise RuntimeError('No data')
df = compute_indicators(df)

# build smaller grid by monkeypatching optimize module's grid parameters
# We will call simulate directly by constructing a reduced grid using mod.simulate
simulate = mod['simulate']

oversold_options = [(120,130),(115,130)]
dev_options = [10,15]
days_since_min_opts = [0,1,2]
profit_targets = [0,5,10]
exit_k_opts = [60,70]
stop_loss_opts = [15,25]
min_window_opts = [7,14]

results = []
count=0
for overs in oversold_options:
    for dev in dev_options:
        for days in days_since_min_opts:
            for pt in profit_targets:
                for ek in exit_k_opts:
                    for sl in stop_loss_opts:
                        for mw in min_window_opts:
                            params = {'oversold_min': overs[0], 'oversold_max': overs[1], 'dev_pct': dev, 'days_since_min': days, 'profit_target': pt, 'exit_k': ek, 'stop_loss': sl, 'min_window': mw}
                            res = simulate(df, params, USER_COST)
                            count += 1
                            if res:
                                results.append(res)

print(f'Completed quick grid: tested {count} combos, found {len(results)} results')
# sort and print top 10
results_sorted = sorted(results, key=lambda r: (r['win_rate'], r['recovery_rate'], r['avg_ret']), reverse=True)
for r in results_sorted[:10]:
    p=r['params']
    print(f"win={r['win_rate']}% recov={r['recovery_rate']}% trades={r['trades']} avg_ret={r['avg_ret']}% total={r['total_return']}% -> overs={p['oversold_min']}-{p['oversold_max']} dev={p['dev_pct']}% days={p['days_since_min']} profit={p['profit_target']}% exitK={p['exit_k']} stop={p['stop_loss']}% window={p['min_window']}")

# save results
import json
with open('optimize_2337_quick_results.json','w',encoding='utf-8') as f:
    json.dump(results_sorted, f, default=str, ensure_ascii=False, indent=2)
print('Saved optimize_2337_quick_results.json')
print('Done at', datetime.now())
