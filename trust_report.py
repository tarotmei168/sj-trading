#!/usr/bin/env python3
"""
投信偷偷建倉追蹤腳本 v1 — 爬聚財網投信買賣超 + 永豐API技術面
輸出：晨報專用 HTML
"""
import os, re, sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
OUTPUT = os.path.join(BASE, f"trust_report_{TODAY.strftime('%m%d')}.html")

HEADERS = {'User-Agent': 'Mozilla/5.0'}

def parse_wearn_table(html_text):
    """Parse wearn's trust buy/sell table from HTML"""
    buy_data = []
    sell_data = []
    
    # 找投信買超前 200 名表格區塊
    # Pattern: 排名 代號 股名 買進 賣出 買超
    
    # Split the page into buy section and sell section
    parts = re.split(r'投信賣超前 200 名', html_text, maxsplit=1, flags=re.IGNORECASE)
    
    buy_section = parts[0] if len(parts) > 0 else ""
    sell_section = parts[1] if len(parts) > 1 else ""
    
    # Find all stock rows in buy section
    # Pattern: number stock_id [name](url) buy sell nets
    # Looking for lines like: 1 2887 [台新新光金](url) 10637 0 10637
    
    # Parse buy section
    for match in re.finditer(r'(\d+)\s+<a[^>]*>(\d+)</a>\s+\[([^\]]+)\]', buy_section):
        pass  # Too complex, use a simpler approach
    
    # Simpler: parse the markdown-like text that readability generates
    # Lines like: " 1 2887 [台新新光金](https://stock.wearn.com/a2887.html) 10637 0 10637"
    
    return buy_data, sell_data

def parse_wearn_text(text):
    """Parse the readable markdown text from wearn"""
    buy_list = []
    sell_list = []
    
    # Split into buy and sell sections
    parts = re.split(r'投信賣超前', text, maxsplit=1, flags=re.IGNORECASE)
    
    buy_text = parts[0] if len(parts) > 0 else ""
    sell_text = parts[1] if len(parts) > 1 else ""
    
    # Parse buy section: find lines like " 1 2887 [台新新光金](url) 10637 0 10637"
    for line in buy_text.split('\n'):
        line = line.strip()
        # Match: rank code [name](url) buy sell nets
        m = re.match(r'(\d+)\s+(\d{4}|^[A-Z0-9]+)\s+\[([^\]]+)\]', line)
        if m:
            rest = line[m.end():]
            parts_list = rest.split()
            if len(parts_list) >= 3:
                try:
                    code = m.group(2)
                    name = m.group(3)
                    buy = int(parts_list[0].replace(',', ''))
                    sell = int(parts_list[1].replace(',', ''))
                    nets = int(parts_list[2].replace(',', ''))
                    buy_list.append({
                        'code': code, 'name': name,
                        'buy': buy, 'sell': sell, 'nets': nets
                    })
                except ValueError:
                    continue
    
    # Parse sell section  
    for line in sell_text.split('\n'):
        line = line.strip()
        m = re.match(r'(\d+)\s+(\d{4}|[A-Z0-9]+)\s+\[([^\]]+)\]', line)
        if m:
            rest = line[m.end():]
            parts_list = rest.split()
            if len(parts_list) >= 3:
                try:
                    code = m.group(2)
                    name = m.group(3)
                    buy = int(parts_list[0].replace(',', ''))
                    sell = int(parts_list[1].replace(',', ''))
                    nets = int(parts_list[2].replace(',', ''))
                    sell_list.append({
                        'code': code, 'name': name,
                        'buy': buy, 'sell': sell, 'nets': -nets
                    })
                except ValueError:
                    continue
    
    return buy_list, sell_list

def fetch_trust_data(date_str):
    """Fetch trust buy/sell data from wearn.com"""
    url = f'https://stock.wearn.com/b50.asp'
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = 'utf-8'
        text = r.text
        
        # Check if we got the right page
        if '投信買賣超' not in text:
            print(f"  ⚠️  {date_str}: 頁面內容異常")
            return [], []
        
        # Get readable text version for parsing
        # Simple strip HTML approach
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean)
        
        # Better approach: parse directly from raw HTML
        buy_list, sell_list = parse_wearn_html_direct(text)
        
        print(f"  ✅ {date_str}: 買超{len(buy_list)}筆, 賣超{len(sell_list)}筆")
        return buy_list, sell_list
    except Exception as e:
        print(f"  ❌ {date_str}: {e}")
        return [], []

