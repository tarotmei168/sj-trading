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

# 富邦爬蟲（即時抓取，不用 PIP）
from fubon_force_crawler import fetch_force_top_2d, fetch_trust_top_1d, fubon_crawler

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

# 載入 .env（永豐金 API Key）
try:
    from dotenv import load_dotenv
    env_path = os.path.join(BASE_DIR, '.env')
    load_dotenv(env_path)
except:
    pass

# ─── 19檔持股（架構文件規定）──────────────────
# ─── 11檔核心持股（純核心倉位）──────────────────
# 潛力股從 trust_scan_latest.json 動態載入
CORE_19 = [
    ('2436','偉詮電'), ('2337','旺宏'), ('5351','鈺創'),
    ('3673','TPK-KY'), ('3711','日月光'), ('4958','臻鼎-KY'),
    ('3042','晶技'), ('2454','聯發科'), ('2317','鴻海'),
    ('8150','南茂'), ('2330','台積電'), ('0050','元大台灣50'),
]
CORE_IDS = [s[0] for s in CORE_19]
CORE_NAMES = {s[0]: s[1] for s in CORE_19}

# ─── 星期對照 ────────────────────────────────
WEEKDAY_NAMES = ['一','二','三','四','五','六','日']

# ═══════════════════════════════════════════════
#  📦 模組匯入 (graceful fallback)
# ═══════════════════════════════════════════════

# calc_tech: KD/RSI/支撐 (完全離線)
from calc_tech import read_local_csv, calc_STOCH, calc_RSI, calc_MACD

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
    
    try:
        if sjc:
            sjc.login()
            sjc_ok = True
        else:
            sjc_ok = False
    except Exception as sjc_e:
        print(f'[Shioaji] 登入失敗: {sjc_e}')
        sjc_ok = False
    
    if sjc_ok:
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

# ── 3年30分K KD最佳參數（2026-07-21回測）──
KD3Y_PARAMS = {
    "2436": {"K":5, "VolF":0, "Pos":"none"},
    "2337": {"K":21, "VolF":0, "Pos":"none"},
    "5351": {"K":14, "VolF":0, "Pos":"none"},
    "3673": {"K":14, "VolF":1, "Pos":"none"},
    "3711": {"K":21, "VolF":0, "Pos":"none"},
    "4958": {"K":21, "VolF":0, "Pos":"mid"},
    "3042": {"K":14, "VolF":1, "Pos":"none"},
    "2454": {"K":21, "VolF":0, "Pos":"none"},
    "2317": {"K":14, "VolF":1, "Pos":"none"},
    "8150": {"K":21, "VolF":0, "Pos":"none"},
    "2330": {"K":9, "VolF":1, "Pos":"none"},
    "0050": {"K":9, "VolF":0, "Pos":"none"},  # ETF用日K KD，K=9保守
}

import numpy as np

def compute_talib_stoch(highs, lows, closes, fastk=14, slowk=1, slowd=3):
    """TA-Lib STOCH(14,1,3) — TradingView 標準預設"""
    import talib
    k_vals, d_vals = talib.STOCH(highs, lows, closes,
                                  fastk_period=fastk,
                                  slowk_period=slowk,
                                  slowk_matype=0,
                                  slowd_period=slowd,
                                  slowd_matype=0)
    return k_vals, d_vals

def _fetch_rsi_from_finmind(stock_id):
    """用 yfinance 抓近60個交易日日K，算RSI(14) (FinMind已付費,改用yfinance)"""
    try:
        import yfinance as yf
        tw_sid = stock_id + '.TW' if not stock_id.startswith('0050') else stock_id + '.TW'
        tk = yf.Ticker(tw_sid)
        df = tk.history(period='6mo')
        if df is not None and len(df) >= 15:
            closes = df['Close'].values[-62:]
            import numpy as np
            arr = np.array(closes, dtype=float)
            deltas = np.diff(arr)
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)
            avg_gain = np.mean(gains[-14:])
            avg_loss = np.mean(losses[-14:])
            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            rsi = round(100 - 100 / (1 + rs), 1)
            return rsi
        return 50.0
    except Exception as e:
        print(f'  RSI fail ({stock_id}): {str(e)[:50]}')
        return 50.0


