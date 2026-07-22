c = open(r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\ta_strategy_engine.py', encoding='utf-8').read()

# Fix 1: remove misplaced import before SCRIPT_DIR
old_bad = "sys.path.insert(0, SCRIPT_DIR)\nfrom download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download\n\n# "
new_good = "sys.path.insert(0, SCRIPT_DIR)\n\n# "
assert old_bad in c, "bad pattern not found"
c = c.replace(old_bad, new_good, 1)

# Fix 2: add import at correct location (after sys.path.insert line)
target = 'sys.path.insert(0, SCRIPT_DIR); load_dotenv(os.path.join(BASE_DIR, ".env"))'
if target in c:
    c = c.replace(
        target,
        target + '\nfrom download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download',
        1
    )
else:
    print("WARN: target not found, trying manual insert after SCRIPT_DIR line")
    idx = c.find("sys.path.insert(0, SCRIPT_DIR);")
    if idx >= 0:
        end = c.find("\n", idx)
        c = c[:end+1] + "from download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download\n" + c[end+1:]

open(r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\ta_strategy_engine.py', 'w', encoding='utf-8').write(c)
import ast; ast.parse(c); print('OK')
