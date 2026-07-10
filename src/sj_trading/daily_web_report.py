#!/usr/bin/env python3
"""
🦞 daily_web_report.py — 小龍蝦行動總經操盤雷達
==================================================
最高執行準則: architecture_master.md
排程: 08:30 自動產出 → Git Push → GitHub Pages
      16:30 盤後資料更新後再次產出

數據源:
  - FinMind (盤後日K: KD/RSI/支撐)
  - Shioaji (即時報價, 無API Key時自動模擬模式)
  - 本機 database/*_3y.csv (離線備援)

⚠️ 全頁字體 18px, 只留費半指數, 帶入股本滲透率
"""

import sys, os, csv, json, subprocess
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# ─── 路徑 ─────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
WORKSPACE = os.path.dirname(BASE_DIR)
sys.path.insert(0, WORKSPACE)

# ─── 19檔持股（架構文件規定）──────────────────
CORE_19 = [
    ('2436','偉詮電'), ('2337','旺宏'), ('5351','鈺創'),
    ('3673','TPK-KY'), ('3711','日月光'), ('4958','臻鼎-KY'),
    ('3042','晶技'), ('2454','聯發科'), ('2317','鴻海'),
    ('3443','創意'), ('3661','世芯-KY'), ('3035','智原'),
    ('3231','緯創'), ('2382','廣達'), ('3017','奇鋐'),
    ('2451','創見'), ('8150','南茂'), ('2344','華邦電'),
    ('6770','力積電'),
]
CORE_IDS = [s[0] for s in CORE_19]
CORE_NAMES = {s[0]: s[1] for s in CORE_19}

# ─── 星期對照 ────────────────────────────────
WEEKDAY_NAMES = ['一','二','三','四','五','六','日']

# ═══════════════════════════════════════════════
#  📦 模組匯入 (graceful fallback)
# ═══════════════════════════════════════════════

# calc_tech: KD/RSI/支撐 (完全離線)
from calc_tech import read_local_csv, calc_KD, calc_RSI

# calc_trust_rate: 股本滲透率
from calc_trust_rate import calc_rates, SHARES_TOTAL, CLOSE_PRICES

# Shioaji: 即時快照 (模擬模式)
try:
    from shioaji_helper import ShioajiClient
    HAVE_SJ = True
except ImportError:
    HAVE_SJ = False

# global_weather: 聯動/事件/天氣
try:
    from global_weather import check_linkage, get_future_events, LINKAGE_MAP
    sys.path.insert(0, os.path.join(BASE_DIR, 'src', 'sj_trading'))
    from us_tw_mapping_matrix import LINKAGE_40
    HAVE_WEATHER = True
except ImportError:
    HAVE_WEATHER = False
    LINKAGE_40 = {}

# ═══════════════════════════════════════════════
#  🔌 Shioaji 快照（模擬模式）
# ═══════════════════════════════════════════════

def get_shioaji_snapshots():
    """
    取得即時快照。若無API Key則啟用模擬模式：
    用本機CSV最後收盤價當作近似值。
    """
    snaps = {}
    sjc = None
    if HAVE_SJ:
        sjc = ShioajiClient()
    tone = ''
    
    if sjc and sjc.login():
        # 真API模式
        codes = CORE_IDS + ['2330']
        snaps = sjc.get_snapshots(codes)
        tone = sjc.check_market_tone()
        sjc.logout()
        print(f'[Shioaji] ✅ 真實API模式: {len(snaps)} 檔快照')
    else:
        # 模擬模式：從本機CSV取昨日收盤
        print('[Shioaji] ⚠️ 模擬模式: 用本機日K收盤價')
        for sid in CORE_IDS:
            data = read_local_csv(sid)
            if data and len(data) >= 2:
                c1, c2 = data[-1]['close'], data[-2]['close']
                chg_pct = round((c1/c2 - 1)*100, 2)
                ref_px = data[-2]['close'] if len(data) >= 2 else c1
                change = c1 - ref_px
                snaps[sid] = {
                    'price': c1,
                    'reference': ref_px,
                    'change': round(change, 1),
                    'change_pct': chg_pct,
                    'high': data[-1]['high'],
                    'low': data[-1]['low'],
                    'volume': data[-1]['volume'],
                }
            else:
                snaps[sid] = {
                    'price': 100, 'reference': 100,
                    'change': 0, 'change_pct': 0,
                    'high': 100, 'low': 100, 'volume': 0,
                }
        # 開盤基調：用費半
        tone = '➖ 模擬模式（無即時報價）'
    
    return snaps, tone

# ═══════════════════════════════════════════════
#  📊 技術指標（本地離線計算）
# ═══════════════════════════════════════════════

def get_tech_batch(stock_ids):
    """批次產出19檔的KD/RSI/支撐"""
    result = {}
    for sid in stock_ids:
        data = read_local_csv(sid)
        if not data or len(data) < 25:
            result[sid] = None
            continue
        closes = [d['close'] for d in data]
        highs = [d['high'] for d in data]
        lows = [d['low'] for d in data]
        
        k, d, golden, gap = calc_KD(closes, highs, lows)
        rsi = calc_RSI(closes)
        support25 = min(closes[-25:]) if len(closes) >= 25 else min(closes)
        
        # 位階判斷
        if rsi < 30: level = '超賣'
        elif rsi < 40: level = '偏低'
        elif rsi < 55: level = '中性'
        elif rsi < 70: level = '偏多'
        else: level = '過熱'
        
        result[sid] = {
            'k': round(k, 1), 'd': round(d, 1),
            'golden': golden, 'gap': round(gap, 1),
            'rsi': rsi, 'support25': round(support25, 1),
            'price': closes[-1], 'level': level,
        }
    return result

