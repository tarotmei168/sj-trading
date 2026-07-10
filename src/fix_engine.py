import re
p = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\triple_engine.py'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()

# Fix: 重大事件警報! ({len(critical)}則}") -> add missing )
s = s.replace(
    '重大事件警報! ({len(critical)}則}")',
    '重大事件警報! ({len(critical)}則)")'
)

with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print('Fixed!')
