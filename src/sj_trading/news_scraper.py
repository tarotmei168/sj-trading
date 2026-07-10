# -*- coding: utf-8 -*-
"""
新聞輿情爬蟲（免 Token，直接爬主流財經媒體）
==========================================
來源：鉅亨網、工商時報、經濟日報、Yahoo奇摩股市
"""
import urllib.request, json, os, re, time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(BASE, "output")
os.makedirs(OUTPUT, exist_ok=True)
CACHE_FILE = os.path.join(OUTPUT, "news_sentiment.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 監控標的對照（stock_id -> 中文名）
WATCH = {
    "2436":"偉詮電","2337":"旺宏","5351":"鈺創","3673":"TPK-KY",
    "3711":"日月光","4958":"臻鼎-KY","3042":"晶技","2454":"聯發科",
    "2317":"鴻海","3443":"創意","3661":"世芯","3035":"智原",
    "3231":"緯創","2382":"廣達","3017":"奇鋐","2451":"創見","8150":"南茂",
}

# 鉅亨網：用搜尋方式找個股新聞
def fetch_cnyes_news(stock_id, pages=2):
    """從鉅亨網爬個股新聞"""
    news = []
    for page in range(1, pages+1):
        url = "https://news.cnyes.com/search/v3?keyword=%s&page=%d&limit=5" % (WATCH.get(stock_id, stock_id), page)
        try:
            req = urllib.request.Request(url, headers={"User-Agent":UA})
            resp = urllib.request.urlopen(req, timeout=10)
            j = json.loads(resp.read().decode("utf-8"))
            items = j.get("items",{}).get("data",[]) if isinstance(j.get("items"), dict) else j.get("data",[])
            for item in items:
                title = item.get("title","")
                summary = item.get("summary","")
                pub = item.get("publishAt", 0)
                news.append({"title":title, "summary":summary[:200], "time":pub, "source":"鉅亨網"})
        except:
            pass
    return news

# 情感分析（關鍵字比對）
def analyze(text):
    t = (text or "").lower()
    score = 0.0
    bulls = ["調升","認證","通過","突破","創高","暴增","大漲","供不應求",
             "市佔升","新訂單","擴產","法說","利多","成長","旺季","落底",
             "回升","轉強","買進","加碼","受惠","谷底"]
    bears = ["調降","裁員","違約","訴訟","衰退","暴跌","利空","庫存高",
             "需求疲","砍單","價格戰","警戒","示警","跌破","賣壓","虧損",
             "減資","打入全額交割"]
    for kw in bulls:
        if kw in t: score += 0.2
    for kw in bears:
        if kw in t: score -= 0.2
    return max(-1.0, min(1.0, score))

def scan():
    print("="*60)
    print("  📰 新聞輿情掃描")
    print("  %s" % datetime.now().strftime('%Y-%m-%d %H:%M'))
    print("="*60)
    
    results = {}
    
    # 各大盤新聞（用"台股"關鍵字）
    print("\n  大盤新聞...", end=" ", flush=True)
    mkt_news = fetch_cnyes_news("台股", 2)
    print("%d 則" % len(mkt_news))
    for n in mkt_news[:5]:
        s = n["title"] + n["summary"]
        sc = analyze(s)
        print("    [%+.2f] %s" % (sc, n["title"][:50]))
    
    # 各股新聞
    for sid, sname in WATCH.items():
        print("\n  %s %s..." % (sid, sname), end=" ", flush=True)
        news = fetch_cnyes_news(sid, 1)
        if not news:
            print("無")
            continue
        print("%d 則" % len(news))
        
        scores = []
        news_items = []
        for n in news[:3]:
            full = n["title"] + " " + n["summary"]
            sc = analyze(full)
            scores.append(sc)
            news_items.append({"title":n["title"][:80],"source":"鉅亨網","score":sc})
            print("    [%+.2f] %s" % (sc, n["title"][:50]))
        
        avg = sum(scores)/len(scores) if scores else 0
        results[sid] = {"name":sname,"score":round(avg,2),"count":len(news),"news":news_items}
    
    # 儲存
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"time":datetime.now().strftime("%H:%M"),"results":results}, f, ensure_ascii=False, indent=2)
    print("\n  💾 已儲存: %s" % CACHE_FILE)
    
    # 摘要
    print("\n📊 輿情摘要:")
    for sid, r in sorted(results.items(), key=lambda x: x[1]["score"], reverse=True):
        e = "🔥" if r["score"]>=0.3 else "📈" if r["score"]>0 else "➖" if r["score"]==0 else "📉" if r["score">=-0.3] else "⚠️"
    print("  (sorting error)")

if __name__ == "__main__":
    scan()
