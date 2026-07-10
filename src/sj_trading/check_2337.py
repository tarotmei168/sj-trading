# -*- coding: utf-8 -*-
"""旺宏(2337)完整分析"""
import csv, os, numpy as np

DB = os.path.expanduser(r"~/.openclaw/workspace/sj-trading/database")

dates = []; c_list = []; h_list = []; l_list = []; v_list = []
with open(os.path.join(DB, "2337_3y.csv"), "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        dates.append(row["date"])
        c_list.append(float(row["close"]))
        h_list.append(float(row["high"]))
        l_list.append(float(row["low"]))
        v_list.append(float(row["volume"]))

c = np.array(c_list, dtype=float)
h = np.array(h_list, dtype=float)
l = np.array(l_list, dtype=float)
v = np.array(v_list, dtype=float)

n = len(c)
k = np.zeros(n); d = np.zeros(n)
k[0]=50; d[0]=50
for i in range(1,n):
    ps=max(0,i-9+1)
    hh=np.max(h[ps:i+1]); ll=np.min(l[ps:i+1])
    rsv=(c[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
    k[i]=(2/3)*k[i-1]+(1/3)*rsv
    d[i]=(2/3)*d[i-1]+(1/3)*k[i]

print("=== 旺宏(2337) ===")
print("日期: %s" % dates[-1])
print("收盤: %.1f" % c[-1])
print("K=%.1f  D=%.1f  %s" % (k[-1], d[-1], "K>D多头" if k[-1]>d[-1] else "K<D空头"))

print()
print("近10日:")
for i in range(-10, 0):
    st = ""
    if k[i] < 25: st = "超卖"
    elif k[i] > 80: st = "过热"
    if k[i] > d[i] and k[i] < 40: st = "低档金叉"
    print("  %s 收%.0f K%.1f D%.1f %s %s" % (dates[i][5:], c[i], k[i], d[i], "K>D" if k[i]>d[i] else "K<D", st))

# 支撑
low20 = min(l[-20:])
avg20 = np.mean(c[-20:])
print()
print("20日最低支撑: %.1f" % low20)
print("20日均价: %.1f" % avg20)
print("目前%.1f 距支撑%.1f (%.1f%%)" % (c[-1], c[-1]-low20, (c[-1]/low20-1)*100))

# 3年回测
print()
print("3年KD低档金叉绩效(K<35):")
profits = []
for i in range(1,n):
    if k[i-1]<=d[i-1] and k[i]>d[i] and k[i]<35:
        buy_p = c[i]
        for j in range(i+5,n):
            if k[j-1]>=d[j-1] and k[j]<d[j]:
                profits.append((c[j]-buy_p)/buy_p*100)
                break

if profits:
    wins = sum(1 for p in profits if p>0)
    print("  总交易: %d次" % len(profits))
    print("  胜率: %d%%" % (wins/len(profits)*100))
    print("  平均报酬: %+.2f%%" % np.mean(profits))
    print("  最佳: %+.2f%%  最差: %+.2f%%" % (max(profits), min(profits)))
