# -*- coding: utf-8 -*-
"""
全市場3年資料下載（逐日抓取）
=============================
邏輯：每天發1次請求拿「全市場所有股票當天日K」
720個交易日 = 720次請求
每檔股票都不會漏掉，且跟三竹完全對齊

產出：database/market_YYYYMMDD.csv（每天1檔）
"""
import urllib.request, json, os, csv, time
from datetime import datetime, timedelta

UA = "Mozilla/5.0"
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
os.makedirs(DB, exist_ok=True)

def fetch_all_stocks_by_date(date_str):
    """抓特定日期全市場所有股票的日K"""
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&start_date=%s&end_date=%s" % (date_str, date_str)
    req = urllib.request.Request(url, headers={"User-Agent":UA})
    resp = urllib.request.urlopen(req, timeout=60)
    j = json.loads(resp.read().decode("utf-8"))
    if j.get("status") == 200:
        return j.get("data", [])
    return None

def get_trading_dates(start_date, end_date):
    """產生所有交易日清單（週一到週五）"""
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 週一到週五
            dates.append(current)
        current += timedelta(days=1)
    return dates

# 設定時間範圍
end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
start_date = end_date - timedelta(days=3*365)

# 找出所有交易日
trading_dates = get_trading_dates(start_date, end_date)
total = len(trading_dates)
print("="*60)
print("  全市場3年資料下載（逐日抓取）")
print("  範圍: %s ~ %s" % (trading_dates[0].strftime('%Y/%m/%d') if trading_dates else '?', 
      trading_dates[-1].strftime('%Y/%m/%d') if trading_dates else '?'))
print("  預估交易日: %d 天 = %d 次請求" % (total, total))
print("="*60)

# 檢查已有檔案，跳過已下載的
already = set()
for f in os.listdir(DB):
    if f.startswith("market_") and f.endswith(".csv"):
        already.add(f.replace("market_", "").replace(".csv", ""))

print("  已存在: %d 天" % len(already))

todo = [d for d in trading_dates if d.strftime("%Y%m%d") not in already]
print("  待下載: %d 天" % len(todo))

if not todo:
    print("  全部已完成！")
else:
    success = 0; fail = 0
    for i, d in enumerate(todo):
        ds = d.strftime("%Y-%m-%d")
        fname = "market_%s.csv" % d.strftime("%Y%m%d")
        fpath = os.path.join(DB, fname)
        
        print("  [%d/%d] %s ..." % (i+1, len(todo), ds), end=" ", flush=True)
        data = fetch_all_stocks_by_date(ds)
        
        if data and len(data) > 0:
            with open(fpath, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["stock_id","open","high","low","close","volume"])
                for r in data:
                    w.writerow([r["stock_id"], r["open"], r["max"], r["min"], r["close"], 
                               r.get("Trading_Volume",0)])
            print("%d 筆 ✅" % len(data))
            success += 1
        else:
            print("❌")
            fail += 1
        
        # 每10次休息1秒，避免被擋
        if i % 10 == 0 and i > 0:
            time.sleep(1)
    
    print()
    print("="*60)
    print("  下載完成！")
    print("  成功: %d 天" % success)
    print("  失敗: %d 天" % fail)
    print("  總檔案: %d 天" % len([f for f in os.listdir(DB) if f.startswith("market_")]))
    print("="*60)
