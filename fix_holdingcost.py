import os
files = [
    'morning_report.py',
    'morning_report_html.py',
    'src/sj_trading/alert_system.py',
]
old = 'HOLDING_COST = {"3711": 481, "4958": 461, "3042": 196, "2337": 174, "2436": 76, "3673": 51.69}'
new = 'HOLDING_COST = {}'
for f in files:
    if os.path.exists(f):
        c = open(f, 'r', encoding='utf-8').read()
        if old in c:
            c = c.replace(old, new)
            open(f, 'w', encoding='utf-8').write(c)
            print(f'fixed {f}')
print('done')
