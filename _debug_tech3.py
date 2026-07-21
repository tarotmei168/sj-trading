import sys, os
BASE_DIR = r'C:\Users\User\.openclaw\workspace\sj-trading'
SCRIPT_DIR = os.path.join(BASE_DIR, 'src', 'sj_trading')
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

import calc_tech
print('calc_tech.__file__:', calc_tech.__file__)
print('calc_tech.BASE_DIR:', calc_tech.BASE_DIR)
print('calc_tech.DB_DIR:', calc_tech.DB_DIR)
print('DB exists:', os.path.exists(calc_tech.DB_DIR))
print('KD3 exists:', os.path.exists(calc_tech.KD3_DIR))

data = calc_tech.read_local_csv('2330')
print('2330 data:', len(data) if data else None)

# Now check if daily_web_report uses the same
from daily_web_report import get_tech_batch, CORE_IDS
print('daily_web_report BASE_DIR:', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