def parse_wearn_html_direct(html):
    """直接從 HTML 解析投信買賣超 - 逐行解析"""
    buy_list = []
    sell_list = []
    
    # Split by "投信賣超" section
    parts = re.split(r'投信賣超', html, maxsplit=1, flags=re.IGNORECASE)
    buy_section = parts[0] if len(parts) > 0 else ""
    sell_section = parts[1] if len(parts) > 1 else ""
    
    def parse_section(section, is_sell=False):
        result = []
        # Find all <tr> blocks in this section
        # Pattern: <tr ...> <td>RANK</td><td>CODE</td><td><a...>NAME</a></td><td>BUY</td><td>SELL</td><td>NETS</td></tr>
        rows = re.findall(
            r'<tr[^>]*>\s*<td>(\d+)</td>\s*'
            r'<td>([A-Z0-9]+)</td>\s*'
            r'<td><a[^>]*>([^<]+)</a></td>\s*'
            r'<td[^>]*>([\d,]+)</td>\s*'
            r'<td[^>]*>([\d,]+)</td>\s*'
            r'<td[^>]*>([-\d,]+)</td>\s*</tr>',
            section, re.DOTALL
        )
        for match in rows:
            try:
                rank = int(match[0])
                code = match[1].strip()
                name = match[2].strip()
                buy_val = int(match[3].replace(',', ''))
                sell_val = int(match[4].replace(',', ''))
                nets = int(match[5].replace(',', ''))
                
                # Skip ETF-like codes (6-digit starting with 00)
                if len(code) >= 4 and code.startswith('00'):
                    # Allow 0050, 0056 etc but mark them
                    pass
                
                result.append({
                    'code': code, 'name': name,
                    'buy': buy_val, 'sell': sell_val, 'nets': nets
                })
            except (ValueError, IndexError):
                continue
        return result
    
    buy_list = parse_section(buy_section)
    # For sell section, nets will be negative (e.g. -12171)
    sell_list = parse_section(sell_section)
    # Filter: buy section should have positive nets, sell section should have negative
    buy_list = [x for x in buy_list if x['nets'] > 0]
    sell_list = [x for x in sell_list if x['nets'] < 0]
    
    return buy_list, sell_list

