import requests, json, sys, re
sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.twse.com.tw/fund/T86"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/zh/page/trading/fund/T86.html",
    "X-Requested-With": "XMLHttpRequest",
})

d = "20260722"
# selectType=ALL 但指定 selectType=ALL 不傳投信資料的情況
# 試試不同方式: 不加 selectType 參數（預設全部）
resp = session.get(url, params={"response": "json", "date": d}, timeout=20)
data = resp.json()
print(f"不加selectType: stat={data.get('stat')}, 筆數={len(data.get('data',[]))}")
print(f"欄位: {data.get('fields', [])}")
print(f"第一筆: {data['data'][0]}")
print()

# 試試 selectType=ALL
resp2 = session.get(url, params={"response": "json", "date": d, "selectType": "ALL"}, timeout=20)
data2 = resp2.json()
print(f"selectType=ALL: stat={data2.get('stat')}, 筆數={len(data2.get('data',[]))}")
# 直接找投信買超>0的
count = 0
for row in data2['data']:
    code = row[0].strip()
    if not re.match(r'^\d{4}$', code):
        continue
    trust_net_str = row[10].strip() if len(row) > 10 and row[10].strip() else "0"
    trust_net = int(trust_net_str.replace(",","")) if trust_net_str != "0" else 0
    if trust_net > 0:
        name = row[1].strip()
        print(f"  {code} {name:10s} 投信買超 {trust_net:>8,} 張")
        count += 1
        if count >= 20:
            break
if count == 0:
    print("  (無投信買超>0的資料)")
    # 顯示欄位
    print(f"  第一筆: {data2['data'][0]}")
    print(f"  欄位10: {data2['data'][0][10] if len(data2['data'][0]) > 10 else '無'}")
    print(f"  欄位長度: {len(data2['data'][0])}")
