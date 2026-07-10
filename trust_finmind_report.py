#!/usr/bin/env python3
"""
投信建倉雷達 v2 — FinMind API 逐檔查 taiwan_stock_institutional_investors
抓盤後投信買賣超，篩出 1-3 天內偷偷建倉的股票
"""
import sys, json, os, requests, time
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
TODAY = datetime.now()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
OUTPUT = os.path.join(BASE, f"trust_report_{TODAY.strftime('%m%d')}.html")

API_URL = "https://api.finmindtrade.com/api/v4/data"
DATES = ['2026-07-03', '2026-07-06', '2026-07-07', '2026-07-08']

# 需要查詢的股票（全部上市櫃有成交量的）
# 先從知名+你的觀察清單開始擴展
TARGET_STOCKS = [
    # 你的持股
    '2436','2337','3042','5351','2317','2454','8150','4958','3673','3711',
    # 你的潛力 + 觀察
    '2330','4961','6451','3532','2327','8016','2464','6139','1303','5425',
    '2303','6284','6213','6271','6173','3131','3583','6239','2408','6770',
    '2344','6182','8261','2434','6488','3008','2409','3481','1815',
    # 投信今天買超前段的中小型
    '3026','6278','4764','5469','6282','3260','8096','2441',
    '6548','2006','3665','6257','2451','4967','2458','6147',
    '8016','1476','5483','6409','6223','2383','1608','8069',
    '3227','3023','6415','6526','3661','2376','2377','3592',
    '5536','6691','6239','2455','6271','5347','2542','2206',
    '1210','5876','1477','5871','1102','6669','2379','3406',
    '2347','2027','2105','2609','2610','2603','2308','1326',
    '1907','2385','2059','2501','9910','8261','2634','5434',
    '3004','2204','2363','6196','5904','9914','3491',
]
# 排除的股票
EXCLUDE_CODES = {
    '0050','0051','0052','0055','0056','006201','00713','00632R','00633L','00637L','00646',
    '00935','00919','00929','00937B','00988A','00997A','00981A','00403A',
    '2881','2882','2883','2884','2885','2886','2887','2890','2891','2892',
    '5880','2845','2834','2897','2801','2812','2855','6026','2851','6005','6023',
    '2330','2412','3045',
}

def should_exclude(code):
    if code in EXCLUDE_CODES:
        return True
    if code.startswith('00') and len(code) <= 6:
        return True
    if code.startswith('006') or code.startswith('007') or code.startswith('008') or code.startswith('009'):
        return True
    return False

def fetch_one_stock(sid):
    """Fetch institutional investors data for one stock"""
    params = {
        'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
        'data_id': sid,
        'start_date': DATES[0],
        'end_date': DATES[-1],
    }
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        data = r.json()
        if data.get('status') == 200:
            return data.get('data', [])
        return None
    except:
        return None

def fetch_stock_info():
    """Get all stock names from FinMind"""
    r = requests.get(API_URL, params={'dataset': 'TaiwanStockInfo'}, timeout=15)
    data = r.json()
    info = {}
    if data.get('status') == 200:
        for rec in data.get('data', []):
            info[rec['stock_id']] = {
                'name': rec.get('stock_name', ''),
                'industry': rec.get('industry_category', ''),
            }
    return info

def format_num(n):
    if n >= 1000:
        return f"{n:,}"
    return str(n)

