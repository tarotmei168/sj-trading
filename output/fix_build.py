fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\build_60d_kd_db.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

c = c.replace('.resample("30min"].', '.resample("30min").')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
print('OK')
