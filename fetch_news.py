# -*- coding: utf-8 -*-
"""晨報爬蟲：新聞 + 台指期夜盤 + 費半"""
import json, urllib.request
from datetime import datetime

def get_news(limit=8):
    url="https://news.cnyes.com/api/v3/news/category/tw_stock?limit=20&page=1"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=5) as r:
            data=json.loads(r.read().decode("utf-8"))
        items=data.get("items",{}).get("list",[]) if "items" in data else data.get("list",[])
        news=[]
        for item in items[:limit]:
            news.append({"title":item.get("title",""),"date":str(item.get("publishedAt",""))[:10]})
        return news
    except: return [{"title":"連線失敗","date":""}]

def get_quote(url):
    """使用 web_fetch 的回傳格式，這裡先模擬"""
    import subprocess, sys
    try:
        result=subprocess.run([sys.executable,"-c","import urllib.request,json;req=urllib.request.Request('"+url.replace("'","")+"',headers={'User-Agent':'Mozilla/5.0'});print(urllib.request.urlopen(req,timeout=5).read().decode())"],capture_output=True,text=True,timeout=8)
        data=json.loads(result.stdout)
        return data
    except: return None

def get_futures_night():
    """從期交所抓台指期夜盤"""
    from datetime import datetime
    today=datetime.now().strftime("%Y/%m/%d")
    url=f"https://www.taifex.com.tw/cht/3/futAndOptClose?queryType=2&marketCode=0&commodityId=TX&out=html&MarketCode=0&COMMODITY_ID=TX&queryDate={today}"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=5) as r:
            html=r.read().decode("cp950","ignore")
        # 找收盤價
        import re
        prices=re.findall(r'<td[^>]*>([\d,]+\.?\d*)</td>',html)
        if len(prices)>=6:
            return f"{prices[5]}"
        return "盤中"
    except: return "連線失敗"

def get_sox_close():
    """從 Google Finance 抓費半"""
    url="https://www.google.com/finance/quote/SOXX:INDEXNASDAQ"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=5) as r:
            html=r.read().decode("utf-8","ignore")
        import re
        m=re.search(r'"lbl":"SOXX[^}]*?"(?:l)|finalPrice[^"]*"[^"]*"([\d,.]+)',html)
        if m: return m.group(1)
        m2=re.search(r'class="YMlKec"[^>]*>([\d,.]+)',html)
        if m2: return m2.group(1)
        return "查無"
    except: return "連線失敗"

def get_night_summary():
    fut=get_futures_night()
    sox=get_sox_close()
    lines=[]
    lines.append(f"台指期夜盤: {fut}")
    lines.append(f"費半指數: {sox}")
    lines.append("明日預測: ⚪ 待開盤確認")
    return lines

if __name__=="__main__":
    for l in get_night_summary():
        print(l)
    print()
    for n in get_news():
        print(f"📰 {n['date']} {n['title']}")