def build_html():
    print("🏗 投信建倉雷達 v2 — FinMind API 逐檔查")
    print(f"📅 {TODAY_STR}")
    print(f"📡 查詢 {len(TARGET_STOCKS)} 檔股票...")
    
    # Get stock info
    print("\n📋 取得基本資料...")
    stock_info = fetch_stock_info()
    print(f"   ✅ 已取得 {len(stock_info)} 檔基本資料")
    
    # Fetch data for each stock
    all_stocks = {}
    count = 0
    errors = 0
    
    for sid in TARGET_STOCKS:
        if should_exclude(sid):
            continue
        records = fetch_one_stock(sid)
        if records is None:
            errors += 1
        else:
            trust_records = [r for r in records if r['name'] == 'Investment_Trust']
            if trust_records:
                all_stocks[sid] = trust_records
        count += 1
        if count % 30 == 0:
            print(f"   ✅ {count}/{len(TARGET_STOCKS)} ... ({len(all_stocks)} 有投信資料)")
        time.sleep(0.1)  # Rate limiting
    
    print(f"   ✅ 完成! 查詢{count}檔, {len(all_stocks)}檔有投信資料, {errors}錯誤")
    
    # Analyze
    print("\n📊 分析投信建倉...")
    results = []
    for sid, records in all_stocks.items():
        daily = {}
        for rec in records:
            d = rec['date']
            net = rec['buy'] - rec['sell']
            if d not in daily:
                daily[d] = {'buy': 0, 'sell': 0, 'net': 0}
            daily[d]['buy'] += rec['buy']
            daily[d]['sell'] += rec['sell']
            daily[d]['net'] += net
        
        # Count consecutive buy days in recent window
        consec = 0
        recent_net = 0
        total_net = sum(v['net'] for v in daily.values())
        
        for d in sorted(DATES, reverse=True):
            if d in daily and daily[d]['net'] > 0:
                consec += 1
                recent_net += daily[d]['net']
            elif d in daily and daily[d]['net'] <= 0:
                break
        
        # Only include if has recent buys
        if recent_net < 50:
            continue
        
        results.append({
            'code': sid,
            'consec': consec,
            'total_net': total_net,
            'recent_net': recent_net,
            'daily': daily,
            'last_net': daily.get(DATES[-1], {}).get('net', 0),
        })
    
    # Sort: best = high consec days + high recent_net
    results.sort(key=lambda r: (r['consec'] * 10000 + r['recent_net']), reverse=True)
    
    print(f"   📋 符合條件: {len(results)} 檔")
    
    active = [r for r in results if r['consec'] >= 2 and r['recent_net'] >= 200]
    new_b = [r for r in results if r not in active and r['recent_net'] >= 100]
    light = [r for r in results if r not in active and r not in new_b]
    
    print(f"   🔥 積極建倉(2-3天+大量): {len(active)}")
    print(f"   🔨 新建倉: {len(new_b)}")
    print(f"   👀 微量: {len(light)}")
    
    # === Generate HTML ===
    now = TODAY.strftime("%Y-%m-%d %H:%M")
    
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投信建倉雷達 · {TODAY_STR}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, 'PingFang SC', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
    background: linear-gradient(145deg, #0b1120 0%, #1a2332 100%);
    color: #e1e9f0; padding: 24px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 4px; }}
.subtitle {{ color: #8899aa; font-size: 13px; margin-bottom: 24px; }}
.section {{ margin-bottom: 28px; }}
.section-title {{ font-size: 16px; font-weight: 600; color: #8ba4c6; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }}
.section-title::before {{ content: ''; display: inline-block; width: 3px; height: 16px; border-radius: 2px; background: #f0c27a; }}
.section-title.active::before {{ background: #4ade80; }}
.section-title.new::before {{ background: #facc15; }}
.section-title.sell::before {{ background: #f87171; }}
.card {{ background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.06); border-radius: 12px; padding: 18px 22px; overflow-x: auto; }}
.card+.card {{ margin-top: 12px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 8px 6px; font-size: 11px; color: #8899aa; border-bottom: 1px solid rgba(255,255,255,.1); font-weight: 600; white-space: nowrap; }}
td {{ padding: 7px 6px; border-bottom: 1px solid rgba(255,255,255,.04); white-space: nowrap; }}
tr:hover {{ background: rgba(255,255,255,.04); }}
.buy {{ color: #4ade80; font-weight: 600; }}
.sell {{ color: #f87171; font-weight: 600; }}
.code {{ color: #8899aa; font-size: 11px; }}
.stats {{ display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }}
.stat-item {{ background: rgba(255,255,255,.03); border-radius: 8px; padding: 12px 16px; text-align: center; min-width: 110px; flex: 1; }}
.stat-item .num {{ font-size: 26px; font-weight: 700; color: #f0c27a; }}
.stat-item .lbl {{ font-size: 11px; color: #8899aa; margin-top: 2px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }}
.badge-fire {{ background: rgba(74,222,128,.2); color: #4ade80; }}
.badge-new {{ background: rgba(250,204,21,.15); color: #facc15; }}
.badge-light {{ background: rgba(139,164,198,.15); color: #8ba4c6; }}
.note {{ color: #8899aa; font-size: 12px; margin-bottom: 12px; }}
.footer {{ text-align: center; font-size: 12px; color: #445566; margin-top: 40px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.05); }}
</style>
</head>
<body>
<div class="container">

<h1>🏗 投信建倉雷達 v2</h1>
<div class="subtitle">{now} · FinMind TaiwanStockInstitutionalInvestorsBuySell · 逐檔查{len(all_stocks)}檔有投信資料</div>

<div class="stats">
    <div class="stat-item"><div class="num">{len(results)}</div><div class="lbl">投信買超標的</div></div>
    <div class="stat-item"><div class="num" style="color:#4ade80;">{len(active)}</div><div class="lbl">🔥 積極建倉 2-3天</div></div>
    <div class="stat-item"><div class="num" style="color:#facc15;">{len(new_b)}</div><div class="lbl">🔨 新建倉 1-2天</div></div>
    <div class="stat-item"><div class="num" style="color:#8ba4c6;">{len(light)}</div><div class="lbl">👀 微量試單</div></div>
</div>
"""
    
    def build_table(entries, badge_fn):
        rows = []
        for r in entries:
            code = r['code']
            info = stock_info.get(code, {})
            name = info.get('name', code)
            industry = info.get('industry', '')
            
            cells = []
            for d in DATES:
                if d in r['daily']:
                    net = r['daily'][d]['net']
                    cls = "buy" if net > 0 else "sell"
                    cells.append(f'<td class="{cls}">{format_num(abs(net))}</td>')
                else:
                    cells.append('<td style="color:#445566;">-</td>')
            
            rows.append(f"""<tr>
<td><span class="code">{code}</span></td>
<td><b>{name}</b></td>
<td style="font-size:11px;color:#8899aa;">{industry}</td>
<td>{badge_fn(r)}</td>
<td class="buy">{format_num(r['recent_net'])}</td>
{''.join(cells)}
</tr>""")
        return '\n'.join(rows)
    
    # Active building
    if active:
        html += """
<div class="section">
<div class="section-title active">🔥 投信積極建倉（連買 2-3 天 + 大量 ≥200 張）</div>
<div class="card">
<table>
<thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>連買</th><th>近3日合計</th><th>7/3</th><th>7/6</th><th>7/7</th><th>7/8</th></tr></thead>
<tbody>
"""
        html += build_table(active, lambda r: f'<span class="badge badge-fire">{r["consec"]}天</span>')
        html += "</tbody></table></div></div>\n"
    
    # New building
    if new_b:
        html += """
<div class="section">
<div class="section-title new">🔨 投信新建倉（1-2 天內開始買，≥100 張）</div>
<div class="card">
<table>
<thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>連買</th><th>近3日合計</th><th>7/3</th><th>7/6</th><th>7/7</th><th>7/8</th></tr></thead>
<tbody>
"""
        html += build_table(new_b, lambda r: f'<span>{r["consec"]}天</span>')
        html += "</tbody></table></div></div>\n"
    
    # Light trial
    if light:
        html += """
<div class="section">
<div class="section-title">👀 微量試單（50-99 張，觀察是否持續加碼）</div>
<div class="card">
<table>
<thead><tr><th>代號</th><th>名稱</th><th>產業</th><th>連買</th><th>近3日合計</th><th>7/3</th><th>7/6</th><th>7/7</th><th>7/8</th></tr></thead>
<tbody>
"""
        html += build_table(light[:40], lambda r: f'<span>{r["consec"]}天</span>')  # Top 40
        html += "</tbody></table></div></div>\n"
    
    # Your holdings
    YOUR_MAP = {
        '2436':'偉詮電','2337':'旺宏','3042':'晶技','5351':'鈺創',
        '2317':'鴻海','2454':'聯發科','8150':'南茂','4958':'臻鼎-KY',
        '3673':'TPK-KY','3711':'日月光',
    }
    holdings_data = []
    for sid, name in YOUR_MAP.items():
        if sid in all_stocks:
            records = all_stocks[sid]
            daily = defaultdict(int)
            for rec in records:
                daily[rec['date']] += rec['buy'] - rec['sell']
            total = sum(daily.values())
            holdings_data.append((sid, name, daily, total))
    
    if holdings_data:
        html += """
<div class="section">
<div class="section-title sell">📋 你的持股 vs 投信動向（完整 4 天）</div>
<div class="card">
<table>
<thead><tr><th>代號</th><th>名稱</th><th>7/3</th><th>7/6</th><th>7/7</th><th>7/8</th><th>合計</th><th>方向</th></tr></thead>
<tbody>
"""
        for sid, name, daily, total in holdings_data:
            cells = []
            for d in DATES:
                net = daily.get(d, 0)
                if net > 0:
                    cells.append(f'<td class="buy">{format_num(net)}</td>')
                elif net < 0:
                    cells.append(f'<td class="sell">{format_num(abs(net))}</td>')
                else:
                    cells.append('<td style="color:#445566;">0</td>')
            
            if total > 300:
                direction = '🟢✅ 投信大幅買超'
            elif total > 0:
                direction = '🟢 投信小買'
            elif total > -200:
                direction = '⚪ 接近中性'
            else:
                direction = '🔴⚠️ 投信明顯賣超'
            
            total_cls = "buy" if total >= 0 else "sell"
            html += f'<tr><td><span class="code">{sid}</span></td><td><b>{name}</b></td>{"".join(cells)}<td class="{total_cls}">{format_num(abs(total))}</td><td style="font-size:12px;">{direction}</td></tr>\n'
        
        html += "</tbody></table></div></div>\n"
    
    # Footer
    html += f"""
<div class="footer">
    投信建倉雷達 v2 · FinMind API TaiwanStockInstitutionalInvestorsBuySell · {now}
</div>
</div></body></html>
"""
    
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 報告已產出: {OUTPUT}")
    return results

if __name__ == '__main__':
    build_html()
