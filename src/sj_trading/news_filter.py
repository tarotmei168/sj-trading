# -*- coding: utf-8 -*-
"""
FinMind 新聞過濾引擎
====================
1. 從 FinMind TaiwanStockNews 抓個股新聞
2. 用關鍵字過濾：只保留產業大事（法說、財報、訂單、擴產、缺料、漲價等）
3. 儲存到 output/news_filtered.json 供晨報使用
"""
import os, json, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(BASE, "output")
os.makedirs(OUTPUT, exist_ok=True)
CACHE = os.path.join(OUTPUT, "news_filtered.json")

# 監控標的
WATCH = [
    ("2436","偉詮電"),("2337","旺宏"),("5351","鈺創"),
    ("3673","TPK-KY"),("3711","日月光"),("4958","臻鼎-KY"),("3042","晶技"),
    ("2454","聯發科"),("2317","鴻海"),
    ("3443","創意"),("3661","世芯"),("3035","智原"),
    ("3231","緯創"),("2382","廣達"),("3017","奇鋐"),("2451","創見"),("8150","南茂"),
    # 記憶體
    ("2344","華邦電"),("6770","力積電"),
    # 大盤
    ("TAIEX","大盤加權"),
]

# ⭐ 產業大事關鍵字（只保留這些，其他小道消息全部過濾）
IMPORTANT_KW = [
    "法說會","法人說明會",
    "營收","財報","EPS","獲利",
    "訂單","接單",
    "擴產","擴廠","產能",
    "缺料","漲價","供不應求",
    "調升","調降",
    "通過認證","認證通過",
    "合約","簽約",
    "股利","股息","除息","除權",
    "上市","上櫃",
    "併購","收購","入股",
    "新產品","新品發表",
    "量產",
    "募資",
    "整併",
]

def fetch_news(stock_id, date_str):
    """用 FinMind 抓單日新聞"""
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        df = dl.taiwan_stock_news(stock_id=stock_id, start_date=date_str, end_date="")
        if df is not None and len(df) > 0:
            return df.to_dict("records")
    except:
        pass
    return []

def filter_important(news_list):
    """用關鍵字過濾：只留產業大事"""
    important = []
    for n in news_list:
        title = (n.get("title","") + " " + n.get("content",""))
        for kw in IMPORTANT_KW:
            if kw in title:
                important.append(n)
                break
    return important

def summarize_news(news_list):
    """摘要新聞：最多3則，每則30字以內"""
    summaries = []
    seen = set()
    for n in news_list:
        title = n.get("title","").strip()
        source = n.get("source","").strip()
        
        # 去重
        key = title[:30]
        if key in seen:
            continue
        seen.add(key)
        
        # 簡短摘要：取來源+標題關鍵部分
        short = title[:35].replace(source,"").strip()
        summaries.append("%s｜%s" % (source[:4], short))
        
        if len(summaries) >= 3:
            break
    
    return summaries

def scan_all():
    """掃描所有監控標的的新聞"""
    print("="*60)
    print("  📰 FinMind 新聞過濾引擎")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("="*60)
    
    # 抓今天和昨天的新聞
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    results = {}
    
    for sid, sname in WATCH:
        print("\n  %s %s..." % (sid, sname), end=" ", flush=True)
        
        all_news = []
        for date_str in [today, yesterday]:
            news = fetch_news(sid, date_str)
            if news:
                all_news.extend(news)
        
        if not all_news:
            print("無新聞")
            results[sid] = {"name": sname, "count": 0, "summaries": []}
            continue
        
        # 過濾重要新聞
        important = filter_important(all_news)
        print("%d則(重要%d則)" % (len(all_news), len(important)))
        
        if important:
            summaries = summarize_news(important)
            for s in summaries:
                print("    📌 %s" % s)
        else:
            summaries = []
            print("    無重大產業新聞")
        
        results[sid] = {
            "name": sname,
            "count": len(all_news),
            "important_count": len(important),
            "summaries": summaries,
        }
    
    # 儲存
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump({
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print("\n  💾 已儲存: %s" % CACHE)
    
    return results


def get_for_report():
    """供晨報讀取新聞摘要"""
    if os.path.exists(CACHE):
        try:
            with open(CACHE, "r", encoding="utf-8") as f:
                return json.load(f).get("results", {})
        except:
            pass
    return {}


if __name__ == "__main__":
    scan_all()
