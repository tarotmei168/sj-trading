"""Replace login, download, merge in ta_strategy_engine.py using proven v2 approach"""
fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\ta_strategy_engine.py'

with open(fpath, encoding='utf-8') as f:
    c = f.read()

# Find the 3 function positions
idx_login = c.find('\ndef login_shioaji()')
idx_merge = c.find('\ndef merge_30min(df)')

# Replace login and download with thin wrappers
new_login = '''
def login_shioaji():
    """使用 proven 的登入方式 (from download_3y_intraday_kd_v2)"""
    return _shioaji_login()


def download_60d_1min(api, sid):
    """使用 proven 的 60天1分K下載 (download_3y_intraday_kd_v2)"""
    return _shioaji_download(api, sid, lookback_days=60, seg_days=30)
'''

c = c[:idx_login] + new_login + c[idx_merge:]

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

import ast
ast.parse(c)
print('OK')