def get_tech_batch(stock_ids):
    """批次產出技術指標（3年30分K KD + RSI + 量能）"""
    result = {}
    for sid in stock_ids:
        data = read_local_csv(sid)
        if not data or len(data) < 25:
            # 沒本機資料的：先用 yfinance（免費，不需 API Key）
            data = None
            try:
                import yfinance as yf
                tw_sid = sid + '.TW' if not sid.startswith('0050') else sid + '.TW'
                tk = yf.Ticker(tw_sid)
                df = tk.history(period='3mo')
                if df is not None and len(df) >= 25:
                    items = df.reset_index().to_dict('records')
                    data = []
                    for d in items:
                        data.append({
                            'close': float(d['Close']),
                            'high': float(d['High']),
                            'low': float(d['Low']),
                            'volume': int(d['Volume']) if d['Volume'] else 0,
                        })
                    closes = np.array([d['close'] for d in data], dtype=float)
                    highs = np.array([d['high'] for d in data], dtype=float)
                    lows = np.array([d['low'] for d in data], dtype=float)
                    volumes = np.array([d['volume'] for d in data], dtype=float)
            except:
                pass
            if data is None:
                result[sid] = None
                continue
        else:
            closes = np.array([d['close'] for d in data], dtype=float)
            highs = np.array([d['high'] for d in data], dtype=float)
            lows = np.array([d['low'] for d in data], dtype=float)
            volumes = np.array([d['volume'] for d in data], dtype=float)
        
        # KD: TA-Lib STOCH(14,1,3) — TradingView 標準
        k_vals, d_vals = compute_talib_stoch(highs, lows, closes, 14, 1, 3)
        k = float(k_vals[-1]) if not np.isnan(k_vals[-1]) else 50.0
        d = float(d_vals[-1]) if not np.isnan(d_vals[-1]) else 50.0
        gap = k - d
        golden = k >= d
        # 取前一筆K判斷趨勢
        k_prev = float(k_vals[-2]) if len(k_vals) >= 2 and not np.isnan(k_vals[-2]) else k
        k_trend_up = k > k_prev
        
        # RSI: TA-Lib RSI(14) — TradingView 標準
        try:
            rsi_val = calc_RSI(closes)
        except:
            rsi_val = 50.0
        
        # 量能（還是用30分K的最後幾根來比）
        if len(volumes) >= 25:
            vol5 = float(np.mean(volumes[-5:]))
            vol20 = float(np.mean(volumes[-20:-5])) if len(volumes) >= 25 else vol5
            vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0
        else:
            vol5 = float(np.mean(volumes[-5:])) if len(volumes) >= 5 else 0
            vol20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else vol5
            vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0
        
        if vol_ratio > 1.5: vol_note = '放量🟢'
        elif vol_ratio < 0.8: vol_note = '量縮🔴'
        else: vol_note = '平量⚪'
        
        # 位階
        if rsi_val < 30: level = '超賣'
        elif rsi_val < 40: level = '偏低'
        elif rsi_val < 55: level = '中性'
        elif rsi_val < 70: level = '偏多'
        else: level = '過熱'
        
        # MACD: TA-Lib MACD(12,26,9) — TradingView 標準
        try:
            _macd, _sig, _hist = calc_MACD(closes)
            macd_val = round(float(_macd[-1]), 2) if not np.isnan(_macd[-1]) else None
            sig_val = round(float(_sig[-1]), 2) if not np.isnan(_sig[-1]) else None
            hist_val = round(float(_hist[-1]), 2) if not np.isnan(_hist[-1]) else None
            # 取前一根hist來判斷柱狀體方向
            hist_prev = float(_hist[-2]) if len(_hist) >= 2 and not np.isnan(_hist[-2]) else None
        except:
            macd_val = sig_val = hist_val = hist_prev = None
        
        result[sid] = {
            'k': round(k, 1), 'd': round(d, 1), 'gap': round(gap, 1),
            'golden': golden, 'rsi': rsi_val,
            'macd': macd_val, 'macd_sig': sig_val, 'macd_hist': hist_val,
            'macd_hist_prev': hist_prev,
            'low_30d': _get_30d_low(sid),
            'vol_ratio': round(vol_ratio, 2), 'vol_note': vol_note,
            'price': closes[-1],
            'prev_close': closes[-2] if len(closes) >= 2 else None,
            'level': level,
        }
    return result

# ═══════════════════════════════════════════════
#  🏦 股本滲透率 (P_day + P_cum)
# ═══════════════════════════════════════════════

def _get_30d_low(stock_id):
    """從本機CSV取最近30根K棒最低價最低值（判斷支撐位），無本機資料則用FinMind"""
    data = read_local_csv(stock_id)
    if not data or len(data) < 5:
        # FinMind 備援
        try:
            import requests
            url = 'https://api.finmindtrade.com/api/v4/data'
            params = {'dataset': 'TaiwanStockPrice', 'data_id': stock_id, 'start_date': '2026-05-01', 'end_date': datetime.now().strftime('%Y-%m-%d')}
            r = requests.get(url, params=params, timeout=10).json()
            if r.get('status') == 200 and r.get('data') and len(r['data']) >= 5:
                items = r['data']
                lows = [d['min'] for d in items[-30:]]
                return round(float(min(lows)), 1)
        except:
            pass
        return None
    tail = data[-30:] if len(data) >= 30 else data
    lows = [d['low'] for d in tail]
    return round(float(min(lows)), 1)


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

# ─── 🐂 美國四巫日（Quadruple Witching）自動計算 ───────
def get_quadruple_witching(year, month):
    """回傳該月第3個星期五的日期 (datetime)，僅對 3/6/9/12 月有效"""
    if month not in (3, 6, 9, 12):
        return None
    first_day = datetime(year, month, 1)
    # weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    days_ahead = 4 - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_fri = first_day + timedelta(days=days_ahead)
    third_fri = first_fri + timedelta(weeks=2)  # 第1 + 2週 = 第3個
    return third_fri

def get_upcoming_quadruple_witching(today, cutoff):
    """未來14天內是否有四巫日"""
    results = []
    for m in (3, 6, 9, 12):
        qw = get_quadruple_witching(today.year, m)
        if qw is None:
            continue
        if today <= qw <= cutoff:
            days_to = (qw - today).days
            results.append((qw.strftime('%Y-%m-%d'), f'⚠️ 美股四巫日（結算日）波動加劇（{days_to}天後）'))
        # 如果跨年也檢查
        if m == 12 and qw < today and qw.month == 12:
            qw_next = get_quadruple_witching(today.year + 1, 3)
            if qw_next and today <= qw_next <= cutoff:
                days_to = (qw_next - today).days
                results.append((qw_next.strftime('%Y-%m-%d'), f'⚠️ 美股四巫日（結算日）波動加劇（{days_to}天後）'))
    return results

