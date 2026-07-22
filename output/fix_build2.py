fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\build_60d_kd_db.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

# Fix download: add dt_module import, use UTC aware conversion
old = '''def download(api, sid):
    """60天1分K，14天/段。Shioaji ts 為 UTC，轉台北時間"""
    end=datetime.now(); start=end-timedelta(days=60)'''

new = '''def download(api, sid):
    """60天1分K，14天/段。Shioaji ts 為 UTC，轉台北時間"""
    import datetime as dt_module
    end=datetime.now(); start=end-timedelta(days=60)'''

c = c.replace(old, new, 1)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

import ast
ast.parse(c)
print('OK')
