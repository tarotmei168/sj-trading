#!/usr/bin/env python3
"""Check potential stocks filtering"""
import json
with open('output/trust_scan_latest.json', 'r', encoding='utf-8') as f:
    ts = json.load(f)

candidates = [h for h in ts.get('trust_top40', []) if h['days'] >= 3 and h['total_trust'] >= 500000]
print(f'Total candidates: {len(candidates)}')
watch = [c for c in candidates if c.get('is_watch', False)]
non_watch = [c for c in candidates if not c.get('is_watch', False)]
print(f'Watch (core in trust_scan): {len(watch)}')
for w in watch:
    print(f'  {w["sid"]} {w["name"]} days={w["days"]}')
print(f'Non-watch: {len(non_watch)}')
for n in non_watch[:10]:
    print(f'  {n["sid"]} {n["name"]} days={n["days"]}')
potential = (watch[:10] + non_watch[:10])[:20]
print(f'Total potential: {len(potential)}')
