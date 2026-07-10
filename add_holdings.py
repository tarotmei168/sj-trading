c = open('daily_report_v3.py','r',encoding='utf-8').read()
insert = '''    ("4958","臻鼎KY","PCB大廠，股性穩健","趨勢偏多，K<D但MACD柱負，量能萎縮\n防守30分K MA20約570，等量增金叉再考慮加碼"),
    ("3711","日月光","全球封測龍頭，權值股","K81超買+RSI83，追價力道盤整\n高檔注意回檔，守今日低點680，跌破減碼"),\n'''
old = 'CORE_HOLDINGS = [\n'
c = c.replace(old, old + insert)
open('daily_report_v3.py','w',encoding='utf-8').write(c)
print('done')
