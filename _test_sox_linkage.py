# 測試 SOX + 聯動表的資料正確性
import sys, io, contextlib
sys.path.insert(0, 'src/sj_trading')
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("🔍 SOX 指數檢查")
print("=" * 60)

import yfinance as yf
with contextlib.redirect_stderr(io.StringIO()):
    t = yf.Ticker('^SOX')
    df = t.history(period='5d')

if df is not None and len(df) >= 2:
    import pandas as pd
    for idx, row in df.iterrows():
        print(f"  {idx.date()}  Close={row['Close']:.2f}  Vol={row['Volume']:,.0f}")
    
    closes = df['Close'].values
    print(f"\n  昨天: {closes[-2]:.2f} → 今天: {closes[-1]:.2f}")
    print(f"  漲跌: {(closes[-1]/closes[-2] - 1)*100:+.2f}%")
else:
    print("  ⚠️ 無資料")

print()
print("=" * 60)
print("🔗 LINKAGE_40 聯動檢查")
print("=" * 60)

from global_weather import LINKAGE_MAP, get_us_stock_change

# 只檢查前10組，看看每組能不能抓到資料
count_ok = 0
count_fail = 0
for sym, info in list(LINKAGE_MAP.items())[:20]:
    chg, close = get_us_stock_change(sym)
    if chg is not None:
        print(f"  ✅ {sym:6s} {info['name']:12s} {chg:+.2f}% 收{close}")
        count_ok += 1
    else:
        print(f"  ❌ {sym:6s} {info['name']:12s} 抓不到資料")
        count_fail += 1

print(f"\n共 {count_ok} 成功 / {count_fail} 失敗")
