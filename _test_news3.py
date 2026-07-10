# -*- coding: utf-8 -*-
import urllib.request, re, json, sys

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def get_cnyes_news(category='tw_stock', limit=6):
    """鉅亨網台股新聞"""
    url = f'https://news.cnyes.com/api/v3/news/category/{category}?limit={limit}&page=1'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', {}).get('data', [])
        return [item.get('title', '')[:60] for item in items]
    except:
        return []

def get_yahoo_news(limit=8):
    """Yahoo Finance 新聞"""
    url = 'https://finance.yahoo.com/news/'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        titles = []
        # 找 h3 下的連結
        for part in html.split('<h3')[1:]:
            m = re.search(r'href=\"([^\"]+)\"[^>]*>([^<]+)<', part)
            if m:
                t = m.group(2).strip()
                if t and len(t) > 10:
                    titles.append(t[:60])
                    if len(titles) >= limit:
                        break
        return titles
    except:
        return []

# 測試
print('=== 鉅亨網台股新聞 ===')
for t in get_cnyes_news('tw_stock', 6):
    print(f'  {t}')

print()
print('=== 鉅亨網國際/美股 ===')
for t in get_cnyes_news('world', 6):
    print(f'  {t}')

print()
print('=== Yahoo Finance Headlines ===')
for t in get_yahoo_news(8):
    print(f'  {t}')
