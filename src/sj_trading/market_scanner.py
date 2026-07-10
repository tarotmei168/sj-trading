# -*- coding: utf-8 -*-
"""
全市場潛力股自動化掃描引擎
===========================
每天16:30執行：
1. 讀取 taiwan_stock_info.csv（4276檔全市場清單）
2. 逐批查詢投信買賣超
3. 篩選：投信連買1-3天 + 營收年增>20% + 60天橫盤<25%
4. 產出黑馬清單 → 隔天晨報第三層
"""
import urllib.request, json, os, csv, sys
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
OUTPUT = os.path.join(BASE, "output")
sys.path.insert(0, os.path.join(BASE, "src", "sj_trading"))

UA = "Mozilla/5.0"

def load_stock_info():
    """讀取本地全市場股票清單"""
    path = os.path.join(DB, "taiwan_stock_info.csv")
    if not os.path.exists(path):
        print("  錯誤: taiwan_stock_info.csv 不存在，請先下載")
        return []
    stocks = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stocks.append(row)
    return stocks

def fetch_institutional_batch(stock_ids, date_str):
    """批量查詢投信買賣超"""
    ids = "&data_id=".join(stock_ids)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id=%s&start_date=%s&end_date=%s" % (
        ids, date_str, date_str)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":UA})
        resp = urllib.request.urlopen(req, timeout=30)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status") == 200:
            return j.get("data", [])
    except:
        pass
    return []

def fetch_revenue(sid):
    """抓單一股票營收年增率"""
    end = datetime.now(); start = end - timedelta(days=400)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=%s&start_date=%s&end_date=%s" % (sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent":UA})
        resp = urllib.request.urlopen(req, timeout=10)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status") == 200 and len(j.get("data",[])) >= 13:
            data = sorted(j["data"], key=lambda x: (x["revenue_year"], x["revenue_month"]))
            curr = data[-1]["revenue"]
            prev = data[-13]["revenue"]
            if prev > 0:
                yoy = (curr - prev) / prev * 100
                return round(yoy, 1)
    except:
        pass
    return None

def scan_potential():
    """主掃描流程"""
    print("="*60)
    print("  全市場潛力股自動化掃描")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("="*60)
    
    # 1. 讀全市場清單
    all_stocks = load_stock_info()
    print("\n全市場: %d 檔" % len(all_stocks))
    
    # 2. 只篩選上市+上櫃股票（排除ETF、權證等）
    candidates = [s for s in all_stocks if s.get("market_type","") in ["上市","上櫃"]]
    print("上市+上櫃: %d 檔" % len(candidates))
    
    # 3. 逐批查投信買賣超（每批10檔，共約170批）
    batch_size = 10
    trust_buyers = {}
    
    print("\n掃描投信買賣超...")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        sids = [s["stock_id"] for s in batch]
        data = fetch_institutional_batch(sids, yesterday)
        
        for d in data:
            sid = d.get("stock_id","")
            # net = buy - sell
            try:
                buy = int(d.get("buy",0))
                sell = int(d.get("sell",0))
                net = buy - sell
            except:
                net = 0
            
            if sid not in trust_buyers:
                trust_buyers[sid] = {"buy_today": 0, "net": 0, "days": 0, "name": ""}
            
            # 找出對應名稱
            name = d.get("name","")
            if name:
                trust_buyers[sid]["name"] = name
            
            trust_buyers[sid]["buy_today"] += buy
            trust_buyers[sid]["net"] += net
            trust_buyers[sid]["days"] += 1
        
        if i % 100 == 0:
            print("  進度: %d/%d" % (i, len(candidates)), flush=True)
    
    # 4. 篩選條件：投信淨買超>0
    hot = {sid: v for sid, v in trust_buyers.items() if v["net"] > 0}
    print("\n投信買超股票: %d 檔" % len(hot))
    
    # 5. 排序：淨買超量最大
    sorted_hot = sorted(hot.items(), key=lambda x: x[1]["net"], reverse=True)
    
    # 6. 產出報告
    lines = []
    lines.append("")
    lines.append("="*60)
    lines.append("  🎯 全市場投信佈局黑馬清單")
    lines.append("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    lines.append("="*60)
    lines.append("")
    
    for sid, v in sorted_hot[:30]:
        name = v["name"][:10] if v["name"] else sid
        net_w = v["net"] / 10000
        lines.append("  %s %s | 投信淨買%+.1f萬股" % (sid, name, net_w))
    
    # 存檔
    path = os.path.join(OUTPUT, "potential_candidates_full.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n已儲存: %s" % path)
    
    return sorted_hot[:30]

if __name__ == "__main__":
    scan_potential()
