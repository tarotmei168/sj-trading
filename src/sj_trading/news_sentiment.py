# -*- coding: utf-8 -*-
"""
新聞輿情大腦 (News Sentiment Agent)
=====================================
🌙 晚上(20:00-08:30)：抓18檔核心持股+大盤24小時新聞，AI情感打分
☀️ 盤中(09:00-13:35)：新聞配合技術面雙重濾網，升級預警等級

資料源：FinMind TaiwanStockNews（鉅亨網、工商時報、經濟日報、Yahoo財經）
"""
import urllib.request, json, os, csv
from datetime import datetime, timedelta
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
OUTPUT = os.path.join(BASE, "output")
os.makedirs(OUTPUT, exist_ok=True)

UA = "Mozilla/5.0"
CACHE_FILE = os.path.join(DB, "news_cache.json")
SENTIMENT_FILE = os.path.join(OUTPUT, "news_sentiment_today.json")

# ═══════════════════════════════════════════════
#  監控標的（與 DayMonitor 同步）
# ═══════════════════════════════════════════════
WATCH_STOCKS = {
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "3711": "日月光", "4958": "臻鼎-KY", "3042": "晶技",
    "2454": "聯發科", "2317": "鴻海",
    "3443": "創意", "3661": "世芯", "3035": "智原",
    "3231": "緯創", "2382": "廣達", "3017": "奇鋐", "2451": "創見", "8150": "南茂",
}

def fetch_news(stock_id, hours=24):
    """從FinMind抓取個股最近N小時的新聞"""
    end = datetime.now()
    start = end - timedelta(hours=hours)
    url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockNews&data_id=%s&start_date=%s&end_date=%s" % (
        stock_id, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=15)
        j = json.loads(resp.read().decode("utf-8"))
        if j.get("status") == 200:
            return j.get("data", [])
    except:
        pass
    return []

def fetch_news_taiex(hours=24):
    """抓大盤新聞"""
    return fetch_news("TAIEX", hours)

def analyze_sentiment(title, content=""):
    """
    AI情感打分（模擬DeepSeek評分）
    實際使用時可改成調用本地LLM API
    
    規則：根據新聞標題關鍵字判斷情感分數
    回傳: -1.0 ~ +1.0 之間的分數
    """
    text = (title + " " + content).lower()
    
    # 強烈利多關鍵字
    strong_bullish = ["調升目標價", "認證", "通過", "突破", "創新高", "暴增",
                      "大漲", "供不應求", "市佔率提升", "新訂單", "擴大產能",
                      "法說會", "利多", "成長", "旺季來臨", "落底反彈"]
    
    # 強烈利空關鍵字
    strong_bearish = ["調降目標價", "裁員", "違約", "訴訟", "衰退", "暴跌",
                      "利空", "庫存過高", "需求疲軟", "客戶砍單", "價格戰",
                      "警戒", "示警", "跌破", "賣壓"]
    
    # 中性偏多
    mild_bullish = ["回穩", "觀察", "布局", "逢低", "抗震", "展望",
                    "關注", "有撐", "反彈"]
    
    # 中性偏空
    mild_bearish = ["震盪", "觀望", "整理", "回檔", "修正", "壓力",
                    "保守", "審慎"]
    
    score = 0.0
    
    for kw in strong_bullish:
        if kw in text:
            score += 0.3
    
    for kw in strong_bearish:
        if kw in text:
            score -= 0.3
    
    for kw in mild_bullish:
        if kw in text:
            score += 0.15
    
    for kw in mild_bearish:
        if kw in text:
            score -= 0.15
    
    # 限制在 -1 ~ +1 之間
    return max(-1.0, min(1.0, score))


def scan_all_news(hours=24):
    """掃描所有監控標的 + 大盤的新聞"""
    print("\n" + "="*60)
    print("  📰 新聞輿情掃描")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("="*60)
    
    results = {}
    
    # 1. 大盤新聞
    print("\n  大盤 TAIEX...", end=" ", flush=True)
    news = fetch_news_taiex(hours)
    if news:
        print("%d 則" % len(news))
        for n in news[:3]:
            title = n.get("title", "")
            score = analyze_sentiment(title)
            print("    [%+.2f] %s" % (score, title[:60]))
    else:
        print("無")
    
    # 2. 各股新聞
    for sid, sname in WATCH_STOCKS.items():
        print("\n  %s %s..." % (sid, sname), end=" ", flush=True)
        news = fetch_news(sid, hours)
        if not news:
            print("無新聞")
            continue
        
        print("%d 則" % len(news))
        
        # 取最近3則
        scores = []
        news_items = []
        for n in news[:5]:
            title = n.get("title", "")
            content = n.get("content", "")[:200]
            pub_time = n.get("date", "")
            source = n.get("source", "")
            score = analyze_sentiment(title, content)
            scores.append(score)
            news_items.append({
                "title": title[:80],
                "source": source,
                "time": pub_time,
                "score": score,
            })
            print("    [%+.2f] %s" % (score, title[:60]))
        
        # 平均分數
        avg_score = sum(scores) / len(scores) if scores else 0
        results[sid] = {
            "name": sname,
            "score": round(avg_score, 2),
            "news_count": len(news),
            "news": news_items[:3],
            "latest_time": news_items[0]["time"] if news_items else "",
        }
    
    # 3. 儲存結果
    with open(SENTIMENT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "period_hours": hours,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print("\n  💾 已儲存: %s" % SENTIMENT_FILE)
    
    return results


def get_sentiment_for_report():
    """讀取新聞情感評分（供晨報使用）"""
    if os.path.exists(SENTIMENT_FILE):
        try:
            with open(SENTIMENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("results", {})
        except:
            pass
    return {}


def get_sentiment_emoji(score):
    """分數轉表情"""
    if score >= 0.5: return "🔥🔥"
    elif score >= 0.2: return "📈"
    elif score >= -0.2: return "➖"
    elif score >= -0.5: return "📉"
    else: return "⚠️⚠️"


if __name__ == "__main__":
    results = scan_all_news(hours=72)  # 第一次跑抓72小時建立資料
    print("\n📊 新聞輿情摘要:")
    for sid, r in sorted(results.items(), key=lambda x: x[1]["score"], reverse=True):
        emoji = get_sentiment_emoji(r["score"])
        print("  %s %s %s [%+.2f] %d則" % (sid, r["name"], emoji, r["score"], r["news_count"]))
