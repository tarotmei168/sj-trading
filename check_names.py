import re
c = open('daily_report_v2.py','r',encoding='utf-8').read()
matches = re.findall(r'"name":"(\d+)"', c)
for m in matches:
    print(f'Need fix: {m}')
print(f'Total: {len(matches)}')
