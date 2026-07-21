#!/usr/bin/env python3
"""
crawl_headlines.py — 爬鉅亨網新聞，純 HTTP GET，0 token
===========================================================
爬四個分類，存到 output/news_crawled.json
再由 daily_web_report.py 讀取塞進 HTML
"""

import requests, json, os, re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_cnyes(section='us_stock', max_items=10):
    """爬鉅亨網分類新聞，回傳標題+連結列表"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/json,*/*',
    }
    
    urls = {
        'us_stock': 'https://news.cnyes.com/news/cat/headline?category=us_stock',
        'tw_stock': 'https://news.cnyes.com/news/cat/headline?category=tw_stock',
        'tech':     'https://news.cnyes.com/news/cat/headline?category=tech',
        'tw_macro': 'https://news.cnyes.com/news/cat/headline?category=tw_macro',
    }
    
    url = urls.get(section, urls['us_stock'])
    results = []
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        html = resp.text
        
        # 從 HTML 中找新聞條目：<a> 標題 + href
        # 鉅亨網列表結構：<a class="title" href="/news/...">標題</a>
        pattern = r'<a[^>]*class="[^"]*title[^"]*"[^>]*href="(/news/[^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)
        
        for href, title in matches:
            title = title.strip()
            if title and len(title) > 5:
                results.append({
                    'title': title,
                    'link': f'https://news.cnyes.com{href}' if href.startswith('/') else href,
                })
            if len(results) >= max_items:
                break
        
        # 如果上面的 pattern 沒找到，試另一個結構
        if not results:
            pattern2 = r'<h3[^>]*>.*?<a[^>]*href="(/news/[^"]+)"[^>]*>(.*?)</a>.*?</h3>'
            matches2 = re.findall(pattern2, html, re.DOTALL)
            for href, title in matches2:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if title and len(title) > 5:
                    results.append({
                        'title': title,
                        'link': f'https://news.cnyes.com{href}' if href.startswith('/') else href,
                    })
                if len(results) >= max_items:
                    break
    
    except Exception as e:
        print(f'  ⚠️ 爬 {section} 失敗: {e}')
    
    return results


def run():
    now = datetime.now()
    print(f'📰 爬蟲新聞 | {now.strftime("%H:%M")}')
    
    sections = {
        'us_stock': '🇺🇸 美股/國際',
        'tw_stock': '📊 台股重點',
        'tech':     '🔬 科技脈動',
        'tw_macro': '🇹🇼 台灣總經',
    }
    
    all_news = {'update_time': now.strftime('%Y-%m-%d %H:%M'), 'sections': {}}
    total = 0
    
    for key, label in sections.items():
        news = fetch_cnyes(key, 8)
        all_news['sections'][key] = {'label': label, 'items': news}
        total += len(news)
        print(f'  {label}: {len(news)} 則')
    
    output_path = os.path.join(OUTPUT_DIR, 'news_crawled.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)
    
    print(f'  ✅ 共 {total} 則 → {output_path}')
    return all_news


if __name__ == '__main__':
    run()
