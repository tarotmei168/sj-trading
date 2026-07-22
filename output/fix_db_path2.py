import sys

fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\fubon_trust_scanner.py'
with open(fpath, encoding='utf-8') as f:
    c = f.read()

old = '''def calc_30min_kd_macd_rsi_from_db(sid):
    """從 database/3y_kd/ 讀取30分K OHLC，TA-Lib 全算"""
    f=os.path.join(DB_DIR,f"{sid}_kd.csv")
    if not os.path.isfile(f): return None
    try:
        df=pd.read_csv(f)
    except: return None
    if len(df)<30: return None'''

new = '''def calc_30min_kd_macd_rsi_from_db(sid):
    """從 database/30min_60d/ 讀取60天30分K，無則讀 database/3y_kd/"""
    f=os.path.join(DB_DIR,f"{sid}_60d.csv")
    if not os.path.isfile(f):
        f=os.path.join(DB_3Y_DIR,f"{sid}_kd.csv")
        if not os.path.isfile(f): return None
    try:
        df=pd.read_csv(f)
    except: return None
    if len(df)<30: return None'''

assert old in c, "pattern not found"
c = c.replace(old, new, 1)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

# Also update data source comment and print
c2 = c
c2 = c2.replace(
    '資料來源: database/3y_kd/（核心持股）+ Shioaji 60天1分K（潛力股）',
    '資料來源: database/30min_60d/（60天30分K）+ database/3y_kd/（3年回測備用）'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c2)

print("OK")
