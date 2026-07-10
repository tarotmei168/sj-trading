import re
c = open('daily_report_v3.py','r',encoding='utf-8').read()
# 找3711日月光那行，在前面插入TPKKY
old = '   ("3711"'
new = '   ("3673","TPKKY","PCB小而美，股性活潑","買氣93%超強，暫不需急賣\\n今日K=81高檔死叉，注意回檔，防守75"),\n   ("3711"'
c = c.replace(old, new)
open('daily_report_v3.py','w',encoding='utf-8').write(c)
print('done')
