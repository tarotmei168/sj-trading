# -*- coding: utf-8 -*-
import urllib.request, json

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# 試試鉅亨網的其他 API 路徑
urls = [
    ('全球總經', 'https://news.cnyes.com/api/v3/news/category/global_economic?limit=5&page=1'),
    ('國際財經', 'https://news.cnyes.com/api/v3/news/category/international?limit=5&page=1'),
    ('美股', 'https://news.cnyes.com/api/v3/news/category/us_stock?limit=5&page=1'),
    ('頭條', 'https://news.cnyes.com/api/v3/news/category/headline?limit=5&page=1'),
    ('科技', 'https://news.cnyes.com/api/v3/news/category/tech?limit=5&page=1'),
    ('產業', 'https://news.cnyes.com/api/v3/news/category/industry?limit=5&page=1'),
]

for name, url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', {}).get('data', [])
        titles = [item.get('title','')[:50] for item in items[:5]]
        print(f'{name}: {len(items)} 則')
        for t in titles:
            tag = ' ⚠️' if any(k in t for k in ['川普','關稅','中國','美中','晶片','制裁','半導體','華為'] ) else ''
            print(f'  {t}{tag}')
    except Exception as e:
        print(f'{name}: FAILED {str(e)[:30]}')
    print()
