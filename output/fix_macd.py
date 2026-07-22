fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\fubon_trust_scanner.py'
with open(fpath, encoding='utf-8') as f:
    content = f.read()

# Pattern 1 (from_db, line 98)
old1 = '    macd_s=f"{bar_html} {h_last:.1f} {direction}{flip_warn}"\n    \n    # RSI(30分K)\n    rsi_arr=talib.RSI(close,timeperiod=14)\n    rsi_val=round(float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50,1)\n    \n    # 30日最低（30分K低點）'
new1 = '    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}<br><span style=\\"font-size:14px;color:var(--text-muted)\\">{h5_str}</span>"\n    \n    # RSI(30分K)\n    rsi_arr=talib.RSI(close,timeperiod=14)\n    rsi_val=round(float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50,1)\n    \n    # 30日最低（30分K低點）'

# Pattern 2 (finmind, line 165)
old2 = '    macd_s=f"{bar_html} {h_last:.1f} {direction}{flip_warn}(日K)"\n    \n    rsi_arr=talib.RSI(close,timeperiod=14)'
new2 = '    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}(日K)<br><span style=\\"font-size:14px;color:var(--text-muted)\\">{h5_str}</span>"\n    \n    rsi_arr=talib.RSI(close,timeperiod=14)'

# Pattern 3 (shioaji, line 271)
old3 = '    macd_s=f"{bar_html} {h_last:.1f} {direction}{flip_warn}"\n    \n    rsi_arr=talib.RSI(close,timeperiod=14)\n    rsi_val=round(float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50,1)\n    \n    low_30d=round(float(np.min(low[-30:])),1) if len(low)>=30 else None'
new3 = '    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}<br><span style=\\"font-size:14px;color:var(--text-muted)\\">{h5_str}</span>"\n    \n    rsi_arr=talib.RSI(close,timeperiod=14)\n    rsi_val=round(float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50,1)\n    \n    low_30d=round(float(np.min(low[-30:])),1) if len(low)>=30 else None'

print("P1:", old1 in content)
print("P2:", old2 in content)
print("P3:", old3 in content)

content = content.replace(old1, new1, 1)
content = content.replace(old2, new2, 1)
content = content.replace(old3, new3, 1)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
