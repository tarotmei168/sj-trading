"""
小龍蝦 精簡回測引擎 v2（含手續費）
────────────────────────────
只抓 TWSE 日K線 → 算KD → 含手續費回測
跳過三大法人（太慢，盤後再看）
"""
import sys, os, json, time, urllib.request
from datetime import date, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CACHE = Path(__file__).resolve().parents[2] / 'cache'
CACHE.mkdir(parents=True, exist_ok=True)

# 受測股票 — 你持有的 + 想測的
STOCKS = [
    ('2337','旺宏',7),
    ('2436','偉詮電',3),
    ('5351','鈺創',9),
    ('8150','南茂',3),
    ('3711','日月光',3),
    ('3673','TPKKY',3),
    ('4958','臻鼎KY',3),
    ('3042','晶技',3),
    ('2330','台積電',7),
    ('2454','聯發科',5),
    ('2317','鴻海',5),
]
START, END = date(2024,1,1), date(2026,7,3)

# 交易成本
BUY_FEE = 0.001425 * 0.6  # 買進手續費(6折)
SELL_FEE = 0.001425 * 0.6
TAX = 0.003  # 證交稅

def roc_to_ad(y): return y + 1911

def fetch_month(sid, y, m):
    """抓一個月的日K線"""
    ds = f'{y}{m:02d}01'
    cp = CACHE / f'STOCK_DAY_{sid}_{ds}.json'
    if cp.exists():
        with open(cp, 'r', encoding='utf-8') as f:
            return json.load(f)
    url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={ds}&stockNo={sid}'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        raw = urllib.request.urlopen(req, timeout=10).read()
        d = json.loads(raw)
        if d.get('stat') == 'OK':
            with open(cp, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False)
            return d
    except:
        pass
    return None

def load_data(sid):
    """載入完整日K線，回傳 (dates, closes, highs, lows)"""
    all_data = {}
    d = date(START.year, START.month, 1)
    while d <= END:
        raw = fetch_month(sid, d.year, d.month)
        if raw:
            for row in raw.get('data', []):
                y,m2,dd = row[0].split('/')
                ds = f'{roc_to_ad(int(y))}-{int(m2):02d}-{int(dd):02d}'
                def n(s):
                    try: return float(s.replace(',',''))
                    except: return 0.0
                o=n(row[3]); h=n(row[4]); l=n(row[5]); c=n(row[6])
                if o==0 or c==0: continue
                all_data[ds] = {'open':o,'high':h,'low':l,'close':c,'volume':n(row[1])}
        if d.month == 12:
            d = date(d.year+1, 1, 1)
        else:
            d = date(d.year, d.month+1, 1)
        time.sleep(0.1)
    
    if not all_data:
        return [], [], [], []
    sd = sorted(all_data.keys())
    sp = [all_data[x] for x in sd]
    return sd, [x['close'] for x in sp], [x['high'] for x in sp], [x['low'] for x in sp]

def compute_kd(closes, highs, lows, kp):
    """標準 KD 計算"""
    n = len(closes)
    k = [50.0]*n; d = [50.0]*n
    for i in range(kp, n):
        lo = min(lows[i-kp+1:i+1]); hi = max(highs[i-kp+1:i+1])
        rsv = 50.0 if hi==lo else (closes[i]-lo)/(hi-lo)*100
        k[i] = (2/3)*k[i-1] + (1/3)*rsv
        d[i] = (2/3)*d[i-1] + (1/3)*k[i]
    return k, d

def run(dates, closes, k, d, kp, mode='threshold', sell_k=70, sell_hold=5):
    """
    mode='threshold': K≤38買 / K≥sell_k或持有sell_hold天賣
    mode='simple': 金叉買/死叉賣
    回傳 trade list，已含手續費
    """
    trades = []; pos = 0; buy_price = 0; buy_date = ''; hold = 0
    for i in range(kp, len(dates)):
        golden = k[i-1] <= d[i-1] and k[i] > d[i]
        death = k[i-1] >= d[i-1] and k[i] < d[i]
        if pos == 0:
            if golden:
                if mode == 'threshold' and k[i] <= 38:
                    pos = 1; buy_price = closes[i]; buy_date = dates[i]; hold = 0
                elif mode == 'simple':
                    pos = 1; buy_price = closes[i]; buy_date = dates[i]; hold = 0
        else:
            hold += 1; sell = False
            if mode == 'threshold':
                if (k[i] >= sell_k and death) or hold > sell_hold:
                    sell = True
            else:
                if death:
                    sell = True
            if sell:
                bc = buy_price * 1000; sc = closes[i] * 1000
                fee_b = bc * BUY_FEE
                fee_s = sc * SELL_FEE
                tax = sc * TAX
                total_cost = bc + fee_b + fee_s + tax
                net_pnl = (sc - total_cost) / total_cost * 100
                gross = (closes[i] - buy_price) / buy_price * 100
                trades.append({'buy_date':buy_date,'sell_date':dates[i],
                    'buy_price':round(buy_price,2),'sell_price':round(closes[i],2),
                    'pnl_net':round(net_pnl,2),'pnl_gross':round(gross,2),
                    'hold_days':hold,'entry_k':round(k[i-1],1),'exit_k':round(k[i],1)})
                pos = 0
    if pos:
        trades.append({'buy_date':buy_date,'sell_date':'持有中','buy_price':round(buy_price,2),
            'sell_price':0,'pnl_net':0,'pnl_gross':0,'hold_days':hold,
            'entry_k':round(k[len(closes)-1],1),'exit_k':'-'})
    return trades

