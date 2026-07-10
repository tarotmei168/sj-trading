# -*- coding: utf-8 -*-
"""
📰 晨報新聞引擎 v2
==============
整合鉅亨網多個分類，特別關注川普/關稅/半導體相關
"""
import urllib.request, json, re, os
from datetime import datetime

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(BASE, 'output', 'news_headlines.json')

CATEGORIES = {
    '台股': 'tw_stock',
    '美股': 'us_stock',
    '頭條': 'headline',
    '科技': 'tech',
}

# 關鍵字標記
KEYWORD_TAGS = {
    '川普': '🔴川普',
    '關稅': '🔴關稅',
    '中國': '🟡中國',
    '美中': '🔴美中',
    '制裁': '🔴制裁',
    '華為': '🔴華為',
    '晶片': '🟡晶片',
    '半導體': '🟢半導體',
    'AI': '🟢AI',
    '台積電': '🟢台積電',
    '法說': '🟢法說',
    '營收': '📊營收',
}

def fetch_cnyes(category, limit=10):
    url = f'https://news.cnyes.com/api/v3/news/category/{category}?limit={limit}&page=1'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', {}).get('data', [])
        result = []
        for item in items:
            title = item.get('title', '')[:80]
            date = str(item.get('publishedAt', ''))[:10]
            # 計算關鍵字標記
            tags = []
            for kw, tag in KEYWORD_TAGS.items():
                if kw in title:
                    tags.append(tag)
            result.append({
                'title': title,
                'date': date,
                'tags': tags,
            })
        return result
    except:
        return []

def get_all_headlines():
    print('📰 抓取鉅亨網新聞...')
    
    all_news = {}
    for cat_name, cat_id in CATEGORIES.items():
        news = fetch_cnyes(cat_id, 8)
        all_news[cat_name] = news
        tagged = sum(1 for n in news if n['tags'])
        print(f'  {cat_name}: {len(news)} 則 (含關鍵字{tagged}則)')
    
    result = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'categories': all_news,
    }
    
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'  ✅ 已儲存: {CACHE_FILE}')
    return result

def get_for_report():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def generate_html(news_data):
    """產出晨報的新聞 HTML 區塊"""
    cats = news_data.get('categories', {})
    html_parts = []
    
    # 1. 台股新聞（最優先）
    tw = cats.get('台股', [])
    if tw:
        html = '<div class="card">\n'
        html += '<div class="card-title">📰 今日台股重點</div>\n'
        for n in tw[:6]:
            tags = ' '.join(f'<span class="badge badge-red">{t}</span>' for t in n['tags'][:2])
            html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    # 2. 美股新聞
    us = cats.get('美股', [])
    if us:
        html = '<div class="card info">\n'
        html += '<div class="card-title">🇺🇸 美股動態</div>\n'
        for n in us[:4]:
            html += f'<div class="news-item">{n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    # 3. 頭條（含政治/川普）
    hl = cats.get('頭條', [])
    tech = cats.get('科技', [])
    political = [n for n in hl if n['tags']] + [n for n in tech if n['tags']]
    if political:
        html = '<div class="card" style="border-left-color: #a29bfe;">\n'
        html += '<div class="card-title">🗣️ 川普投顧放大鏡</div>\n'
        seen = set()
        for n in political[:5]:
            key = n['title'][:20]
            if key not in seen:
                seen.add(key)
                tags = ' '.join(f'<span class="badge {"badge-red" if "🔴" in t else "badge-orange"}">{t}</span>' for t in n['tags'][:2])
                html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    return '\n'.join(html_parts)


if __name__ == '__main__':
    result = get_all_headlines()
    print()
    print('='*40)
    print(generate_html(result))
