import json
d = json.load(open(r'C:\Users\User\.openclaw\workspace\sj-trading\src\backtest_6m_v4.json'))

# 分類統計
hot_stocks = [(k,v) for k,v in d.items() if v['category']=='熱門']
overlap = [k for k,v in d.items() if v['category']=='0050' and k in [h for h,_ in hot_stocks]]

print("熱門池總共:", len(hot_stocks), "檔")
print("其中也是0050:", len(overlap), "檔（已在0050裡）")
print("純熱門非0050:", len(hot_stocks)-len(overlap), "檔")
print()

# 列出我當初定義的20支熱門股
hot_20 = ["2330","2454","2317","2303","2344","2408","6770","2603","2609","2618","2610","2888","2892","2881","2882","3037","3189","8046","3711","2382"]
print("我定義的永豐金熱門20檔:")
for k in hot_20:
    found = False
    for sk,sv in d.items():
        if sk==k:
            if sv['category']=='0050':
                print(f"  {sk} {sv['name']} ← 已算在0050")
            else:
                print(f"  {sk} {sv['name']} +{sv['best']['pnl']:.1f}%")
            found=True
            break
    if not found:
        print(f"  {k} ← 回測失敗或不在結果中")

print()

# 我漏了哪些?
hot_only = [k for k in hot_20 if k not in [h for h,v in hot_stocks]]
hot_only_0050 = [k for k in hot_20 if k in overlap]
print(f"漏掉的熱門股(在0050已算): {len(hot_only_0050)} 檔")
print(f"漏掉的熱門股(不在0050): {len(hot_only)} 檔")
for k in hot_only:
    print(f"  {k}")

print()
# 列出所有在回測結果中的0050
print("="*50)
print("0050全部47檔:")
for k,v in sorted(d.items()):
    if v['category']=='0050':
        print(f"  {k} {v['name']} +{v['best']['pnl']:.1f}%")