def stats(trades, name, label):
    closed = [t for t in trades if t['sell_date']!='持有中']
    n = len(closed)
    if n==0:
        return {'name':name,'label':label,'n':0,'win':0,'loss':0,'wr':0,
                'total_pnl':0,'avg':0,'max_loss':0,'max_cl':0,'pf':0}
    total = sum(t['pnl_net'] for t in closed)
    wins = sum(1 for t in closed if t['pnl_net']>0)
    losses = n - wins
    wr = wins/n*100
    gp = sum(t['pnl_net'] for t in closed if t['pnl_net']>0)
    gl = abs(sum(t['pnl_net'] for t in closed if t['pnl_net']<=0))
    pf = gp/gl if gl>0 else (float('inf') if gp>0 else 0)
    max_cl = 0; cur_cl = 0; max_l = 0
    for t in closed:
        if t['pnl_net']<0: cur_cl+=1; max_cl=max(max_cl,cur_cl); max_l=min(max_l,t['pnl_net'])
        else: cur_cl=0
    return {'name':name,'label':label,'n':n,'win':wins,'loss':losses,
            'wr':round(wr,1),'total_pnl':round(total,2),'avg':round(total/n,2),
            'max_loss':round(max_l,2),'max_cl':max_cl,'pf':round(pf,2) if pf!=float('inf') else 'inf'}

print('='*65)
print('  小龍蝦 精簡回測引擎 v2（含手續費6折+證交稅）')
print(f'  區間: {START} ~ {END}')
print(f'  股票數: {len(STOCKS)} 支')
print('='*65)

results = []
for sid, name, kp in STOCKS:
    print(f'\n{"─"*55}')
    print(f'  📊 {name}({sid}) K={kp}')
    print(f'{"─"*55}')
    print(f'  下載日K線...')
    dates, closes, highs, lows = load_data(sid)
    if not dates:
        print(f'  ❌ 無資料（可能為上櫃股）')
        results.append({'name':name,'sid':sid,'kp':kp,'error':'no data'})
        continue
    print(f'  {len(dates)} 個交易日  {dates[0]} ~ {dates[-1]}')
    
    k_vals, d_vals = compute_kd(closes, highs, lows, kp)
    
    for mode_label, mode, sell_k, sell_hold in [
        ('門檻(K≤38買 / K≥70或5日賣)','threshold',70,5),
        ('單純KD金叉/死叉','simple',70,0),
    ]:
        if mode == 'threshold':
            ts = run(dates, closes, k_vals, d_vals, kp, 'threshold', sell_k, sell_hold)
        else:
            ts = run(dates, closes, k_vals, d_vals, kp, 'simple', 70, 0)
        st = stats(ts, name, mode_label)
        results.append(st)
        
        closed = [t for t in ts if t['sell_date']!='持有中']
        print(f'\n  {"="*50}')
        print(f'  {mode_label}')
        print(f'  {"="*50}')
        print(f'  交易:{st["n"]}次  勝率:{st["wr"]}%  ({st["win"]}勝/{st["loss"]}敗)')
        print(f'  總報酬(淨): {st["total_pnl"]:+.2f}%  平均:{st["avg"]:+.2f}%')
        print(f'  最大虧損:{st["max_loss"]:.2f}%  最大連虧:{st["max_cl"]}次  獲利因子:{st["pf"]}')
        if closed:
            print(f'\n  最近5筆交易:')
            print(f'  {"買入":<12} {"賣出":<12} {"買價":>8} {"賣價":>8} {"淨報酬":>8} {"持有":>4}')
            for t in closed[-5:]:
                print(f'  {t["buy_date"]:<12} {t["sell_date"]:<12} {t["buy_price"]:>8.2f} {t["sell_price"]:>8.2f} {t["pnl_net"]:>+7.2f}% {t["hold_days"]:>4d}')

# 彙總
print(f'\n{"="*65}')
print(f'  📋 彙總比較')
print(f'{"="*65}')
print(f'  {"股票":<10} {"K":<4} {"策略":<28} {"交易":>5} {"勝率":>6} {"總報酬":>8} {"最大連虧":>5}')
print(f'  {"─"*65}')
for r in results:
    if 'error' in r:
        print(f'  {r["name"]:<10} {r["kp"]:<4} ❌ {r["error"]}')
        continue
    print(f'  {r["name"]:<10} {r["kp"]:<4} {r["label"]:<28} {r["n"]:>5d} {r["wr"]:>5.1f}% {r["total_pnl"]:>+7.2f}% {r["max_cl"]:>4d}')

print(f'\n  ✅ 完成')
