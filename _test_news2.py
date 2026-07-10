# -*- coding: utf-8 -*-
import urllib.request, json, re
UA = 'Mozilla/5.0'

# 1. 鉅亨網台股新聞 - API 可以用
print('=== 鉅亨網台股新聞 (cnYES API) ===')
url = 'https://news.cnyes.com/api/v3/news/category/tw_stock?limit=10&page=1'
try:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    for item in data.get('items', {}).get('data', [])[:6]:
        t = item.get('title', '')[:50]
        print(f'  {t}')
except Exception as e:
    print(f'  FAILED: {str(e)[:30]}')

print()
print('=== 搜尋川普/關稅/半導體相關新聞 ===')
# 搜尋鉅亨網
try:
    url2 = 'https://search.cnyes.com/api/v3/search?q=%E5%B7%9D%E6%99%AE%20%E9%97%9C%E7%A8%85&limit=5'
    req2 = urllib.request.Request(url2, headers={'User-Agent': UA})
    resp2 = urllib.request.urlopen(req2, timeout=10)
    html2 = resp2.read().decode('utf-8', errors='replace')
    # 可能不是 JSON 格式，先看內容
    print(f'  Response: {html2[:200]}')
except Exception as e:
    print(f'  fails: {str(e)[:30]}')

# 改用 RSS/Yahoo
print()
print('=== Yahoo Finance (Web Scrape) ===')
try:
    req3 = urllib.request.Request('https://finance.yahoo.com/news/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    resp3 = urllib.request.urlopen(req3, timeout=10)
    html3 = resp3.read().decode('utf-8', errors='replace')
    # 用簡單正則找標題
    import re
    # 找所有 <h3> 內的連結
    parts = html3.split('<h3')
    print(f'  Found {len(parts)} h3 sections')
    count = 0
    for p in parts[1:8]:
        m = re.search(r'href=\"([^\"]+)\"[^>]*>([^<]+)<', p)
        if m:
            t = m.group(2).strip()
            if t and len(t) > 10:
                count += 1
                print(f'  {count}. {t[:60]}')
except Exception as e:
    print(f'  FAILED: {str(e)[:30]}')