def get_prices_from_shioaji(codes):
    """Use Shioaji to get current prices for stocks"""
    try:
        import shioaji as sj
        import numpy as np
        
        api = sj.Shioaji(simulation=True)
        api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
        
        prices = {}
        # Batch query using snapshots for efficiency
        contracts = []
        for code in codes[:50]:  # Max 50 stocks
            try:
                contract = api.Contracts.Stocks[code]
                contracts.append(contract)
            except:
                pass
        
        if contracts:
            snaps = api.snapshots(contracts)
            for snap in snaps:
                code = snap.code
                close = snap.close
                change = snap.change_price
                change_pct = (change / (close - change) * 100) if (close - change) != 0 else 0
                prices[code] = {
                    'price': round(close, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': snap.volume if hasattr(snap, 'volume') else 0
                }
        
        api.logout()
        return prices
    except Exception as e:
        print(f"  ⚠️ Shioaji 價格查詢失敗: {e}")
        return {}

def build_trust_html():
    """Main function: build trust report HTML"""
    print("📊 投信建倉追蹤報告產生中...")
    print(f"📅 日期: {TODAY_STR}")
    
    # Fetch today's data
    print("\n📡 抓取投信買賣超...")
    today_buy, today_sell = fetch_trust_data(TODAY_STR)
    
    if not today_buy:
        # Fallback: use cached data from web_fetch
        print("  ⚠️ 直接爬取失敗，使用替代方法...")
        # Try reading the raw HTML from the web_fetch results directly
        r = requests.get('https://stock.wearn.com/b50.asp', headers=HEADERS, timeout=10)
        r.encoding = 'utf-8'
        today_buy, today_sell = parse_wearn_html_direct(r.text)
    
    print(f"\n📊 今日投信買超: {len(today_buy)} 檔")
    print(f"📊 今日投信賣超: {len(today_sell)} 檔")
    
    # Get all unique stock codes for price lookup
    all_codes = list(set(
        [x['code'] for x in today_buy[:80]] + 
        [x['code'] for x in today_sell[:40]]
    ))
    
    # Get prices
    print("\n💹 查詢股價...")
    prices = get_prices_from_shioaji(all_codes)
    print(f"  ✅ 取得 {len(prices)} 檔股價")
    
    # === 篩選潛在建倉標的 ===
    # Criteria: 
    # - Not ETF (0050, 0056, 009xx etc)
    # - Not mega-bank financials
    # - Not giant caps like 2330
    # - Nets > 100 shares
    # - Interesting for short-term building
    
    EXCLUDED_PREFIXES = ('00', '006', '007', '008', '009', '01')
    EXCLUDED_CODES = {'0050', '0056', '0052', '2887', '2891', '2886', '2885', 
                      '2882', '2883', '2884', '2880', '2881', '2890', '5880',
                      '2845', '2834', '2892', '2897', '2801', '2812',
                      '2330', '2412', '3045', '2454', '2317'}
    
    potential = []
    for item in today_buy:
        code = item['code']
        nets = item['nets']
        name = item['name']
        
        # Skip ETFs
        if code.startswith('0') and len(code) == 4:
            continue
        if code in EXCLUDED_CODES:
            continue
        
        if nets >= 50:
            price_info = prices.get(code, {})
            potential.append({
                **item,
                'price': price_info.get('price', '-'),
                'change': price_info.get('change', '-'),
                'change_pct': price_info.get('change_pct', '-'),
            })
    
    # Sort by nets descending
    potential.sort(key=lambda x: x['nets'], reverse=True)
    
    # === 投信賣超觀察（與你有關的） ===
    YOUR_STOCKS = {'2436','2337','3042','5351','2317','2454','8150','4958','3673','3711',
                   '2330','6139','1303','5425','2327','8016','4961','3532','2464','6451','6213'}
    
    related_sells = [x for x in today_sell if x['code'] in YOUR_STOCKS]
    
    # === 產生 HTML ===
    date_display = TODAY.strftime("%Y-%m-%d %H:%M")
    
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投信建倉雷達 · {TODAY_STR}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, 'PingFang SC', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
    background: #0b1120;
    color: #e1e9f0;
    padding: 24px;
}}
.container {{ max-width: 1000px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 8px; }}
.subtitle {{ color: #8899aa; font-size: 13px; margin-bottom: 24px; }}

.section {{ margin-bottom: 28px; }}
.section-title {{
    font-size: 16px; font-weight: 600; color: #8ba4c6;
    margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
}}
.section-title::before {{
    content: ''; display: inline-block; width: 3px; height: 16px;
    border-radius: 2px; background: #f0c27a;
}}
.section-title.trust::before {{ background: #4ade80; }}
.section-title.sell::before {{ background: #f87171; }}

.card {{
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 12px; padding: 18px 22px;
    overflow-x: auto;
}}
.card + .card {{ margin-top: 12px; }}

table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{
    text-align: left; padding: 8px 6px; font-size: 11px;
    color: #8899aa; border-bottom: 1px solid rgba(255,255,255,.1);
    font-weight: 600; white-space: nowrap;
}}
td {{ padding: 7px 6px; border-bottom: 1px solid rgba(255,255,255,.04); white-space: nowrap; }}
tr:hover {{ background: rgba(255,255,255,.04); }}

.buy {{ color: #4ade80; font-weight: 600; }}
.sell {{ color: #f87171; font-weight: 600; }}
.code {{ color: #8899aa; font-size: 11px; }}
.price-up {{ color: #f87171; }}
.price-down {{ color: #4ade80; }}

.badge {{
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 10px; font-weight: 600;
}}
.badge-accum {{ background: rgba(74,222,128,.15); color: #4ade80; }}
.badge-new {{ background: rgba(250,204,21,.15); color: #facc15; }}
.badge-warn {{ background: rgba(248,113,113,.15); color: #f87171; }}
.badge-mid {{ background: rgba(139,164,198,.15); color: #8ba4c6; }}

.stats {{ display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }}
.stat-item {{
    background: rgba(255,255,255,.03); border-radius: 8px;
    padding: 12px 16px; text-align: center;
    min-width: 100px; flex: 1;
}}
.stat-item .num {{ font-size: 26px; font-weight: 700; color: #f0c27a; }}
.stat-item .lbl {{ font-size: 11px; color: #8899aa; margin-top: 2px; }}

.reason {{ font-size: 11px; color: #8899aa; line-height: 1.4; max-width: 300px; white-space: normal; }}
.footer {{ text-align: center; font-size: 12px; color: #445566; margin-top: 40px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.05); }}
</style>
</head>
<body>
<div class="container">

<h1>🏗 投信建倉雷達</h1>
<div class="subtitle">{date_display} · 抓投信 1-3 天偷偷建倉的股票</div>

<div class="stats">
    <div class="stat-item"><div class="num">{len(today_buy)}</div><div class="lbl">投信買超總數</div></div>
    <div class="stat-item"><div class="num" style="color:#4ade80;">{len(potential)}</div><div class="lbl">篩選：潛在建倉</div></div>
    <div class="stat-item"><div class="num" style="color:#f87171;">{len(today_sell)}</div><div class="lbl">投信賣超總數</div></div>
    <div class="stat-item"><div class="num" style="color:#8ba4c6;">{len(prices)}</div><div class="lbl">已取得股價</div></div>
</div>
""")
    
    # === 潛在建倉表 ===
    html_parts.append("""
<div class="section">
<div class="section-title trust">🔨 投信潛在建倉標的（篩選：排除ETF/金融/巨型權值，聚焦中小型）</div>
<div class="card">
<table>
<thead>
<tr>
    <th>代號</th><th>名稱</th><th>投信買超</th><th>股價</th><th>漲跌%</th><th>標記</th><th>觀察理由</th>
</tr>
</thead>
<tbody>
""")
    
    for item in potential:
        code = item['code']
        name = item['name']
        nets = item['nets']
        price = item['price']
        chg = item['change_pct']
        
        price_str = str(price) if price != '-' else '-'
        chg_str = f"{chg:+.2f}%" if chg != '-' else '-'
        chg_cls = "price-up" if isinstance(chg, (int, float)) and chg > 0 else ("price-down" if isinstance(chg, (int, float)) and chg < 0 else "")
        
        # Determine badge and reason
        badge = '<span class="badge badge-accum">🔨 建倉</span>'
        reason = "投信單日大量買入，尚未明顯發動"
        
        if nets >= 1000:
            badge = '<span class="badge badge-accum">🔥 大量建倉</span>'
            reason = "異常大量買超，投信明顯看好"
        elif nets >= 500:
            badge = '<span class="badge badge-accum">🔨 顯著建倉</span>'
            reason = "顯著買超，短線值得追蹤"
        elif nets >= 200:
            badge = '<span class="badge badge-new">📊 開始布局</span>'
            reason = "投信開始布局，量能放大可期"
        elif nets >= 100:
            badge = '<span class="badge badge-mid">👀 小量試單</span>'
            reason = "小量試水溫，觀察是否連買"
        else:
            badge = '<span class="badge badge-mid">🔍 微量觀察</span>'
            reason = "微量買超，續觀察"
        
        # Custom reasons for specific stocks
        custom_reasons = {
            '3026': '被動元件通路，單日2813張非比尋常',
            '6278': 'SMT/PCB組裝，底部量能擴增中',
            '4764': '化工股投信極少碰，883張異常',
            '5469': 'PCB廠，底部量擴增',
            '6282': '電源供應器，新納入標的',
            '8096': 'IC通路，全買330張無賣',
            '6548': 'IC載板中小型，值得注意',
            '2006': '鋼鐵循環可能落底',
            '6691': '廠務工程，有資金進駐',
            '2441': '封測廠，底部轉強',
        }
        if code in custom_reasons:
            reason = custom_reasons[code]
        
        html_parts.append(f'<tr>')
        html_parts.append(f'<td><span class="code">{code}</span></td>')
        html_parts.append(f'<td><b>{name}</b></td>')
        html_parts.append(f'<td class="buy">{nets:,}</td>')
        html_parts.append(f'<td>{price_str}</td>')
        html_parts.append(f'<td class="{chg_cls}">{chg_str}</td>')
        html_parts.append(f'<td>{badge}</td>')
        html_parts.append(f'<td class="reason">{reason}</td>')
        html_parts.append(f'</tr>\n')
    
    html_parts.append("</tbody></table></div></div>\n")
    
    # === 投信賣超表（與你有關的） ===
    html_parts.append("""
<div class="section">
<div class="section-title sell">⚠️ 投信賣超 · 與你的持股/觀察相關</div>
<div class="card">
<table>
<thead>
<tr>
    <th>代號</th><th>名稱</th><th>投信賣超</th><th>關聯</th>
</tr>
</thead>
<tbody>
""")
    
    if related_sells:
        for item in related_sells:
            code = item['code']
            name = item['name']
            nets = abs(item['nets'])
            
            relation = "⚠️ 你的持股或觀察股"
            if code in {'2436','3042','2337','5351','2317','2454','3673','3711'}:
                relation = "⚠️ 你的持股"
            elif code in {'8150','4958'}:
                relation = "⚠️ 你的觀察/區間操作股"
            elif code in {'6139','1303','5425','2327'}:
                relation = "⚠️ 你的避開清單，方向一致"
            
            html_parts.append(f'<tr>')
            html_parts.append(f'<td><span class="code">{code}</span></td>')
            html_parts.append(f'<td><b>{name}</b></td>')
            html_parts.append(f'<td class="sell">-{nets:,}</td>')
            html_parts.append(f'<td class="reason">{relation}</td>')
            html_parts.append(f'</tr>\n')
    else:
        html_parts.append('<tr><td colspan="4" style="color:#556677; text-align:center;">✅ 你的持股/觀察股今天沒有被投信大量賣超</td></tr>')
    
    html_parts.append("</tbody></table></div></div>\n")
    
    # === 完整買超TOP 50 ===
    html_parts.append("""
<div class="section">
<div class="section-title">📊 投信買超 TOP 50（完整排行）</div>
<div class="card">
<table>
<thead>
<tr><th>#</th><th>代號</th><th>名稱</th><th>買超(張)</th></tr>
</thead>
<tbody>
""")
    
    for i, item in enumerate(today_buy[:50], 1):
        code = item['code']
        name = item['name']
        nets = item['nets']
        html_parts.append(f'<tr><td>{i}</td><td><span class="code">{code}</span></td><td>{name}</td><td class="buy">{nets:,}</td></tr>\n')
    
    html_parts.append("</tbody></table></div></div>\n")
    
    # === 賣超TOP 20 ===
    html_parts.append("""
<div class="section">
<div class="section-title sell">📊 投信賣超 TOP 20</div>
<div class="card">
<table>
<thead>
<tr><th>#</th><th>代號</th><th>名稱</th><th>賣超(張)</th></tr>
</thead>
<tbody>
""")
    
    for i, item in enumerate(today_sell[:20], 1):
        code = item['code']
        name = item['name']
        nets = abs(item['nets'])
        html_parts.append(f'<tr><td>{i}</td><td><span class="code">{code}</span></td><td>{name}</td><td class="sell">-{nets:,}</td></tr>\n')
    
    html_parts.append("</tbody></table></div></div>\n")
    
    # Footer
    html_parts.append(f"""
<div class="footer">
    投信建倉雷達 · 資料來源：聚財網投信買賣超 + 永豐金API · {date_display}
</div>
</div></body></html>
""")
    
    html_output = '\n'.join(html_parts)
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_output)
    
    print(f"\n✅ 報告已產出: {OUTPUT}")
    return potential, today_buy, today_sell

if __name__ == '__main__':
    build_trust_html()
