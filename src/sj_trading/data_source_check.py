"""
盘中资料源健康检查 — 找即时买卖超、大户、法人资料
"""
import sys, os, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

results = []

def test(name, url, parse_fn):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        raw = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='replace')
        data = json.loads(raw)
        result = parse_fn(data)
        results.append(f"[{'✅' if result else '❌'}] {name}: {result or '空資料'}")
    except Exception as e:
        results.append(f"[❌] {name}: {e}")

# ===== 1. TWSE 盤後三大法人 =====
test("TWSE 三大法人 (盤後/前日)", 
     "https://www.twse.com.tw/fund/T86?response=json&date=20260703&selectType=ALL",
     lambda d: f'{d.get("total",0)} 筆 (前日)' if d.get("total") else None)

# ===== 2. 鉅亨即時報價 =====
test("鉅亨 2330 即時報價",
     "https://ws.api.cnyes.com/ticks/api/v1/tickers/2330/real-time?type=day",
     lambda d: f'close={d.get("close")} vol={d.get("volume")}' if d.get("close") else None)

# ===== 3. 鉅亨盤中逐筆 =====
test("鉅亨 2330 盤中逐筆",
     "https://ws.api.cnyes.com/ticks/api/v1/tickers/2330/ticks?type=tick",
     lambda d: f'{len(d.get("data",{}).get("items",[]))} 筆' if d.get("data") else None)

# ===== 4. 鉅亨盤中分價量 =====
test("鉅亨 2330 分價量",
     "https://ws.api.cnyes.com/ticks/api/v1/tickers/2330/ticks?type=day",
     lambda d: f'{len(d.get("data",{}).get("items",[]))} 筆分K' if d.get("data") else None)

# ===== 5. Goodinfo 法人買賣超 (即時/盤中) =====
test("Goodinfo 2330 法人買賣超",
     "https://goodinfo.tw/StockInfo/StockDetail.asp?STOCK_ID=2330",
     lambda d: f'抓到頁面 {len(str(d))} chars' if d else None)

print("\n=== 📡 資料源健康檢查 ===\n")
for r in results:
    print(r)

# 額外：試試鉅亨的分價量表結構
print("\n=== 鉅亨逐筆詳細結構 ===\n")
try:
    req = urllib.request.Request("https://ws.api.cnyes.com/ticks/api/v1/tickers/2330/ticks?type=tick", headers=HEADERS)
    raw = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='replace')
    data = json.loads(raw)
    items = data.get("data",{}).get("items",[])
    if items:
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:500])
    print(f"總筆數: {len(items)}")
except Exception as e:
    print(f"❌ {e}")
