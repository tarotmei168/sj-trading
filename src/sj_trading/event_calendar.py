#!/usr/bin/env python3
"""
📅 事件行事曆引擎（自動來源）
=============================
資料來源：
  1. 證交所除權息預告表 (TWSE TWT48U) → API即時
  2. 美國總經行事曆 → 固定排程程式化產生
  3. 投信季底作帳 → 固定日期推算

不再用手寫 KNOWN_EVENTS，全部自動產生。
"""

import requests, json
from datetime import datetime, timedelta, date
from typing import Optional

# ── 核心持股監控清單（用於過濾除權息事件）──
CORE_CODES = {
    '2330', '2454', '2317', '3711', '3042', '4958', '8150',
    '2337', '5351', '2436', '3673', '0050',
    '2382', '3231', '3443', '3661', '3035', '3017', '2451',
    '2344', '6770',
}

WEEKDAY_NAMES = ['一','二','三','四','五','六','日']


def fmt_date(d: date) -> str:
    return f'{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})'


def fetch_twse_dividend(from_date: date, to_date: date) -> list:
    """從證交所抓除權息預告表"""
    events = []
    url = 'https://www.twse.com.tw/exchangeReport/TWT48U'
    params = {
        'response': 'json',
        'strDate': from_date.strftime('%Y%m%d'),
        'endDate': to_date.strftime('%Y%m%d'),
    }
    try:
        r = requests.get(url, params=params, timeout=10).json()
        if r.get('stat') == 'OK' and r.get('data'):
            for row in r['data']:
                code = row[1]
                name = row[2]
                ex_type = row[3]  # 息/權
                cash = row[7]     # 現金股利
                ex_date_str = row[0]  # '115年07月21日'
                # 轉成 YYYY-MM-DD
                try:
                    # 民國年轉西元
                    y_str = ex_date_str.replace('年', '-').replace('月', '-').replace('日', '')
                    parts = y_str.split('-')
                    if len(parts) == 3:
                        yr = int(parts[0]) + 1911
                        ex_date = date(yr, int(parts[1]), int(parts[2]))
                    else:
                        continue
                except:
                    continue
                
                # 過濾只留核心持股 + 台灣50成分股相關
                if code not in CORE_CODES:
                    continue
                
                # 判斷重要性
                impact = '🔥'
                if code in ('2330', '2454', '2317'):
                    impact = '🔥🔥🔥'
                elif code in ('3711', '2382'):
                    impact = '🔥🔥'
                
                # 現金股利文字
                cash_str = ''
                if cash and cash not in ('', '0.00000000'):
                    try:
                        cash_val = float(cash.replace(',', ''))
                        cash_str = f'{cash_val:.1f}元'
                    except:
                        pass
                
                ev = f'{impact} {code}{name}除息{cash_str}'.strip()
                events.append((ex_date, ev))
    except:
        pass
    return events