# ─── 🇺🇸 美國總經自動抓取（BLS + Fed 官方行事曆）───────
_US_EVENTS_CACHE = None
_US_EVENTS_CACHE_TIME = None

def _fetch_bls_calendar(year, month):
    """從 BLS.gov List View 抓該月的行事曆，回傳 [(date_str, 事件名稱), ...]"""
    import re
    url = f'https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm'
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        text = r.text
        events = []
        # List View 格式乾淨：每行 "Tuesday, August 04, 2026" 後面接時間 + 事件名
        # 用正則抓 "(Monday|Tuesday|...), (Month) (DD), (YYYY)"
        date_pattern = re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (\w+) (\d{1,2}), (\d{4})')
        month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                    'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
        lines = text.split('\n')
        current_date_str = None
        for i, line in enumerate(lines):
            line_s = line.strip()
            # 檢查日期行
            m = date_pattern.search(line_s)
            if m:
                month_name = m.group(2)
                day = int(m.group(3))
                yr = int(m.group(4))
                mm = month_map.get(month_name)
                if mm:
                    current_date_str = f'{yr}-{mm:02d}-{day:02d}'
                continue
            # 檢查事件名行（非空、不含HTML標籤）
            if current_date_str and line_s and '<' not in line_s and '>' not in line_s:
                keywords = ['Employment Situation', 'Consumer Price Index', 'Producer Price Index',
                           'Job Openings', 'Labor Turnover', 'Real Earnings', 'Import and Export',
                           'Employment Cost Index', 'Productivity and Costs',
                           'State Employment', 'Metropolitan Area', 'Usual Weekly Earnings',
                           'Access to and Use of Leave', 'Employment Projections',
                           'Worker Displacement', 'County Employment',
                           'Current Employment Statistics', 'Summer Youth']
                if any(k.lower() in line_s.lower() for k in keywords):
                    events.append((current_date_str, line_s))
                    current_date_str = None  # 同一日期一個事件
        return events
    except:
        return []

def _fetch_fomc_calendar():
    """從 Fed 官網抓 FOMC 會議日期"""
    import re
    url = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return []
        html = r.text
        events = []
        # 找 "2026 FOMC Meetings"</div> 後的 panel-body
        month_pattern = re.compile(r'fomc-meeting__month[^>]*><strong>(\w+)</strong>')
        date_pattern = re.compile(r'fomc-meeting__date[^>]*>(\d{1,2})[^\d]*(\d{1,2})?')
        # 從 2026 年 section 開始找
        idx = html.find('id="42828"')  # 2026 FOMC 的 id
        if idx < 0:
            idx = html.find('2026 FOMC')
        if idx < 0:
            return events
        section = html[idx:idx+12000]  # 2026 全年約 12000 字元
        lines = section.split('\n')
        current_month = None
        month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                    'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
        month_name = {'January':'1月','February':'2月','March':'3月','April':'4月','May':'5月','June':'6月',
                     'July':'7月','August':'8月','September':'9月','October':'10月','November':'11月','December':'12月'}
        for line in lines:
            line_s = line.strip()
            # 匹配月分行
            mm = month_pattern.search(line_s)
            if mm:
                current_month = mm.group(1)
                continue
            # 匹配日期行
            dd = date_pattern.search(line_s)
            if dd and current_month:
                m = month_map.get(current_month)
                if m:
                    end_day = int(dd.group(2)) if dd.group(2) else int(dd.group(1))
                    start_day = int(dd.group(1))
                    date_obj = datetime(2026, m, end_day)
                    events.append((date_obj.strftime('%Y-%m-%d'), f'🔥🔥🔥 FOMC {month_name.get(current_month,current_month)}利率決議'))
                    if start_day != end_day:
                        date_obj_start = datetime(2026, m, start_day)
                        events.append((date_obj_start.strftime('%Y-%m-%d'), f'🔥🔥🔥 FOMC {month_name.get(current_month,current_month)}會議首日'))
                current_month = None
        return events
    except Exception as _fe:
        print(f'  ⚠️ FOMC 行事曆抓取失敗: {_fe}')
        return []

