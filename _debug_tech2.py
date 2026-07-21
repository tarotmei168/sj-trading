import sys, os

BASE_DIR = r'C:\Users\User\.openclaw\workspace\sj-trading'
SCRIPT_DIR = os.path.join(BASE_DIR, 'src', 'sj_trading')
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

# 直接 import daily_web_report 然後呼叫
from daily_web_report import get_tech_batch, CORE_IDS

tech = get_tech_batch(CORE_IDS)
for sid in CORE_IDS:
    t = tech.get(sid)
    if t:
        print(f'{sid}: price={t["price"]:.1f}, k={t["k"]:.1f}, d={t["d"]:.1f}, golden={t["golden"]}, rsi={t["rsi"]}')
    else:
        print(f'{sid}: NO DATA')
