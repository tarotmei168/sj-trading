# -*- coding: utf-8 -*-
import urllib.request, json, re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

# 1. 鉅亨網台股新聞
print('=== 鉅亨網台股新聞 ===')
url = 'https://news.cnyes.com/api/v3/news/category/tw_stock?limit=10&page=1'
try:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    items = data.get('items', {}).get('data', [])
    print(f'{len(items)} 則')
    for i, item in enumerate(items[:8]):
        t = item.get('title', '')
        print(f'  {i+1}. {t[:60]}')
except Exception as e:
    print(f'FAILED: {str(e)[:50]}')

# 2. 鉅亨網美股新聞
print()
print('=== 鉅亨網美股/國際新聞 ===')
url2 = 'https://news.cnyes.com/api/v3/news/category/world?limit=10&page=1'
try:
    req2 = urllib.request.Request(url2, headers={'User-Agent': UA})
    resp2 = urllib.request.urlopen(req2, timeout=10)
    data2 = json.loads(resp2.read().decode('utf-8'))
    items2 = data2.get('items', {}).get('data', [])
    print(f'{len(items2)} 則')
    for i, item in enumerate(items2[:8]):
        t = item.get('title', '')
        if '川普' in t or '關稅' in t or '晶片' in t or '中國' in t or '美中' in t or '制裁' in t:
            print(f'  {i+1}. [政治] {t[:60]}')
        else:
            print(f'  {i+1}. {t[:60]}')
except Exception as e:
    print(f'FAILED: {str(e)[:50]}')

# 3. 試試看關鍵字搜尋川普
print()
print('=== 鉅亨網川普相關新聞 ===')
url3 = 'https://search.cnyes.com/api/v3/search?q=%E5%B7%9D%E6%99%AE&limit=10'
try:
    req3 = urllib.request.Request(url3, headers={'User-Agent': UA})
    resp3 = urllib.request.urlopen(req3, timeout=10)
    data3 = json.loads(resp3.read().decode('utf-8'))
    items3 = data3.get('items', {}).get('data', [])
    print(f'{len(items3)} 則')
    for i, item in enumerate(items3[:8]):
        t = item.get('title', '')
        print(f'  {i+1}. {t[:60]}')
except Exception as e:
    print(f'FAILED: {str(e)[:50]}')