def _generate_us_rules_events(today, cutoff):
    """用已知排程規則推算美國總經事件日期"""
    results = []
    def nth_wd(y, m, wd, nth):
        d = datetime(y, m, 1)
        da = wd - d.weekday()
        if da < 0:
            da += 7
        return d + timedelta(days=da) + timedelta(weeks=nth-1)
    
    month_names = {1:'1月',2:'2月',3:'3月',4:'4月',5:'5月',6:'6月',
                   7:'7月',8:'8月',9:'9月',10:'10月',11:'11月',12:'12月'}
    
    for i in range(3):
        m = today.month + i
        y = today.year
        if m > 12:
            m -= 12
            y += 1
        
        # 非農 NFP: 第1個星期五
        nfp = nth_wd(y, m, 4, 1)
        if today <= nfp <= cutoff:
            results.append((nfp.strftime('%Y-%m-%d'), f'US {month_names[m]}非農就業(NFP)'))
        
        # CPI: 第2個星期三
        cpi = nth_wd(y, m, 2, 2)
        if today <= cpi <= cutoff:
            results.append((cpi.strftime('%Y-%m-%d'), f'US {month_names[m]}CPI'))
        
        # PPI: 第2個星期四
        ppi = nth_wd(y, m, 3, 2)
        if today <= ppi <= cutoff:
            results.append((ppi.strftime('%Y-%m-%d'), f'US {month_names[m]}PPI'))
        
        # ISM 製造業 PMI: 第1個工作日
        fd = datetime(y, m, 1)
        ism_m = fd
        while ism_m.weekday() >= 5:
            ism_m += timedelta(days=1)
        if today <= ism_m <= cutoff:
            results.append((ism_m.strftime('%Y-%m-%d'), f'US {month_names[m]}ISM製造業PMI'))
        
        # ISM 服務業 PMI: 通常第3個工作日（製造業後第2個工作日）
        ism_s = ism_m + timedelta(days=1)
        while ism_s.weekday() >= 5:
            ism_s += timedelta(days=1)
        if today <= ism_s <= cutoff:
            results.append((ism_s.strftime('%Y-%m-%d'), f'US {month_names[m]}ISM服務業PMI'))
        
        # JOLTS: 通常在NFP之後的週二
        jolts = nfp + timedelta(days=4) if nfp.weekday() <= 2 else nfp + timedelta(days=11)
        if today <= jolts <= cutoff:
            results.append((jolts.strftime('%Y-%m-%d'), f'US {month_names[m]}JOLTS職位空缺'))
        
        # GDP: 1月/4月/7月/10月的最後一週
        if m in (1, 4, 7, 10):
            gdp = datetime(y, m, 28)
            while gdp.weekday() != 3:  # 星期四
                gdp += timedelta(days=1)
            gdp_label = {1:'Q4',4:'Q1',7:'Q2',10:'Q3'}
            if today <= gdp <= cutoff:
                results.append((gdp.strftime('%Y-%m-%d'), f'US {gdp_label[m]} GDP初值'))
    
    return results

