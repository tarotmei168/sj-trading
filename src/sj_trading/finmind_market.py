# -*- coding: utf-8 -*-
"""
FinMind 正確接口 — 全市場 + 大盤權值股
=====================================
1. 大盤指數 (TAIEX data_id=001)
2. 權值股 (2330, 2454, 2317, 0050)
3. 全市場投信買賣超 TaiwaneseStockInstitutionalInvestorsBuySell
4. 每日全市場股價 (taiwan_stock_daily用stock_id_list批量)
"""
import urllib.request, json, os, csv, time
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
os.makedirs(DB, exist_ok=True)

UA = "Mozilla/5.0"

def fetch_finmind(params, timeout=30):
    """通用FinMind API請求"""
    url = "https://api.finmindtrade.com/api/v4/data?" + params
    try:
        req = urllib.request.Request(url, headers={"User-Agent":UA})
        resp = urllib.request.urlopen(req, timeout=timeout)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status") == 200:
            return j.get("data", [])
    except Exception as e:
        print("  ERR: %s" % str(e)[:50])
    return None

# ═══════════════════════════════════════════════
#  1. 大盤指數 (TAIEX = stock_id=001)
# ═══════════════════════════════════════════════
def fetch_taiex(years=3):
    """抓加權指數 3 年日K"""
    end = datetime.now()
    start = end - timedelta(days=years*365)
    params = "dataset=TaiwanStockPrice&data_id=001&start_date=%s&end_date=%s" % (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    data = fetch_finmind(params)
    if data:
        path = os.path.join(DB, "TAIEX_3y.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date","open","high","low","close","volume"])
            for r in data:
                w.writerow([r["date"], r["open"], r["max"], r["min"], r["close"], r.get("Trading_Volume",0)])
        print("  大盤(TAIEX): %d笔 收%s ✅" % (len(data), data[-1]["close"] if data else "?"))
        return data
    return None

# ═══════════════════════════════════════════════
#  2. 權值股單獨下載 (台積電/聯發科/鴻海/0050)
# ═══════════════════════════════════════════════
MEGA_STOCKS = {
    "0050": "元大台灣50",
    "2330": "台積電",
    "2454": "聯發科",
    "2317": "鴻海",
}

def fetch_mega_stocks():
    """下載權值大軍3年日K"""
    print("  權值大軍下載:")
    for sid, name in MEGA_STOCKS.items():
        end = datetime.now(); start = end - timedelta(days=3*365)
        params = "dataset=TaiwanStockPrice&data_id=%s&start_date=%s&end_date=%s" % (sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        data = fetch_finmind(params)
        if data and len(data) > 100:
            path = os.path.join(DB, "%s_3y.csv" % sid)
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date","open","high","low","close","volume"])
                for r in data:
                    w.writerow([r["date"], r["open"], r["max"], r["min"], r["close"], r.get("Trading_Volume",0)])
            print("    %s %s: %d笔 收%s ✅" % (sid, name, len(data), data[-1]["close"]))
        else:
            print("    %s %s: 无资料 ❌" % (sid, name))

# ═══════════════════════════════════════════════
#  3. 全市場投信買賣超 (TaiwanStockInstitutionalInvestorsBuySell)
# ═══════════════════════════════════════════════
def fetch_all_institutional(date_str):
    """抓全市場三大法人買賣超（特定日期）"""
    params = "dataset=TaiwanStockInstitutionalInvestorsBuySell&date=%s" % date_str
    data = fetch_finmind(params, timeout=60)
    if data:
        path = os.path.join(DB, "institutional_%s.csv" % date_str.replace("-",""))
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if data:
                w.writerow(list(data[0].keys()))
                for r in data:
                    w.writerow(list(r.values()))
        print("  投信買賣超: %d笔 ✅" % len(data))
    return data

# ═══════════════════════════════════════════════
#  4. 全市場每日股價 (taiwan_stock_daily 批量)
# ═══════════════════════════════════════════════
def fetch_market_daily(date_str):
    """用 TaiwanStockPrice + 特定日期抓全市場"""
    params = "dataset=TaiwanStockPrice&start_date=%s&end_date=%s" % (date_str, date_str)
    data = fetch_finmind(params, timeout=60)
    if data and len(data) > 100:
        path = os.path.join(DB, "market_daily_%s.csv" % date_str.replace("-",""))
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["stock_id","open","high","low","close","volume"])
            for r in data:
                w.writerow([r["stock_id"], r["open"], r["max"], r["min"], r["close"], r.get("Trading_Volume",0)])
        print("  全市場日K: %d笔 ✅" % len(data))
        return data
    return None

# ═══════════════════════════════════════════════
#  🚀 主流程
# ═══════════════════════════════════════════════
def full_init():
    """初始化：大盤+權值+投信+全市場日K"""
    print("="*60)
    print("  FinMind 正確接口初始化")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("="*60)
    
    # 1. 大盤
    print("\n[1] 大盤指數 TAIEX")
    fetch_taiex()
    
    # 2. 權值大軍
    print("\n[2] 權值大軍")
    fetch_mega_stocks()
    
    # 3. 投信買賣超(昨天)
    print("\n[3] 全市場投信買賣超")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    fetch_all_institutional(yesterday)
    
    # 4. 全市場日K(昨天)
    print("\n[4] 全市場日K")
    fetch_market_daily(yesterday)
    
    print("\n"+"="*60)
    print("  ✅ 初始化完成")
    print("  database/ 目錄已有:")
    for f in sorted(os.listdir(DB)):
        size = os.path.getsize(os.path.join(DB, f)) // 1024
        print("    %s (%dKB)" % (f, size))
    print("="*60)


if __name__ == "__main__":
    full_init()
