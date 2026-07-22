#!/usr/bin/env python3
"""Debug: check TA-Lib tech data for all stocks"""
import sys, json
sys.path.insert(0, 'src/sj_trading')
from daily_web_report import get_tech_batch, CORE_IDS

# Check core + potential
with open('output/trust_scan_latest.json', 'r', encoding='utf-8') as f:
    ts = json.load(f)

candidates = [h for h in ts.get('trust_top40', []) if h['days'] >= 3 and h['total_trust'] >= 500000]
watch = [c for c in candidates if c.get('is_watch', False)]
non_watch = [c for c in candidates if not c.get('is_watch', False)]
potential = (watch[:10] + non_watch[:10])[:20]
ids = list(dict.fromkeys(CORE_IDS + [h['sid'] for h in potential]))

t = get_tech_batch(ids)
ok = sum(1 for v in t.values() if v)
fail = sum(1 for v in t.values() if not v)
print(f'OK={ok}/{len(ids)}, Failed={fail}')

# Show all fails
for sid in ids:
    d = t.get(sid)
    if not d:
        print(f'  FAIL: {sid}')
    else:
        print(f'  {sid}: K={d["k"]:.1f} D={d["d"]:.1f} RSI={d["rsi"]} MACD={d["macd"]}')