def get_us_events():
    """合併四巫日 + 規則推算 + FOMC 行事曆，輸出 [(date_str, event_name), ...]"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = today + timedelta(days=14)
    results = []
    
    # 1. 四巫日
    qw_list = get_upcoming_quadruple_witching(today, cutoff)
    results.extend(qw_list)
    
    # 2. 用規則推算美國總經事件
    rules_events = _generate_us_rules_events(today, cutoff)
    results.extend(rules_events)
    
    # 3. FOMC（從 Fed 官網即時抓取）
    fomc_events = _fetch_fomc_calendar()
    for date_str, name in fomc_events:
        ev_dt = datetime.strptime(date_str, '%Y-%m-%d')
        if today <= ev_dt <= cutoff:
            results.append((date_str, name))
    
    # 去重、排序
    seen = set()
    deduped = []
    for date_str, name in sorted(results, key=lambda x: x[0]):
        key = (date_str, name)
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped

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

def gen_html(snaps, tech_data, trust_rates, alerts, events, tone, news_html='', potential_stocks=None, us_events=None):
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    now_hm = now.strftime('%H:%M')
    
    # ── SOX 指數（從 global_weather 抓） ──
    try:
        from global_weather import get_us_indexes
        us = get_us_indexes()
    except:
        us = {}
    
    # ── 台指期指數（直接用 yfinance 抓加權指數，TX00.TW 常離線）──
    try:
        import yfinance as yf
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            twii = yf.Ticker('^TWII')
            twii_df = twii.history(period='5d')
        if twii_df is not None and len(twii_df) >= 2:
            closes = twii_df['Close'].values
            fut = {
                'close': round(float(closes[-1]), 2),
                'change': round((closes[-1] / closes[-2] - 1) * 100, 2),
                'source': '加權指數',
            }
        else:
            fut = None
    except:
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
    def _price_cell(px, s, prev_close=None):
        """產出股價+漲跌幅的上下兩行HTML
        s 為 snaps[sid] (Shioaji即時) 或 None
        prev_close 為昨天收盤價 (tech_data 備援)
        """
        pxt = f'{px}' if px else '—'
        chg, chg_pct = None, None
        if s and s.get('change') is not None:
            chg = s['change']
            chg_pct = s.get('change_pct', 0)
        elif prev_close and px and prev_close > 0:
            chg = px - prev_close
            chg_pct = (chg / prev_close) * 100
        
        if chg is not None:
            if chg > 0:
                icon, cls = '▲', 'up'
            elif chg < 0:
                icon, cls = '▼', 'down'
            else:
                icon, cls = '▸', ''
            chg_s = f'<span class="{cls}">{icon} {abs(chg):.2f} ({chg_pct:+.2f}%)</span>'
            return (
                f'<div style="font-weight:bold;font-size:1.05em;line-height:1.2">{pxt}</div>'
                f'<div style="font-size:0.85em;line-height:1.2">{chg_s}</div>'
            )
        else:
            return f'<div style="font-weight:bold;font-size:1.05em">{pxt}</div>'

    def fmt_stock_row(sid, sname, tech):
        t = tech.get(sid)
        if not t:
            return ''
        
        px = t.get('price', 0)
        k, d = t['k'], t['d']
        gap = t['gap']
        rsi_val = t['rsi']
        vol_note = t.get('vol_note', '—')
        
        # KD: TA-Lib STOCH(14,1,3) — K値/D値 線型顯示
        kp = '14,1,3'
        if gap > 5:
            kd_s = f'🟢K↑{k:.1f} D↑{d:.1f} (金叉,gap={gap:.1f})'
        elif gap > 0:
            kd_s = f'🟡K{k:.1f} D{d:.1f} (逼近金叉,gap={gap:.1f})'
        elif gap > -5:
            kd_s = f'🟡K{k:.1f} D{d:.1f} (逼近死叉,gap={gap:.1f})'
        else:
            kd_s = f'🔴K↓{k:.1f} D↓{d:.1f} (死叉,gap={gap:.1f})'
        
        # MACD: TA-Lib MACD(12,26,9) — 柱狀體方向描述
        macd_v = t.get('macd')
        macd_hist = t.get('macd_hist')
        macd_hist_prev = t.get('macd_hist_prev')
        if macd_v is not None and macd_hist is not None:
            if macd_hist > 0:
                if macd_hist_prev is not None and macd_hist > macd_hist_prev:
                    macd_s = f'🟢MACD {macd_v:.2f} 紅柱增長(多頭攻擊)'
                else:
                    macd_s = f'🟢MACD {macd_v:.2f} 紅柱縮短(動能減弱)'
            else:
                if macd_hist_prev is not None and macd_hist < macd_hist_prev:
                    macd_s = f'🔴MACD {macd_v:.2f} 綠柱增長(空頭攻擊)'
                else:
                    macd_s = f'🔴MACD {macd_v:.2f} 綠柱縮短(止跌訊號)'
        else:
            macd_s = '—'
        
        hints = []
        if gap > 5: hints.append('🔥金叉中')
        elif gap < -5: hints.append('💀死叉中')
        if rsi_val > 70: hints.append('過熱')
        elif rsi_val < 30: hints.append('超賣')
        hint_s = ' | '.join(hints) if hints else '—'
        
        if gap > 5 and rsi_val < 60:
            strategy = '🟢 K金叉 可持股'
        elif gap > 0 and rsi_val < 50:
            strategy = '🟡 近金叉 觀望期待'
        elif gap < -5 and rsi_val > 40:
            strategy = '🔴 死叉中 避開'
        elif rsi_val > 70:
            strategy = '🔴 RSI過熱 注意回檔'
        elif rsi_val < 30 and gap > 0:
            strategy = '🟢 RSI超賣+金叉 留意買點'
        else:
            strategy = '➖ 觀望'
        
        low_30d = t.get('low_30d')
        if low_30d:
            dist_to_low = round(((px / low_30d) - 1) * 100, 1)
            if dist_to_low < 5:
                low_s = f'<span style="color:var(--red-alert)">{low_30d} ⚠️</span>'
            else:
                low_s = f'{low_30d}'
        else:
            low_s = '—'
        
        # 股票欄：上名稱下代號
        s_cell = f'<div style="line-height:1.2"><b>{sname}</b></div><div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">{sid}</div>'
        # 股價欄：上股價下漲跌（Shioaji 離線時用技術資料前一日收盤價）
        _prev_c = t.get('prev_close')
        p_cell = _price_cell(px, snaps.get(sid), prev_close=_prev_c)
        
        return (
            f'<tr>'
            f'<td>{s_cell}</td>'
            f'<td>{p_cell}</td>'
            f'<td>{low_s}</td>'
            f'<td>{kd_s}</td>'
            f'<td>{rsi_val}</td>'
            f'<td>{macd_s}</td>'
            f'<td>{vol_note}</td>'
            f'<td>{hint_s}</td>'
            f'<td>{strategy}</td></tr>\n'
        )

    price_rows = ''
    for sid, sname in CORE_19:
        price_rows += fmt_stock_row(sid, sname, tech_data)
    if not price_rows:
        price_rows = '<tr><td colspan="9" style="text-align:center;color:#666;">⏳ 資料讀取中</td></tr>'
    
    # ── 潛力股候選（全市場非持股中被投信大買的）──
    trust_update_time = '—'
    now_hm = now.strftime('%H:%M')
    trust_scan_path = os.path.join(OUTPUT_DIR, 'trust_scan_latest.json')
    if potential_stocks is None and os.path.exists(trust_scan_path):
        try:
            with open(trust_scan_path, 'r', encoding='utf-8') as f:
                trust_scan = json.load(f)
            trust_update_time = trust_scan.get('update_time', '—')
            # 全部候選：持股+非持股，只要有投信連買>=3天、總額>50萬
            candidates = [h for h in trust_scan.get('trust_top40', []) 
                         if h['days'] >= 3 and h['total_trust'] >= 500000]
            # 核心持股放前面，非持股放後面，最多20檔
            watch = [c for c in candidates if c.get('is_watch', False)]
            non_watch = [c for c in candidates if not c.get('is_watch', False)]
            potential_stocks = (watch[:10] + non_watch[:10])[:20]
        except Exception as _pe:
            print(f'  ⚠️ 潛力股載入失敗: {_pe}')
            potential_stocks = []
    elif potential_stocks is None:
        potential_stocks = []
    
    # ── 台美聯動牆（即時從 global_weather.check_linkage() 抓取）──
    # ⚠️ 之前寫死 top_us 已修改為動態抓取 (2026-07-21)
    linkage_rows = ''
    if HAVE_WEATHER:
        try:
            from global_weather import LINKAGE_MAP as _LM, get_us_stock_change as _gusc
            # 各主題欄位專用聯動美股列表
            _LINKAGE_WATCH = {
                '半導體': ['TSM','ASML','AVGO','INTC','NVDA','AMD','ARM','QCOM','MRVL'],
                '記憶體': ['MU','WDC','STX'],
                '設備': ['AMAT','LRCX','KLAC'],
                '封測/通路': ['ASX','AMKR'],
                '車用/類比': ['TXN','STM','ON','IFNNY','NXP'],
            }
            _seen_stocks = set()
            for _topic, _syms in _LINKAGE_WATCH.items():
                _topic_rows = ''
                for _sym in _syms:
                    _chg, _close = _gusc(_sym)
                    if _chg is None:
                        continue
                    # 取台股對應
                    _info = _LM.get(_sym.upper(), {})
                    _tw_names_str = ', '.join(_info.get('tw_names', {}).values()) if _info else ''
                    # 防重複
                    if _tw_names_str in _seen_stocks:
                        continue
                    _seen_stocks.add(_tw_names_str)
                    _abs = abs(_chg)
                    if _abs >= 4:
                        _badge = '🔴🔴'
                        _bc = 'badge-red'
                    elif _abs >= 2:
                        _badge = '🔴'
                        _bc = 'badge-red'
                    elif _chg > 0:
                        _badge = '🟢'
                        _bc = 'badge-blue'
                    else:
                        _badge = '🔻'
                        _bc = 'badge-orange'
                    _chg_str = f'{_chg:+.2f}%'
                    _tw_str = f' → {_tw_names_str}' if _tw_names_str else ''
                    _topic_rows += (
                        f'<div class="link-row">'
                        f'<span class="badge {_bc}">{_badge}</span> '
                        f'<b>{_sym} {_info.get("name","") if _info else ""}</b> {_chg_str}{_tw_str}'
                        f'</div>\n'
                    )
                    if _topic_rows.count('link-row') >= 4:
                        break
                if _topic_rows:
                    linkage_rows += (
                        f'<div style="margin-bottom:12px">'
                        f'<div style="color:var(--primary-gold);font-size:18px;font-weight:bold;margin-bottom:6px">📌 {_topic}</div>'
                        f'{_topic_rows}'
                        f'</div>'
                    )
            if not linkage_rows:
                linkage_rows = '<div class="link-row">⚠️ 無法取得即時聯動數據</div>'
        except Exception as _le:
            linkage_rows = f'<div class="link-row">⚠️ 聯動牆讀取失敗: {_le}</div>'
    else:
        linkage_rows = '<div class="link-row">⚠️ 聯動模組未啟用</div>'
    
    # ── 未來14天事件 ──
    today_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_dt = today_dt + timedelta(days=14)
    
    # A) 自動抓取的美國事件（四巫日 + BLS總經 + FOMC）
    us_events = get_us_events()
    us_event_rows = ''
    for date_str, ev in us_events:
        us_event_rows += (
            f'<div class="event-row">'
            f'<span>{fmt_date(date_str)}</span>'
            f'<span>{ev}</span>'
            f'</div>\n'
        )
    
    # B) 已知固定事件
    event_rows = ''
    for date_str, ev in KNOWN_EVENTS:
        ev_dt = datetime.strptime(date_str, '%Y-%m-%d')
        if ev_dt >= today_dt and ev_dt <= cutoff_dt:
            event_rows += (
                f'<div class="event-row">'
                f'<span>{fmt_date(date_str)}</span>'
                f'<span>{ev}</span>'
                f'</div>\n'
            )
    if not event_rows:
        event_rows = '<div class="event-row"><span>—</span></div>'
    

    # ── 富邦爬蟲：即時抓取主力/投信買賣超張數 ──
    fubon_force_data = {}   # code -> net (張)
    fubon_trust_data = {}   # code -> net (張)
    try:
        # 主力買超1日 (overlap 較多) + 2日 (備用)
        _ff = fubon_crawler(url='https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_0.djhtm', top=20)
        for r in _ff:
            fubon_force_data[r['code']] = r['net']
        _ff2 = fubon_crawler(url='https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm', top=20)
        for r in _ff2:
            if r['code'] not in fubon_force_data:
                fubon_force_data[r['code']] = r['net']
        _ft = fetch_trust_top_1d(top=20)
        for r in _ft:
            fubon_trust_data[r['code']] = r['net']
    except Exception as _fe:
        print(f'⚠️ 富邦爬蟲失敗: {_fe}')

    # ── 潛力股候選 HTML 行（含富邦買賣超 + 完整 KD/RSI/量能）──
    potential_rows = ''
    for p in potential_stocks:
        fn_color = 'var(--green-go);font-weight:bold;' if p['total_foreign'] < 0 else 'var(--red-alert);font-weight:bold;'
        # 判斷對作還共愛
        trust_buy = p['total_trust'] > 0
        fn_buy = p['total_foreign'] > 0
        if trust_buy and fn_buy:
            flag = '🟢共愛'
            flag_color = 'var(--green-go)'
        elif trust_buy and not fn_buy:
            flag = '🔴對作'
            flag_color = 'var(--primary-gold)'
        else:
            flag = '➖'
            flag_color = '#666'
        
        sid = p['sid']
        t = tech_data.get(sid)
        if t:
            k, d = t['k'], t['d']
            gap = t['gap']
            # KD: TA-Lib STOCH(14,1,3)
            if gap > 5:
                kd_s = f'🟢K↑{k:.1f} D↑{d:.1f} (金叉,gap={gap:.1f})'
            elif gap > 0:
                kd_s = f'🟡K{k:.1f} D{d:.1f} (逼近金叉,gap={gap:.1f})'
            elif gap > -5:
                kd_s = f'🟡K{k:.1f} D{d:.1f} (逼近死叉,gap={gap:.1f})'
            else:
                kd_s = f'🔴K↓{k:.1f} D↓{d:.1f} (死叉,gap={gap:.1f})'
            rsi_val = t['rsi']
            vol_note = t.get('vol_note', '—')
            # MACD: TA-Lib MACD(12,26,9) 柱狀體方向描述
            macd_v = t.get('macd')
            macd_hist = t.get('macd_hist')
            macd_hist_prev = t.get('macd_hist_prev')
            if macd_v is not None and macd_hist is not None:
                if macd_hist > 0:
                    if macd_hist_prev is not None and macd_hist > macd_hist_prev:
                        macd_s = f'🟢MACD {macd_v:.2f} 紅柱增長(多頭攻擊)'
                    else:
                        macd_s = f'🟢MACD {macd_v:.2f} 紅柱縮短(動能減弱)'
                else:
                    if macd_hist_prev is not None and macd_hist < macd_hist_prev:
                        macd_s = f'🔴MACD {macd_v:.2f} 綠柱增長(空頭攻擊)'
                    else:
                        macd_s = f'🔴MACD {macd_v:.2f} 綠柱縮短(止跌訊號)'
            else:
                macd_s = '—'
        else:
            kd_s = '—'
            rsi_val = '—'
            vol_note = '—'
            macd_s = '—'
        # 潛力股的30日低
        _p_low = _get_30d_low(sid)
        _p_low_s = f'{_p_low}' if _p_low else '—'
        _p_price = t['price'] if t else p.get('close',0) or 0
        # 潛力股欄位：上名稱下代號
        pot_s_cell = f'<div style="line-height:1.2"><b>{p["name"]}</b></div><div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">{sid}</div>'
        # 潛力股股價+漲跌
        _p_prev = t.get('prev_close') if t else None
        pot_p_cell = _price_cell(round(_p_price,2) if _p_price else _p_price, snaps.get(sid), prev_close=_p_prev)
        # 富邦買賣超張數
        fb_force = fubon_force_data.get(sid, None)
        fb_trust = fubon_trust_data.get(sid, None)
        fb_force_s = f'<span style="color:var(--red-alert);font-weight:bold;">{fb_force:+,}</span>' if fb_force is not None else '<span style="color:#666;">—</span>'
        fb_trust_s = f'<span style="color:var(--red-alert);font-weight:bold;">{fb_trust:+,}</span>' if fb_trust is not None else '<span style="color:#666;">—</span>'
        potential_rows += (
            f'<tr><td>{pot_s_cell}</td>'
            f'<td>{pot_p_cell}</td>'
            f'<td>{fb_force_s}</td>'
            f'<td>{fb_trust_s}</td>'
            f'<td>{_p_low_s}</td>'
            f'<td>{kd_s}</td>'
            f'<td>{rsi_val}</td>'
            f'<td>{macd_s}</td>'
            f'<td>{vol_note}</td>'
            f'<td style="color:{flag_color};font-weight:bold;">{flag}</td></tr>\n'
        )
    if not potential_rows:
        potential_rows = '<tr><td colspan="10" style="text-align:center;color:#666;">盤後16:30更新全市場掃描</td></tr>'

    # ═══════════════════════════════════════════
    #  🏗️ 最終 HTML
    # ═══════════════════════════════════════════
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>🦞 小龍蝦早報 — 行動總經操盤雷達</title>
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
        <h1>🐛 早報 — 全球股市天氣預報</h1>
        <p>🦞 小龍蝦早報 | {today} {now_hm} | SOX+台指期 | 30分K KD 3年回測最佳參數</p>
    </div>

    <!-- 費半 SOX（唯一指數）-->
    <!-- SOX + 台指期 -->
    <div class="card info">
        <div class="card-title">🇺🇸 費城半導體指數 (SOX) + 🇹🇼 台指期</div>
        <div class="sox-box">
            <div class="sox-name">費城半導體指數 · 台股風向球</div>
            <div class="sox-val">{sox_close}</div>
            <div class="sox-chg">{sox_icon} {sox_chg} {sox_level}</div>
        </div>
        <div style="background: #2a2a2a; padding: 12px; border-radius: 6px; text-align: center; margin-top: 10px; border: 1.5px solid #1e90ff;">
            <div style="font-size: 18px; color: #ccc;">台指期指數</div>
            <div style="font-size: 24px; font-weight: bold; margin: 6px 0; color: #fff;">{fut_str if fut is not None and fut else '台指期 — 離線'}</div>
        </div>
        <div class="tone-bar">
            💡 開盤基調：{tone}
        </div>
    </div>

    <!-- 第1層：核心持股（含19檔全體）-->
    <div class="card">
        <div class="card-title">🔒 核心持股（11檔）技術監控</div>
        <table>
            <thead>
                <tr>
                    <th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>RSI</th><th>MACD</th><th>量能</th><th>提示</th><th>策略</th>
                </tr>
            </thead>
            <tbody>{price_rows}</tbody>
        </table>
    </div>

    <!-- 未來14天關鍵事件（台股固定 + 美國自動抓取）-->
    <div class="card alert">
        <div class="card-title">📅 未來 14 天台股進程與作帳節奏</div>
        {event_rows}
    </div>

    <!-- 美國關鍵事件（自動抓取 BLS + Fed）-->
    <div class="card info">
        <div class="card-title">🇺🇸 未來 14 天美股/總經關鍵事件</div>
        {us_event_rows if us_event_rows else '<div class="event-row"><span>暫無高重要性事件</span></div>'}
    </div>

    <!-- 潛力股候選（全市場投信+法人掃描 + 富邦主力/投信買賣超張數）-->
    <div class="card alert">
        <div class="card-title">
            🎯 潛力股候選
            · 更新: {trust_update_time}
        </div>
        <table>
            <thead>
                <tr>
                    <th>股票</th><th>股價</th>
                    <th>富邦主力<br>買賣超(張)</th>
                    <th>富邦投信<br>買賣超(張)</th>
                    <th>30日低</th>
                    <th>KD</th>
                    <th>RSI</th>
                    <th>MACD</th>
                    <th>量能</th>
                    <th>備註</th>
                </tr>
            </thead>
            <tbody>{potential_rows}</tbody>
        </table>
    </div>

    <!-- 台美產業聯動警報 -->
    <div class="card">
        <div class="card-title">🔗 台美全市場產業強聯動牆</div>
        {linkage_rows}
    </div>

    <!-- 新聞區塊：從 output/news_crawled.json 讀取（爬蟲，0 token） -->
    {news_html if news_html else ''}

    <div class="footer">
        小龍蝦自動產出 | 08:30 早報 · 09:00~13:35 監控 · 16:30 更新
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
        subprocess.run([git_path, 'commit', '-m', f'🦞 早報更新 {now}'],
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
    print(f'  🦞 網頁早報產出 | {now.strftime("%Y-%m-%d %H:%M")}')
    print(f'  執行模式: {"模擬" if not HAVE_SJ else "標準"} | 18px 全頁')
    print('=' * 60)
    
    # 1. Shioaji 快照
    print('\n📡 取得即時快照...')
    snaps, tone = get_shioaji_snapshots()
    print(f'   ✅ {len(snaps)} 檔快照就緒')
    
    # 2. 技術指標（含核心持股 + 潛力股）
    print('\n📊 計算技術指標 (KD/RSI/支撐)...')
    # 先讀潛力股，一併算 KD
    trust_scan_path = os.path.join(OUTPUT_DIR, 'trust_scan_latest.json')
    potential_ids = []
    if os.path.exists(trust_scan_path):
        try:
            with open(trust_scan_path, 'r', encoding='utf-8') as f:
                ts = json.load(f)
            # 持股+非持股都算KD
            candidates = [h for h in ts.get('trust_top40', [])
                         if h['days'] >= 3 and h['total_trust'] >= 500000]
            potential_ids = [h['sid'] for h in candidates[:20] if h['sid'] not in CORE_IDS]
        except:
            pass
    all_ids = list(dict.fromkeys(CORE_IDS + potential_ids))
    tech_data = get_tech_batch(all_ids)
    ok_count = sum(1 for v in tech_data.values() if v)
    print(f'   ✅ {ok_count}/{len(all_ids)} 檔技術指標就緒（含 {len(potential_ids)} 檔潛力股）')
    
    # 3. 投信滲透率
    print('\n🏦 計算股本滲透率...')
    trust_rates = get_trust_penetration()
    active = sum(1 for v in trust_rates.values() if isinstance(v.get('p_day', 0), (int, float)) and v.get('p_day', 0) > 0)
    print(f'   ✅ {active} 檔有投信買超記錄')
    
    # 4. 組裝 HTML
    print('\n🏗️ 組裝 HTML...')
    alerts = get_linkage_alerts()
    events = get_events()
    # 4a. 新聞從 output/news_headlines.json 讀取（鉅亨網 API，0 token）
    news_html = ''
    news_path = os.path.join(OUTPUT_DIR, 'news_headlines.json')
    if os.path.exists(news_path):
        try:
            with open(news_path, 'r', encoding='utf-8') as f:
                nd = json.load(f)
            # 用 morning_news.generate_html() 直接產HTML
            sys.path.insert(0, os.path.join(BASE_DIR, 'src', 'sj_trading'))
            from morning_news import generate_html as gen_news_html
            news_html = gen_news_html(nd)
        except Exception as _ne:
            print(f'  ⚠️ 新聞讀取失敗: {_ne}')
    
    html = gen_html(snaps, tech_data, trust_rates, alerts, events, tone, news_html, potential_stocks=None)
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
    
    # 8. Git Push — 跳過（本機檢視）
    print('\n📤 Git Push — 跳過（本機檢視模式）')
    
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
<tr><td><b>08:30</b> ???</td><td>早報產出 + Git Push</td><td>daily_web_report.py</td></tr>
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
<tr><td>今日重大事件</td><td>除息/法說/結算</td><td>08:35 1次</td><td>隨早報</td></tr>
<tr><td>費半暴動</td><td>隔夜 &gt;±3%</td><td>早報1次</td><td>08:30</td></tr>
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
<h2>早報版型規範</h2>
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
<tr><td>web/index.html</td><td>早報 (GitHub Pages)</td></tr>
<tr><td>web/architecture.html</td><td>架構說明</td></tr>
<tr><td>database/代號_3y.csv</td><td>19檔+額外日K</td></tr>
<tr><td>output/SITC_Accumulation.csv</td><td>投信買賣超累積</td></tr>
<tr><td>src/sj_trading/daily_web_report.py</td><td>早報產生器</td></tr>
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
