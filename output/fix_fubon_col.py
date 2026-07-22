fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\fubon_trust_scanner.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    'times=list(df["datetime"])',
    'times=list(df.get("datetime", [str(i) for i in range(len(df))]))'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

import ast
ast.parse(c)
print('OK')
