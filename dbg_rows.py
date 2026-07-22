#!/usr/bin/env python3
"""Check potential stocks rows in HTML"""
import re
with open('web/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('潛力股候選')
sec = html[idx:idx+4000]
tb = sec.find('<tbody>')
te = sec.find('</tbody>')
body = sec[tb+7:te]
rows = re.findall(r'<tr>.*?</tr>', body, re.DOTALL)
print(f'潛力股行數: {len(rows)}')
for r in rows:
    m = re.search(r'<b>(.*?)</b>', r)
    if m:
        print(f'  {m.group(1)}')