def generate_us_econ_calendar() -> list:
    """產生美國總經行事曆（固定排程推算）"""
    today = date.today()
    year = today.year
    events = []
    
    # FOMC 固定會議日期（一年8次）
    fomc_dates = [
        (1, 29), (3, 19), (5, 7), (6, 18),
        (7, 30), (9, 17), (11, 5), (12, 17),
    ]
    for m, d in fomc_dates:
        ev_date = date(year, m, d)
        if today <= ev_date <= today + timedelta(days=60):
            if m == 7 and d == 30:
                events.append((ev_date, '🔥🔥🔥 FOMC利率決策會議'))
            elif m == 9:
                events.append((ev_date, '🔥🔥🔥🔥 FOMC利率決策（含點陣圖）'))
            else:
                events.append((ev_date, '🔥🔥 FOMC利率決策'))
    
    # 非農就業：每月第一個星期五
    for m in range(1, 13):
        first_day = date(year, m, 1)
        wd = first_day.weekday()
        days_to_friday = (4 - wd) % 7
        nfp_date = first_day + timedelta(days=days_to_friday)
        if today <= nfp_date <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((nfp_date, f'🔥🔥🔥 美國{month_name}非農就業'))
    
    # CPI：每月13~15日（取15日，遇假日往前）
    for m in range(1, 13):
        cpi_date = date(year, m, 15)
        if cpi_date.weekday() >= 5:  # 週末往前
            cpi_date = cpi_date - timedelta(days=cpi_date.weekday() - 4)
        if today <= cpi_date <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((cpi_date, f'🔥🔥🔥 美國{month_name}CPI'))
    
    # PCE：每月最後一個週五
    for m in range(1, 13):
        last_day = date(year, m + 1, 1) - timedelta(days=1) if m < 12 else date(year, 12, 31)
        days_to_friday = (last_day.weekday() - 4) % 7
        pce_date = last_day - timedelta(days=days_to_friday)
        if today <= pce_date <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((pce_date, f'🔥🔥 美國{month_name}PCE核心通膨'))
    
    # GDP初值：1月/4月/7月/10月 下旬
    gdp_months = [1, 4, 7, 10]
    for m in gdp_months:
        gdp_date = date(year, m, 28)
        if today <= gdp_date <= today + timedelta(days=60):
            q = (m // 3) + 1
            events.append((gdp_date, f'🔥🔥 美國Q{q} GDP初值'))
    
    # 傑克森霍爾年會：8月最後一個週五前後
    aug_last = date(year, 8, 31)
    jackson_date = aug_last - timedelta(days=(aug_last.weekday() - 4) % 7) - timedelta(days=7)
    if today <= jackson_date <= today + timedelta(days=60):
        events.append((jackson_date, '🔥 傑克森霍爾全球央行年會（鮑爾談話）'))
    
    # FOMC 會議紀要：會後3週公布
    for m, d in fomc_dates:
        meeting_date = date(year, m, d)
        minutes_date = meeting_date + timedelta(days=21)
        if today <= minutes_date <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((minutes_date, f'📋 FOMC {month_name}會議紀要公布'))
    
    # ISM製造業/服務業：每月1日/5日左右
    for m in range(1, 13):
        ism_m = date(year, m, 1)
        ism_s = date(year, m, 5)
        if today <= ism_m <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((ism_m, f'🔥 美國{month_name}ISM製造業PMI'))
        if today <= ism_s <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((ism_s, f'🔥 美國{month_name}ISM服務業PMI'))
    
    return events


def generate_tw_calendar() -> list:
    """產生台股固定行事曆"""
    today = date.today()
    year = today.year
    events = []
    
    # 投信季底作帳
    quarter_ends = [
        (3, 31, 'Q1季底', '🔥🔥'),
        (6, 30, 'Q2季底', '🔥🔥🔥'),
        (9, 30, 'Q3季底', '🔥🔥🔥'),
        (12, 31, 'Q4季底', '🔥🔥🔥'),
    ]
    for m, d, qlabel, impact in quarter_ends:
        qe = date(year, m, d)
        if today <= qe <= today + timedelta(days=60):
            events.append((qe, f'{impact} 投信{qlabel}結帳日'))
            # 結帳前一週
            qe_1w = qe - timedelta(days=7)
            if today <= qe_1w:
                events.append((qe_1w, f'🔥 投信{qlabel}作帳白熱化'))
    
    # 營收公告截止（每月10日）
    for m in range(1, 13):
        rev_date = date(year, m, 10)
        if rev_date.weekday() >= 5:
            rev_date = rev_date + timedelta(days=(7 - rev_date.weekday()))
        if today <= rev_date <= today + timedelta(days=60):
            month_name = f'{m}月'
            events.append((rev_date, f'📅 全市場{month_name}營收公告截止'))
    
    # 台指期結算：每月第3個星期三
    for m in range(1, 13):
        first_day = date(year, m, 1)
        wd = first_day.weekday()
        # 找到第一個星期三
        days_to_wed = (2 - wd) % 7
        third_wed = first_day + timedelta(days=days_to_wed + 14)
        if today <= third_wed <= today + timedelta(days=60):
            events.append((third_wed, '🔥🔥 台指期月結算'))
    
    return events


# ═══════════════════════════════════════════════
#  主輸出：合併所有事件
# ═══════════════════════════════════════════════
def get_all_events(days: int = 14, include_core_only: bool = True) -> list:
    """取得未來N天所有事件（合併除權息+總經+台股行事曆）"""
    today = date.today()
    end_date = today + timedelta(days=days)
    
    all_events = []
    
    # 1. 證交所除權息
    if include_core_only:
        div_events = fetch_twse_dividend(today, end_date)
    else:
        div_events = fetch_twse_dividend(today, end_date)
    all_events.extend(div_events)
    
    # 2. 美國總經
    us_events = generate_us_econ_calendar()
    for ev_date, name in us_events:
        if today <= ev_date <= end_date:
            all_events.append((ev_date, name))
    
    # 3. 台股固定行事曆
    tw_events = generate_tw_calendar()
    for ev_date, name in tw_events:
        if today <= ev_date <= end_date:
            all_events.append((ev_date, name))
    
    # 去重、排序
    seen = set()
    unique = []
    for ev_date, name in sorted(all_events, key=lambda x: x[0]):
        key = f'{ev_date}{name[:20]}'
        if key not in seen:
            seen.add(key)
            unique.append({
                'date': ev_date.strftime('%Y-%m-%d'),
                'days': (ev_date - today).days,
                'name': name,
            })
    
    return unique


# ═══════════════════════════════════════════════
#  ⚡ 快速測試
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    print('📅 未來14天事件（自動來源）')
    print('=' * 60)
    events = get_all_events(days=60)
    for e in events:
        days_str = '📌今天' if e['days'] == 0 else '📌明天' if e['days'] == 1 else f'{e[\"days\"]}天後'
        print(f'  {e[\"date\"]} | {days_str} | {e[\"name\"]}')
