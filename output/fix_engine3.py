fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\ta_strategy_engine.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

# Remove the incorrect import line at top
c = c.replace(
    '\n# 使用 proven 的 Shioaji 下載工具\nsys.path.insert(0, SCRIPT_DIR)\nfrom download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download',
    ''
)

# Add import after SCRIPT_DIR/BASE_DIR definition  
target = 'sys.path.insert(0, SCRIPT_DIR); load_dotenv(os.path.join(BASE_DIR, ".env"))'
replacement = 'sys.path.insert(0, SCRIPT_DIR); load_dotenv(os.path.join(BASE_DIR, ".env"))\nfrom download_3y_intraday_kd_v2 import login as _shioaji_login, download_stock as _shioaji_download'

assert target in c, "target not found"
c = c.replace(target, replacement, 1)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

import ast
ast.parse(c)
print('OK')