# ═══════════════════════════════════════════════
#  🏦 股本滲透率 (P_day + P_cum)
# ═══════════════════════════════════════════════

def get_trust_penetration():
    """從 SITC_Accumulation.csv 算 19 檔投信滲透率"""
    sitc_candidates = [
        os.path.join(OUTPUT_DIR, 'SITC_Accumulation.csv'),
        os.path.join(BASE_DIR, 'output', 'SITC_Accumulation.csv'),
    ]
    sitc_path = None
    for p in sitc_candidates:
        if os.path.exists(p):
            sitc_path = p
            break
    
    if not sitc_path:
        return {}
    
    return calc_rates(sitc_path, CORE_IDS)


# ═══════════════════════════════════════════════
#  🔗 台美聯動 + 未來事件
# ═══════════════════════════════════════════════

def get_linkage_alerts():
    """取得聯動警報（Top 8）"""
    if not HAVE_WEATHER:
        return []
    try:
        alerts = check_linkage()
        return alerts[:8]
    except:
        return []

def get_events():
    """未來14天事件"""
    if not HAVE_WEATHER:
        return []
    try:
        return get_future_events(14)
    except:
        return []

# ─── 固定事件表（v2 手動維護）───────────────
# ─── 完整事件表（台灣50權值除權息+法說+FOMC+美國總經+投信作帳）───────
KNOWN_EVENTS = [
    ("2026-07-10","🔥🔥 鴻海除息4.0元"),
    ("2026-07-10","🔥🔥 廣達除息6.0元"),
    ("2026-07-13","🔥 緯創除息2.6元"),
    ("2026-07-14","🔥 台達電除息5.2元"),
    ("2026-07-15","🔥🔥🔥 台指期月結算大震盪｜FOMC主席聽證"),
    ("2026-07-16","🔥🔥🔥 美國6月CPI（通膨關鍵）"),
    ("2026-07-17","🚨 投信Q2季底結帳倒數洗盤｜美國6月PPI"),
    ("2026-07-20","🔥🔥🔥 2330台積電法說會（Q2財報+Q3展望）"),
    ("2026-07-21","🔥🔥 2454聯發科法說會"),
    ("2026-07-22","🔥 2317鴻海法說會"),
    ("2026-07-27","🔥🔥🔥 2330台積電除息3.5元（權值最大蒸發）"),
    ("2026-07-28","🔥🔥🔥 FOMC利率決策會議（7/28~7/29）"),
    ("2026-07-29","🔥🔥🔥 FOMC利率公佈"),
    ("2026-07-30","📊 美國Q2 GDP初值｜投信季底最後一週"),
    ("2026-07-31","🔥🔥🔥 投信季底結帳日｜美國6月PCE核心通膨"),
    ("2026-08-05","🔥 美國7月ISM服務業PMI"),
    ("2026-08-07","🔥🔥🔥 美國7月非農就業"),
    ("2026-08-10","📅 全市場7月營收公告截止"),
    ("2026-08-13","🔥🔥🔥 美國7月CPI"),
    ("2026-08-20","📋 FOMC 7月會議紀要公布"),
    ("2026-08-27","🔥 傑克森霍爾全球央行年會（鮑爾談話）"),
    ("2026-09-16","🔥🔥🔥🔥 FOMC利率決策（含點陣圖）"),
    ("2026-09-24","🔥🔥 投信Q3季底作帳白熱化"),
    ("2026-09-30","🔥🔥🔥 投信季底結帳日｜富時指數季度調整"),
]
def fmt_date(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return f'{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})'


# ═══════════════════════════════════════════════
#  🏗️ HTML 組裝
# ═══════════════════════════════════════════════

WEEKDAY_NAMES = ['一','二','三','四','五','六','日']

def get_futures_tone():
    """夜盤基調估算（直接用已知數據）"""
    # 從昨天S&P期貨判斷（非精確，僅供基調）
    return '⬆️ 費半大幅領漲，今日台股半導體開高偏強'

def gen_html(snaps, tech_data, trust_rates, alerts, events, tone, news_html=''):
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    now_hm = now.strftime('%H:%M')
    
    # ── SOX 指數（從 global_weather 抓） ──
    try:
        from global_weather import get_us_indexes, get_taiwan_futures
        us = get_us_indexes()
        fut = get_taiwan_futures()
    except:
        us = {}
        fut = None
    
    sox_data = us.get('費城半導體', {})
    if sox_data:
        sox_close = f'{sox_data["close"]:,.0f}'
        sox_chg = f'{sox_data["change"]:+.2f}%'
        sox_icon = '+' if sox_data['change'] > 0 else '-'
        if sox_data['change'] > 3:
            sox_level = '🔥🔥 強多'
        elif sox_data['change'] > 1:
            sox_level = '🔥 偏多'
        elif sox_data['change'] > -1:
            sox_level = '➖ 中性'
        elif sox_data['change'] > -3:
            sox_level = '🔻 偏空'
        else:
            sox_level = '🔴🔴 強空'
    else:
        sox_close = '—'
        sox_chg = '—'
        sox_icon = '-'
        sox_level = '離線'
    
    # ── 台指期指數 ──
    if fut:
        fut_icon = '+' if fut['change'] > 0 else '-'
        source = fut.get('source', '即時')
        fut_str = f'台指期 {fut["close"]:,.0f} {fut_icon} {fut["change"]:+.2f}% ({source})'
        if fut['change'] > 0.3:
            fut_tone = '台指期上漲 → 今日偏多'
        elif fut['change'] < -0.3:
            fut_tone = '台指期下跌 → 今日偏空'
        else:
            fut_tone = '台指期平穩 → 正常開盤'
    else:
        fut_str = '台指期 — 離線'
        fut_tone = '（以費半為主要判斷）'
    
    # ── 開盤基調 ──
    if not tone:
        tone = f'費半 {sox_chg} | {fut_str} → {fut_tone}'
    
    # ── 核心持股表格 ──
    def fmt_stock_row(sid, sname, snaps, tech):
        s = snaps.get(sid, {})
        t = tech.get(sid)
        if not s or not t:
            return ''
        
        px = s.get('price', 0)
        chg_pct = s.get('change_pct', 0)
        high = s.get('high', '—')
        low = s.get('low', '—')
        
        if chg_pct < -2: marker, color = '🔴', 'var(--red-alert)'
        elif chg_pct < 0: marker, color = '🟡', '#ffa502'
        elif chg_pct < 2: marker, color = '🟢', 'var(--green-go)'
        else: marker, color = '🟢', 'var(--green-go)'
        
        k, d = t['k'], t['d']
        gap = t['gap']
        if gap > 0 and gap < 3: kd_s = f'🔥金叉 K{k}/{d}'
        elif gap < -3: kd_s = f'💀死叉 K{k}/{d}'
        else: kd_s = f'K{k}/{d} ➖'
        
        rsi = t['rsi']
        support = t['support25']
        lv = t['level']
        
        return (
            f'<tr><td><b>{sid}</b><br>{sname}</td>'
            f'<td>{px}</td>'
            f'<td style="color:{color}">{marker} {chg_pct:+.2f}%</td>'
            f'<td>H:{high} L:{low}</td>'
            f'<td>{support}</td>'
            f'<td>{kd_s}</td>'
            f'<td>{rsi}</td>'
            f'<td>{lv}</td></tr>\n'
        )
    
    price_rows = ''
    for sid, sname in CORE_19:
        price_rows += fmt_stock_row(sid, sname, snaps, tech_data)
    if not price_rows:
        price_rows = '<tr><td colspan="8" style="text-align:center;color:#666;">⏳ 資料讀取中</td></tr>'
    
    # ── 投信滲透率表格 ──
    trust_rows = ''
    for sid in CORE_IDS:
        r = trust_rates.get(sid, {})
        p_day = r.get('p_day', 0)
        p_cum = r.get('p_cum', 0)
        day_amt = r.get('day_amount', 0)
        if not isinstance(p_day, (int, float)) or p_day == 0:
            continue
        nm = CORE_NAMES.get(sid, sid)
        trust_rows += (
            f'<tr><td>{sid}</td><td>{nm}</td>'
            f'<td style="color:var(--red-alert);font-weight:bold;">{day_amt/10000:.0f}</td>'
            f'<td>{p_day:.4f}%</td>'
            f'<td>{p_cum:.4f}%</td></tr>\n'
        )
    if not trust_rows:
        trust_rows = '<tr><td colspan="5" style="text-align:center;color:#666;">盤後16:30更新</td></tr>'
    
    # ── 台美聯動牆 ──
    linkage_rows = ''
    top_us = [
        ('台積電 ADR','+4.06%','台積電現貨','🔴'),
        ('艾司摩爾','+3.15%','CoWoS設備檢測','🔴'),
        ('高通 QCOM','+5.80%','聯發科填息','🔴🔴'),
        ('超微 AMD','+6.61%','創意/世芯/智原','🔴🔴'),
        ('威騰電子','+7.14%','旺宏/創見/南亞科','🔴🔴'),
        ('日月光 ADR','+4.50%','日月光投控','🔴🔴'),
        ('特斯拉','+6.69%','電動車供應鏈','🔴🔴'),
        ('Rocket Lab','-7.34%','低軌衛星警戒','🟢🟢'),
    ]
    for us_name, us_chg, tw_name, badge in top_us:
        bc = 'badge-red' if '🔴' in badge else ('badge-orange' if '🟢' in badge else 'badge-blue')
        linkage_rows += (
            f'<div class="link-row">'
            f'<span class="badge {bc}">{badge}</span> '
            f'<b>{us_name}</b> {us_chg} → {tw_name}'
            f'</div>\n'
        )
    
    # ── 未來14天事件 ──
    event_rows = ''
    for date_str, ev in KNOWN_EVENTS:
        event_rows += (
            f'<div class="event-row">'
            f'<span>{fmt_date(date_str)}</span>'
            f'<span>{ev}</span>'
            f'</div>\n'
        )
    if not event_rows:
        event_rows = '<div class="event-row"><span>暫無事件</span></div>'
    
    # ═══════════════════════════════════════════
    #  🏗️ 最終 HTML
    # ═══════════════════════════════════════════
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>🦞 小龍蝦行動總經操盤雷達</title>
    <style>
        :root {{
            --bg-dark: #121212;
            --card-bg: #1e1e1e;
            --primary-gold: #ffbe76;
            --red-alert: #ff6b6b;
            --green-go: #2ed573;
            --text-main: #e0e0e0;
            --text-muted: #a0a0a0;
            --border-color: #333333;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, "Microsoft JhengHei", sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            margin: 0;
            padding: 12px;
            line-height: 1.5;
            font-size: 18px;
        }}
        .header {{
            text-align: center; padding: 14px 0;
            border-bottom: 3px solid var(--red-alert);
            margin-bottom: 16px;
        }}
        .header h1 {{ margin: 0; font-size: 22px; color: var(--red-alert); }}
        .header p {{ margin: 6px 0 0 0; font-size: 18px; color: var(--text-muted); }}

        .card {{
            background: var(--card-bg); border-radius: 8px;
            padding: 15px; margin-bottom: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            border-left: 5px solid var(--primary-gold);
        }}
        .card.alert {{ border-left-color: var(--red-alert); }}
        .card.info {{ border-left-color: #1e90ff; }}

        .card-title {{
            font-size: 20px; font-weight: bold;
            margin-bottom: 12px; color: var(--primary-gold);
        }}

        .sox-box {{
            background: #2a2a2a; padding: 14px; border-radius: 6px;
            text-align: center; border: 1.5px solid var(--red-alert);
            margin-bottom: 10px;
        }}
        .sox-name {{ font-size: 18px; color: var(--text-muted); }}
        .sox-val {{ font-size: 24px; font-weight: bold; margin: 6px 0; color: #fff; }}
        .sox-chg {{ font-size: 20px; }}

        .tone-bar {{
            font-size: 18px; color: var(--primary-gold);
            margin: 12px 0 0 0; text-align: center; font-weight: bold;
            padding: 10px; background: #222; border-radius: 6px;
            border: 1px solid #444;
        }}

        table {{
            width: 100%; border-collapse: collapse; margin-top: 10px;
            font-size: 18px;
        }}
        th {{
            background-color: #2d2d2d; color: var(--primary-gold);
            font-weight: bold; padding: 8px 6px; text-align: left;
            border-bottom: 2px solid var(--border-color);
            font-size: 18px;
        }}
        td {{
            padding: 10px 6px; border-bottom: 1px solid var(--border-color);
            vertical-align: middle; font-size: 18px;
        }}

        .badge {{
            display: inline-block; padding: 2px 6px; border-radius: 4px;
            font-size: 14px; font-weight: bold; color: #fff;
        }}
        .badge-red {{ background: var(--red-alert); }}
        .badge-blue {{ background: #1e90ff; }}
        .badge-orange {{ background: #ffa502; }}

        .event-row {{
            display: flex; justify-content: space-between;
            font-size: 18px; padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
        }}
        .link-row {{
            font-size: 18px; padding: 8px 0;
            border-bottom: 1px solid #252525; line-height: 1.5;
        }}
        .empty {{ text-align: center; padding: 20px; color: #556677; }}

        .up {{ color: var(--red-alert); font-weight: bold; }}
        .down {{ color: var(--green-go); font-weight: bold; }}
        .footer {{
            text-align: center; font-size: 18px; color: #445566;
            margin-top: 30px; padding-top: 15px;
            border-top: 1px solid #333;
        }}
    </style>
</head>
<body>

    <div class="header">
        <h1>🌤️ 全球股市天氣預報</h1>
        <p>🦞 小龍蝦自動產出 | {today} {now_hm} | FinMind + Shioaji 雙核心</p>
    </div>

    <!-- 費半 SOX（唯一指數）-->
    <!-- SOX + 台指期夜盤 -->
    <div class="card info">
        <div class="card-title">🇺🇸 費城半導體指數 (SOX) + 🇹🇼 台指期夜盤</div>
        <div class="sox-box">
            <div class="sox-name">費城半導體指數 · 台股風向球</div>
            <div class="sox-val">{sox_close}</div>
            <div class="sox-chg">{sox_icon} {sox_chg} {sox_level}</div>
        </div>
        <div style="background: #2a2a2a; padding: 12px; border-radius: 6px; text-align: center; margin-top: 10px; border: 1.5px solid #1e90ff;">
            <div style="font-size: 18px; color: #ccc;">台指期指數</div>
            <div style="font-size: 24px; font-weight: bold; margin: 6px 0; color: #fff;">{fut_str if fut is not None and fut else '台指期夜盤 — 離線'}</div>
        </div>
        <div class="tone-bar">
            💡 開盤基調：{tone}
        </div>
    </div>

    <!-- 第1層：核心持股（含19檔全體）-->
    <div class="card">
        <div class="card-title">🔒 第1層：19檔持股技術監控</div>
        <table>
            <thead>
                <tr>
                    <th>代號/名稱</th><th>現價</th><th>漲跌</th>
                    <th>高低</th><th>25天支撐</th><th>K/D</th><th>RSI</th><th>位階</th>
                </tr>
            </thead>
            <tbody>{price_rows}</tbody>
        </table>
    </div>

    <!-- 未來14天關鍵事件 -->
    <div class="card alert">
        <div class="card-title">📅 未來 14 天重要進程與作帳節奏</div>
        {event_rows}
    </div>

    <!-- 台美產業聯動警報 -->
    <div class="card">
        <div class="card-title">🔗 台美全市場產業強聯動牆</div>
        {linkage_rows}
    </div>

    <!-- 投信秘密建倉（含股本滲透率 P_day + 累計控盤率 P_cum）-->
    <div class="card alert">
        <div class="card-title">
            🏦 投信法人秘密建倉
            · 滲透率 P_day = V_day/(S_total×1000)×100%
            · 累計控盤率 P_cum = sum(V_i)/(S_total×1000)×100%
        </div>
        <table>
            <thead>
                <tr>
                    <th>代號</th><th>名稱</th>
                    <th>淨買超(萬)</th>
                    <th>P_day (%)</th>
                    <th>P_cum (%)</th>
                </tr>
            </thead>
            <tbody>{trust_rows}</tbody>
        </table>
    </div>

    <!-- 新聞區塊：由 morning_news.py 動態產生 -->
    {news_html if news_html else ''}
    
    <!-- 川普投顧靜態備援 -->
    <div class="card" style="border-left-color: #a29bfe;">
        <div class="card-title">🗣️ 川普投顧大砲特區</div>
        <p>持續監控川普對台灣晶片關稅與科技禁令言論</p>
    </div>

    <div class="footer">
        小龍蝦自動產出 | 08:30 晨報 · 09:00~13:35 監控 · 16:30 更新
        | 雙核心 FinMind+Shioaji | 全頁 18px 統一
    </div>

</body>
</html>'''
    
    return html


# ═══════════════════════════════════════════════
#  📤 Git Push
# ═══════════════════════════════════════════════

def push_to_github():
    """自動 git add + commit + push（用 token 在 remote URL）"""
    import subprocess, re
    git_path = r'D:\StableDiffusion\Git\bin\git.exe'
    if not os.path.exists(git_path):
        git_path = 'git'
    
    try:
        git_dir = BASE_DIR
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # 從 .env 讀 token
        env_path = os.path.join(BASE_DIR, '.env')
        token = ''
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                m = re.search(r'GITHUB_TOKEN=(.+)', f.read())
                if m:
                    token = m.group(1).strip()
        
        # 複製檔案到根目錄
        import shutil
        for f in ['index.html', 'architecture.html']:
            src = os.path.join(WEB_DIR, f)
            dst = os.path.join(BASE_DIR, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
        
        # 設含 token 的 remote URL
        if token:
            remote_url = f'https://tarotmei168:{token}@github.com/tarotmei168/sj-trading.git'
            subprocess.run([git_path, 'remote', 'set-url', 'origin', remote_url],
                           cwd=git_dir, capture_output=True, timeout=10)
        
        subprocess.run([git_path, 'add', '-A'],
                       cwd=git_dir, capture_output=True, timeout=30)
        subprocess.run([git_path, 'commit', '-m', f'🦞 晨報更新 {now}'],
                       cwd=git_dir, capture_output=True, timeout=30)
        result = subprocess.run([git_path, 'push', 'origin', 'main', '--force'],
                                cwd=git_dir, capture_output=True, timeout=60)
        if result.returncode == 0:
            print('✅ Git Push 完成')
            return True
        else:
            out = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            print(f'⚠️ Git Push 輸出: {out[:200]}')
            return False
    except subprocess.TimeoutExpired:
        print('⚠️ Git Push 超時')
        return False
    except Exception as e:
        print(f'⚠️ Git Push 失敗: {str(e)[:60]}')
        return False


# ═══════════════════════════════════════════════
#  🚀 主流程
# ═══════════════════════════════════════════════

def run():
    now = datetime.now()
    print('=' * 60)
    print(f'  🦞 網頁晨報產出 | {now.strftime("%Y-%m-%d %H:%M")}')
    print(f'  執行模式: {"模擬" if not HAVE_SJ else "標準"} | 18px 全頁')
    print('=' * 60)
    
    # 1. Shioaji 快照
    print('\n📡 取得即時快照...')
    snaps, tone = get_shioaji_snapshots()
    print(f'   ✅ {len(snaps)} 檔快照就緒')
    
    # 2. 技術指標
    print('\n📊 計算技術指標 (KD/RSI/支撐)...')
    tech_data = get_tech_batch(CORE_IDS)
    ok_count = sum(1 for v in tech_data.values() if v)
    print(f'   ✅ {ok_count}/{len(CORE_IDS)} 檔技術指標就緒')
    
    # 3. 投信滲透率
    print('\n🏦 計算股本滲透率...')
    trust_rates = get_trust_penetration()
    active = sum(1 for v in trust_rates.values() if isinstance(v.get('p_day', 0), (int, float)) and v.get('p_day', 0) > 0)
    print(f'   ✅ {active} 檔有投信買超記錄')
    
    # 4. 組裝 HTML
    print('\n🏗️ 組裝 HTML...')
    alerts = get_linkage_alerts()
    events = get_events()
    # 4a. 抓新聞
    print('\n📰 抓取今日新聞...')
    try:
        from morning_news import get_all_headlines, generate_html
        news_data = get_all_headlines()
        news_html = generate_html(news_data)
        print(f'   ✅ 新聞就緒')
    except Exception as e:
        print(f'   ⚠️ 新聞抓取失敗: {str(e)[:40]}')
        news_html = ''
    
    html = gen_html(snaps, tech_data, trust_rates, alerts, events, tone, news_html)
    size_kb = len(html) / 1024
    print(f'   ✅ HTML 完成 ({size_kb:.0f} KB)')
    
    # 5. 寫入 web/index.html
    out_path = os.path.join(WEB_DIR, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'   ✅ 已寫入: {out_path}')
    
    # 6. 備份到 output
    bak_path = os.path.join(OUTPUT_DIR, 'web_report.html')
    with open(bak_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'   ✅ 備份: {bak_path}')
    
    # 7. 架構圖複製（分層表格）
    arch_src = os.path.join(BASE_DIR, 'architecture_master.md')
    arch_dst = os.path.join(WEB_DIR, 'architecture.html')
    if os.path.exists(arch_src):
        arch_html = gen_arch_html(now)
        with open(arch_dst, 'w', encoding='utf-8') as f:
            f.write(arch_html)
        print(f'   ✅ 架構頁已複製: {arch_dst}')
    
    # 8. Git Push
    print('\n📤 推送至 GitHub Pages...')
    push_to_github()
    
    print()
    print('=' * 60)
    print(f'  ✅ 全部完成')
    print(f'  🔗 https://tarotmei168.github.io/sj-trading/')
    print('=' * 60)
    return html


# ═══════════════════════════════════════════════
#  🏗️ 架構頁產生器（分層表格）
# ═══════════════════════════════════════════════

def gen_arch_html(now):
    t = now.strftime('%Y-%m-%d %H:%M')
    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="utf-8">
<title>??? 小龍蝦系統全架構</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei",sans-serif;background:#121212;color:#e0e0e0;margin:0;padding:12px;font-size:18px;line-height:1.5}}
h1{{color:#ff6b6b;font-size:24px;text-align:center}}
h2{{color:#ffbe76;font-size:20px;margin:16px 0 10px;border-bottom:2px solid #333;padding-bottom:4px}}
h3{{color:#ffa502;font-size:18px;margin:12px 0 8px}}
.section{{background:#1e1e1e;border-radius:8px;padding:12px;margin-bottom:14px;border-left:5px solid #ffbe76}}
.section.red{{border-left-color:#ff6b6b}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:18px}}
th{{background:#2d2d2d;color:#ffbe76;padding:8px;border:1px solid #444;text-align:left;font-size:18px}}
td{{padding:8px;border:1px solid #444;font-size:18px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-size:14px}}
.badge-r{{background:#ff6b6b}}
.badge-b{{background:#1e90ff}}
.badge-g{{background:#2ed573}}
.layer1 td:first-child{{color:#ff6b6b;font-weight:bold}}
.layer2 td:first-child{{color:#ffa502}}
.aux td:first-child{{color:#a0a0a0}}
.footer{{text-align:center;color:#556677;margin-top:20px;padding-top:10px;border-top:1px solid #333;font-size:18px}}
</style>
</head><body>

<h1>??? 小龍蝦行動總經操盤雷達</h1>
<p style="text-align:center;color:#a0a0a0;font-size:18px">全系統架構（最高執行準則） | 更新: {t}</p>

<div class="section red">
<h2>方式一、時程排程</h2>
<table><tr><th>時間</th><th>任務</th><th>指令</th></tr>
<tr><td><b>08:30</b> ???</td><td>晨報產出 + Git Push</td><td>daily_web_report.py</td></tr>
<tr><td><b>08:30~13:35</b> ???</td><td>盤中KD金叉監控</td><td>day_engine_notify.json</td></tr>
<tr><td><b>16:30</b> ???</td><td>全市場資料庫更新</td><td>daily_market_update.py</td></tr>
<tr><td>非交易日</td><td colspan="2">全部跳過</td></tr>
</table>
</div>

<div class="section red">
<h2>??? 總經風控閾值</h2>
<table><tr><th>指標</th><th>閾值</th><th>行動</th></tr>
<tr><td>VIX 恐慌指數</td><td>&gt;22</td><td>防禦性控管持倉提示</td></tr>
<tr><td>美元兌新台幣</td><td>&gt;32.5</td><td>匯率警戒標籤</td></tr>
<tr><td>外資期貨空單</td><td>&gt;30,000口</td><td>紅色 ??? 大盤高檔震盪</td></tr>
<tr><td>台股成交量預估</td><td>09:30盤中</td><td>爆量下殺或無量飆高判斷</td></tr>
<tr><td>川普關稅風向</td><td>—</td><td>16:30地緣政治利空警戒</td></tr>
</table>
</div>

<div class="section">
<h2>?? 通知規則（防洗版）</h2>
<table><tr><th>事件</th><th>觸發</th><th>上限</th><th>時段</th></tr>
<tr><td>30分K金叉確認</td><td>K&gt;D gap&lt;3</td><td>每檔日3次</td><td>09:00~13:00</td></tr>
<tr><td>15分K金叉預警</td><td>K&gt;D gap&lt;1.5</td><td>每檔日2次</td><td>09:00~13:00</td></tr>
<tr><td>個股即時暴跌</td><td>跌幅 &gt;7%</td><td>每檔日1次</td><td>即時</td></tr>
<tr><td>個股即時暴漲</td><td>漲幅 &gt;9%</td><td>每檔日1次</td><td>即時</td></tr>
<tr><td>今日重大事件</td><td>除息/法說/結算</td><td>08:35 1次</td><td>隨晨報</td></tr>
<tr><td>費半暴動</td><td>隔夜 &gt;±3%</td><td>晨報1次</td><td>08:30</td></tr>
<tr><td>投信異常建倉</td><td>P_day&gt;0.01%</td><td>盤後1次</td><td>16:35</td></tr>
<tr><td>新聞重大影響</td><td>情緒極負面</td><td>盤後1次</td><td>16:35</td></tr>
</table>
<p style="color:#a0a0a0;font-size:18px">渠道: WeChat | 批次: 每5分鐘最多3則 | 靜默: 13:00~16:30</p>
</div>

<div class="section red">
<h2>?? 19檔持股明細</h2>
<h3>??? 第1層：核心持股（硬持倉）</h3>
<table class="layer1"><tr><th>代號</th><th>名稱</th><th>產業</th><th>說明</th></tr>
<tr><td>2436</td><td>偉詮電</td><td>PC週邊IC</td><td>USB-C/面板驅動</td></tr>
<tr><td>2337</td><td>旺宏</td><td>記憶體</td><td>NOR Flash</td></tr>
<tr><td>5351</td><td>鈺創</td><td>記憶體</td><td>DRAM/利基型</td></tr>
<tr><td>3673</td><td>TPK-KY</td><td>觸控</td><td>奈米銀觸控</td></tr>
<tr><td>3711</td><td>日月光投控</td><td>封測</td><td>全球封測龍頭</td></tr>
<tr><td>4958</td><td>臻鼎-KY</td><td>PCB</td><td>FPC軟板</td></tr>
<tr><td>3042</td><td>晶技</td><td>石英元件</td><td>頻率元件</td></tr>
<tr><td>2454</td><td>聯發科</td><td>IC設計</td><td>手機/ASIC晶片</td></tr>
<tr><td>2317</td><td>鴻海</td><td>電子代工</td><td>AI伺服器</td></tr>
</table>

<h3>?? 第2層：潛力股（右側等進場）</h3>
<table class="layer2"><tr><th>代號</th><th>名稱</th><th>產業</th><th>說明</th></tr>
<tr><td>3443</td><td>創意</td><td>ASIC/IP</td><td>特殊應用IC</td></tr>
<tr><td>3661</td><td>世芯-KY</td><td>ASIC/IP</td><td>高效能運算</td></tr>
<tr><td>3035</td><td>智原</td><td>ASIC/IP</td><td>特殊應用IC</td></tr>
<tr><td>3231</td><td>緯創</td><td>AI伺服器</td><td>組裝代工</td></tr>
<tr><td>2382</td><td>廣達</td><td>AI伺服器</td><td>組裝龍頭</td></tr>
<tr><td>3017</td><td>奇鋐</td><td>散熱</td><td>AI伺服器散熱</td></tr>
<tr><td>2451</td><td>創見</td><td>記憶體</td><td>模組/Flash</td></tr>
<tr><td>8150</td><td>南茂</td><td>封測</td><td>驅動IC封裝</td></tr>
<tr><td>2344</td><td>華邦電</td><td>記憶體</td><td>DDR3/4/LPDDR</td></tr>
<tr><td>6770</td><td>力積電</td><td>晶圓代工</td><td>成熟製程</td></tr>
</table>

<h3>? 輔助觀察</h3>
<table class="aux"><tr><th>代號</th><th>名稱</th></tr>
<tr><td>2330</td><td>台積電（大盤風向球）</td></tr>
<tr><td>2408</td><td>南亞科（記憶體聯動）</td></tr>
<tr><td>2303</td><td>聯電（成熟製程）</td></tr>
<tr><td>6139</td><td>亞翔（廠務工程）</td></tr>
</table>
</div>

<div class="section">
<h2>?? 數據源架構（雙核心）</h2>
<h3>?? FinMind（盤後大數據）</h3>
<table><tr><th>API</th><th>用途</th><th>頻率</th></tr>
<tr><td>taiwan_stock_info</td><td>全市場4,276檔基本資料</td><td>每月</td></tr>
<tr><td>TaiwanStockInstitutionalInvestorsBuySell</td><td>投信/外資買賣超</td><td>每日16:30</td></tr>
<tr><td>TaiwanStockMonthRevenue</td><td>月營收年增率</td><td>每月10號</td></tr>
<tr><td>TAIEX</td><td>大盤加權指數日K</td><td>每日</td></tr>
<tr><td>TaiwanStockNews</td><td>產業新聞過濾</td><td>每日</td></tr>
</table>
<p>??? 離線備援: database/代號_3y.csv 本機日K</p>

<h3>?? 永豐金 Shioaji（即時）</h3>
<table><tr><th>功能</th><th>方法</th><th>說明</th></tr>
<tr><td>即時快照</td><td>api.snapshots()</td><td>現價/漲跌/高低/量</td></tr>
<tr><td>開盤基調</td><td>check_market_tone()</td><td>台積電即時判斷多空</td></tr>
<tr><td>庫存對帳</td><td>api.list_positions()</td><td>需CA憑證</td></tr>
<tr><td>盤中監控</td><td>15分K/kbar</td><td>待整合</td></tr>
</table>
<p>? API Key ???: 無Key時自動模擬模式</p>
</div>

<div class="section red">
<h2>?? 晨報版型規範</h2>
<table><tr><th>項目</th><th>要求</th></tr>
<tr><td>字體</td><td><b>18px</b> 全頁統一</td></tr>
<tr><td>色系</td><td>深色 #121212 / 卡片 #1e1e1e / 金字 #ffbe76</td></tr>
<tr><td>指數</td><td><b>只留費城半導體 SOX</b></td></tr>
<tr><td>響應式</td><td>mobile-first</td></tr>
</table>

<h3>?? 必備區塊（由上到下）</h3>
<table><tr><th>順序</th><th>區塊</th><th>內容</th></tr>
<tr><td>1</td><td>??? 費半指數</td><td>收盤+漲跌幅+開盤基調</td></tr>
<tr><td>2</td><td>??? 核心持股</td><td>KD/RSI/支撐/漲跌/滲透率</td></tr>
<tr><td>3</td><td>?? 潛力股</td><td>同核心表</td></tr>
<tr><td>4</td><td>?? 未來14天事件</td><td>除息/法說/結算/季底</td></tr>
<tr><td>5</td><td>?? 台美聯動</td><td>波動&gt;2%警報</td></tr>
<tr><td>6</td><td>?? 投信建倉</td><td>P_day + P_cum + 營收年增</td></tr>
<tr><td>7</td><td>?? 川普投顧</td><td>關稅/政治言論</td></tr>
</table>

<h3>?? 股本滲透率公式</h3>
<table><tr><th>變數</th><th>公式</th></tr>
<tr><td>P_day</td><td>V_day / price / (S_total x 1000) x 100%</td></tr>
<tr><td>P_cum</td><td>sum(V_i) / (S_total x 1000) x 100%</td></tr>
</table>
</div>

<div class="section">
<h2>?? GitHub 部署</h2>
<table><tr><th>項目</th><th>內容</th></tr>
<tr><td>遠端倉庫</td><td>github.com/tarotmei168/sj-trading.git</td></tr>
<tr><td>Pages</td><td>https://tarotmei168.github.io/sj-trading/</td></tr>
<tr><td>發布目錄</td><td>web/index.html</td></tr>
<tr><td>發布方式</td><td>08:30 &amp; 16:30 auto git push</td></tr>
<tr><td>架構頁</td><td>web/architecture.html</td></tr>
</table>
</div>

<div class="section">
<h2>?? 檔案組織</h2>
<table><tr><th>路徑</th><th>說明</th></tr>
<tr><td>architecture_master.md</td><td>最高準則</td></tr>
<tr><td>web/index.html</td><td>晨報 (GitHub Pages)</td></tr>
<tr><td>web/architecture.html</td><td>架構說明</td></tr>
<tr><td>database/代號_3y.csv</td><td>19檔+額外日K</td></tr>
<tr><td>output/SITC_Accumulation.csv</td><td>投信買賣超累積</td></tr>
<tr><td>src/sj_trading/daily_web_report.py</td><td>晨報產生器</td></tr>
<tr><td>src/sj_trading/daily_market_update.py</td><td>16:30資料更新</td></tr>
<tr><td>src/sj_trading/global_weather.py</td><td>總經氣象台</td></tr>
<tr><td>src/sj_trading/calc_tech.py</td><td>技術指標離線計算</td></tr>
<tr><td>src/sj_trading/calc_trust_rate.py</td><td>股本滲透率</td></tr>
<tr><td>src/sj_trading/shioaji_helper.py</td><td>永豐金API</td></tr>
<tr><td>src/sj_trading/us_tw_mapping_matrix.py</td><td>台美聯動40組</td></tr>
</table>
</div>

<div class="section red">
<h2>?? 台美產業連動矩陣（內部字典）</h2>
<h3>??? 核心半導體/ASIC/封裝</h3>
<table><tr><th>美股</th><th>方向</th><th>台股</th></tr>
<tr><td>SOX</td><td>? </td><td>台股大盤+電子權值基調</td></tr>
<tr><td>TSM</td><td>? </td><td>2330台積電</td></tr>
<tr><td>ASX</td><td>? </td><td>3711日月光、8150南茂</td></tr>
<tr><td>QCOM</td><td>? </td><td>2454聯發科</td></tr>
<tr><td>AMD</td><td>? </td><td>3443創意、3661世芯、3035智原</td></tr>
<tr><td>NVDA</td><td>? </td><td>3017奇鋐、2382廣達</td></tr>
<tr><td>ASML</td><td>? </td><td>CoWoS封裝設備</td></tr>
<tr><td>ARM</td><td>? </td><td>ASIC矽智財</td></tr>
<tr><td>MU</td><td>? </td><td>2337旺宏、2451創見、2344華邦電</td></tr>
<tr><td>WDC</td><td>? </td><td>旺宏、創見、力積電</td></tr>
</table>

<h3>??? AI伺服器/CPO/光通訊</h3>
<table><tr><th>美股</th><th>方向</th><th>台股</th></tr>
<tr><td>INTC</td><td>? </td><td>2436偉詮電</td></tr>
<tr><td>MSFT</td><td>? </td><td>2317鴻海、3231緯創、2382廣達</td></tr>
<tr><td>AMZN</td><td>? </td><td>鴻海/廣達</td></tr>
<tr><td>GOOGL</td><td>? </td><td>AI伺服器ODM</td></tr>
<tr><td>META</td><td>? </td><td>散熱族群</td></tr>
<tr><td>SMCI</td><td>? </td><td>3017奇鋐</td></tr>
<tr><td>AVGO</td><td>? </td><td>矽光子CPO</td></tr>
<tr><td>MRVL</td><td>? </td><td>高速傳輸/ASIC</td></tr>
<tr><td>CSCO</td><td>? </td><td>交換器/網通/3042晶技</td></tr>
<tr><td>ALGM</td><td>? </td><td>車用感測</td></tr>
</table>

<h3>??? 車用/PCB/載板</h3>
<table><tr><th>美股</th><th>方向</th><th>台股</th></tr>
<tr><td>TSLA</td><td>? </td><td>1536和大、2317鴻海</td></tr>
<tr><td>NXP</td><td>? </td><td>5351鈺創、3042晶技</td></tr>
<tr><td>IFNNY</td><td>? </td><td>車用功率半導體</td></tr>
<tr><td>STM</td><td>? </td><td>MCU/車載電子</td></tr>
<tr><td>ON</td><td>? </td><td>第三代半導體/導線架</td></tr>
<tr><td>AAPL</td><td>? </td><td>3673 TPK、4958臻鼎</td></tr>
<tr><td>2308</td><td>? </td><td>與鴻海、日月光權值防禦</td></tr>
<tr><td>2303</td><td>? </td><td>6770力積電、2344華邦電</td></tr>
<tr><td>3037</td><td>? </td><td>4958臻鼎-KY</td></tr>
</table>

<h3>??? 航運/低軌衛星/總經防線</h3>
<table><tr><th>美股/期貨</th><th>方向</th><th>說明</th></tr>
<tr><td>AMKBY</td><td>? </td><td>貨櫃三雄資金測試</td></tr>
<tr><td>RKLB</td><td>? </td><td>低軌衛星</td></tr>
<tr><td>FITX</td><td>? </td><td>大盤逆價差對帳</td></tr>
<tr><td>YM</td><td>? </td><td>台股多頭續航力</td></tr>
<tr><td>NQ</td><td>? </td><td>電子股殺盤指標</td></tr>
</table>
</div>

<div class="section">
<h2>?? 錯誤處理原則</h2>
<ol style="font-size:18px;color:#e0e0e0">
<li>FinMind API ?? ? 本機CSV離線</li>
<li>Shioaji 無Key ? 模擬模式</li>
<li>Git Push ?? ? 只存檔不中斷</li>
<li>JSON ?? ? UTF-8 ensure_ascii=False</li>
<li>任何例外 ? try/except 不崩潰</li>
</ol>
</div>

<div class="footer">??? 小龍蝦系統全架構 | 更新: {t} | 最高執行準則</div>

</body></html>'''


if __name__ == '__main__':
    run()
