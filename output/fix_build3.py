fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\build_60d_kd_db.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

# Remove dt_module import from function
c = c.replace(
    '    import datetime as dt_module\n    """60天1分K，14天/段。Shioaji ts \xe7\x82\xba UTC\xef\xbc\x8c\xe8\xbd\x89\xe5\x8f\xb0\xe5\x8c\x97\xe6\x99\x82\xe9\x96\x93"""',
    '    """60天1分K，14天/段。Shioaji ts \xe7\x82\xba UTC\xef\xbc\x8c\xe8\xbd\x89\xe5\x8f\xb0\xe5\x8c\x97\xe6\x99\x82\xe9\x96\x93"""'
)

# Replace datetime.timezone.utc with timezone_utc (defined at module level)
c = c.replace('datetime.timezone.utc', 'timezone_utc')
c = c.replace(
    'from datetime import datetime, timedelta',
    'from datetime import datetime, timedelta, timezone\ntimezone_utc = timezone.utc'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
import ast; ast.parse(c); print('OK')
