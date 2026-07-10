# -*- coding: utf-8 -*-
"""
📰 晨報新聞引擎 v3
===============
資料源：鉅亨網 (Anue) API
分類：tw_macro 台灣總經、us_stock 美股/國際、tw_stock 台股、tech 科技
特別：關鍵字過濾川普/關稅/聯準會/國際政治
"""
import urllib.request, json, os, sys
from datetime import datetime

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(BASE, 'output', 'news_headlines.json')

CATEGORIES = [
    ('tw_macro', '🇹🇼 台灣總經'),
    ('us_stock', '🌍 美股/國際'),
    ('tw_stock', '📊 台股重點'),
    ('tech',     '🔬 科技脈動'),
]

# 關鍵字 → 顏色分類
KEYWORD_RULES = [
    # ⭐ 股價催化劑（最優先標記）
    (['漲價', '調漲', '漲價效應'], '⭐漲價'),
    (['缺料', '缺貨', '供不應求', '產能吃緊'], '⭐缺貨'),
    (['營收新高', '創新高', '歷史新高', '同期新高'], '⭐營收創高'),
    (['EPS', '每股盈餘'], '⭐EPS'),
    (['股利', '股息', '殖利率', '現金股利'], '⭐股利'),
    (['三率三升', '毛利率', '營益率', '淨利率'], '⭐三率三升'),
    (['訂單能見度', '訂單滿載', '接單', '滿手訂單'], '⭐訂單'),
    (['虧轉盈', '轉虧為盈', '轉機', '虧損縮小'], '⭐轉機'),
    (['熱門', '焦點股', '強勢', '飆股', '人氣'], '⭐熱門'),
    (['擴產', '擴廠', '新產能', '量產'], '⭐擴產'),
    # 政治/川普/地緣 (紅色)
    (['川普', '特朗普', 'trump', 'Trump'], '🔴政治'),
    (['關稅', 'tariff', '關稅壁壘'], '🔴關稅'),
    (['制裁', '封鎖', '禁令', 'ban'], '🔴制裁'),
    (['美中', '中美', '中國', '北京', '華盛頓'], '🔴地緣'),
    (['聯準會', 'Fed', '鮑爾', 'Powell', '升息', '降息'], '🔴FED'),
    # 產業大事 (橙色)
    (['晶片', 'chip', '半導體', '台積電', 'TSMC'], '🟠半導體'),
    (['AI', '人工智能', '人工智慧'], '🟠AI'),
    (['法說', '法說會'], '🟠法說'),
    (['營收', '財報'], '🟠財報'),
    (['除息', '除權'], '🟠除息'),
]

def tag_title(title):
    tags = []
    for keywords, tag in KEYWORD_RULES:
        for kw in keywords:
            if kw in title:
                tags.append(tag)
                break
    return tags

def fetch_category(cat_id, limit=10):
    url = f'https://news.cnyes.com/api/v3/news/category/{cat_id}?limit={limit}&page=1'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', {}).get('data', [])
        result = []
        for item in items:
            title = item.get('title', '').strip()
            if not title:
                continue
            result.append({
                'title': title[:80],
                'date': str(item.get('publishedAt', ''))[:10],
                'tags': tag_title(title),
            })
        return result
    except:
        return []

def get_all_headlines():
    print('📰 鉅亨網新聞...')
    all_news = {}
    total = 0
    for cat_id, cat_label in CATEGORIES:
        news = fetch_category(cat_id, 10)
        all_news[cat_id] = {'label': cat_label, 'items': news}
        tagged = sum(1 for n in news if n['tags'])
        total += len(news)
        print(f'  {cat_label}: {len(news)} 則 (含關鍵字{tagged})')
    
    result = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'categories': all_news,
    }
    
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'  ✅ 共{total}則 → {CACHE_FILE}')
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
    """產出晨報新聞 HTML 區塊"""
    cats = news_data.get('categories', {})
    html_parts = []
    
    # 1. 政治/國際大事優先 — 從 us_stock + tw_macro 中找有 tag 的
    political = []
    for cid in ['us_stock', 'tw_macro']:
        if cid in cats:
            political.extend(
                (n, cid) for n in cats[cid]['items'] if n['tags']
            )
    # 從頭條也補
    if 'headline' in cats:
        political.extend(
            (n, 'headline') for n in cats['headline']['items'] if n['tags']
        )
    
    if political:
        seen = set()
        html = '<div class="card alert">\n'
        html += '<div class="card-title">🌍 國際政治 × 總經大事</div>\n'
        count = 0
        for n, cid in political:
            key = n['title'][:20]
            if key not in seen:
                seen.add(key)
                tags = ' '.join(
                    f'<span class="badge badge-red">{t}</span>'
                    for t in n['tags'][:3]
                )
                html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
                count += 1
                if count >= 6:
                    break
        html += '</div>\n'
        html_parts.append(html)
    
    # 2. ⭐ 股價催化劑新聞（從台股+科技+總經中找有星號的）
    catalyst = []
    for cid in ['tw_stock', 'tech', 'tw_macro']:
        if cid in cats:
            catalyst.extend(n for n in cats[cid]['items'] if any(t.startswith('⭐') for t in n['tags']))
    if catalyst:
        seen = set()
        html = '<div class="card" style="border-left-color: #ffa502;">\n'
        html += '<div class="card-title">🔥 股價催化劑（漲價/缺料/營收創高/轉機）</div>\n'
        for n in catalyst[:6]:
            key = n['title'][:20]
            if key not in seen:
                seen.add(key)
                tags = ' '.join(f'<span class="badge badge-red">{t}</span>' for t in n['tags'][:3])
                html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    # 3. 台股重點 (tw_stock)
    if 'tw_stock' in cats and cats['tw_stock']['items']:
        html = '<div class="card">\n'
        html += f'<div class="card-title">📊 台股重點</div>\n'
        for n in cats['tw_stock']['items'][:5]:
            tags = ' '.join(
                f'<span class="badge badge-blue">{t}</span>'
                for t in n['tags'][:2]
            )
            html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    # 4. 科技新聞
    if 'tech' in cats and cats['tech']['items']:
        html = '<div class="card info">\n'
        html += f'<div class="card-title">🔬 科技產業</div>\n'
        for n in cats['tech']['items'][:4]:
            tags = ' '.join(
                f'<span class="badge badge-blue">{t}</span>'
                for t in n['tags'][:2]
            )
            html += f'<div class="news-item">{tags} {n["title"]}</div>\n'
        html += '</div>\n'
        html_parts.append(html)
    
    # 4. 台灣總經 (政治類剩下的)
    if 'tw_macro' in cats:
        macro = [
            n for n in cats['tw_macro']['items']
            if not any('🔴' in t for t in n['tags'])
        ][:3]
        if macro:
            html = '<div class="card">\n'
            html += '<div class="card-title">🇹🇼 台灣總經</div>\n'
            for n in macro:
                html += f'<div class="news-item">{n["title"]}</div>\n'
            html += '</div>\n'
            html_parts.append(html)
    
    return '\n'.join(html_parts)


if __name__ == '__main__':
    data = get_all_headlines()
    print()
    print('='*50)
    print(generate_html(data))
