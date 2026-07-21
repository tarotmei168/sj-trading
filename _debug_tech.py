import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.join(BASE_DIR, 'src', 'sj_trading')
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

from calc_tech import read_local_csv
from daily_web_report import get_tech_batch, CORE_IDS, KD3Y_PARAMS

CORE_IDS = ['2436','2337','5351','3673','3711','4958','3042','2454','2317','8150','2330']
tech = get_tech_batch(CORE_IDS)
for sid in CORE_IDS:
    t = tech.get(sid)
    if t:
        print(f'{sid}: price={t["price"]:.1f}, k={t["k"]:.1f}, d={t["d"]:.1f}, golden={t["golden"]}, rsi={t["rsi"]}')
    else:
        print(f'{sid}: NO DATA')
