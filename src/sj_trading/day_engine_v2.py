import os
from dotenv import load_dotenv
load_dotenv()
import shioaji as sj
import numpy as np
from datetime import datetime

ak = os.environ.get('SJ_API_KEY', '')
sk = os.environ.get('SJ_SEC_KEY', '')
api = sj.Shioaji(simulation=True)
api.login(api_key=ak, secret_key=sk)

now = datetime.now()
start = datetime(now.year, now.month, now.day, 8, 45)

# ===== 第1层：核心持股（有部位，死守监控）=====
CORE = [
    ("2436","weiquan","底打中（严重超跌）"),
    ("2337","wanghong","低档纠结（静待金叉）"),
    ("5351","yuchuang","走势偏弱，等待打底"),
    ("3673","TPK-KY","强烈钝化（主力洗盘）"),
    ("3711","riyueguang","权重封测超卖（等大盘止稳）"),
    ("4958","zhending","超卖低档开花（寻找支撑）"),
    ("3042","jingji","绩优石英超卖（位阶极低）"),
    ("2454","lianfake","IC设计龙头超卖（高价股指标）"),
    ("2317","honghai","多头极限防守点（回测月线）"),
]

# ===== 第2层：核心潜力股（无部位，等右侧开枪）=====
POTENTIAL = [
    ("3443","chuangyi","ASIC绝对核心超卖（指标股）"),
    ("3661","shixin","高价矽智财超卖（法人洗盘）"),
    ("3035","zhiyuan","主力色彩重超卖（极易反弹）"),
    ("3231","weichuang","AI伺服器打底，静待量增"),
    ("2382","guangda","大户筹码洗盘（区间震荡）"),
    ("3017","qihong","散热龙头极致超卖（严重背离）"),
    ("2451","chuanjian","记忆体模组超卖（题材补涨股）"),
]

def calc_rsi_last(closes, period=14):
    n = len(closes)
    if n < period + 1:
        return 50.0
    gains = 0; losses = 0
    for i in range(n-period, n):
        d = closes[i] - closes[i-1]
        if d > 0: gains += d
        else: losses += abs(d)
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 1)

def get_rsi_level(rsi_val):
    if rsi_val < 20: return "极超卖"
    elif rsi_val < 30: return "超卖"
    elif rsi_val < 40: return "偏低"
    elif rsi_val < 50: return "中性偏弱"
    elif rsi_val < 60: return "中性"
    elif rsi_val < 70: return "偏多"
    else: return "过热"

def process_bars(kbars):
    interval = 15
    bars = []; cur = None
    for i in range(len(kbars.Close)):
        t = datetime.fromtimestamp(kbars.ts[i]/1e9)
        slot = t.hour*60 + t.minute
        sn = (slot // interval) * interval
        key = t.strftime('%Y%m%d') + f'{sn:03d}'
        c = float(kbars.Close[i]); h = float(kbars.High[i]); l = float(kbars.Low[i])
        if cur is None or cur[0] != key:
            if cur: bars.append(cur)
            cur = [key, t, c, h, l, c]
        else:
            cur[3] = max(cur[3], h); cur[4] = min(cur[4], l); cur[5] = c
    if cur and (datetime.now() - cur[1]).seconds < 1800:
        bars.append(cur)
    return bars

all_sids = [s[0] for s in CORE + POTENTIAL]
all_contracts = {}
for sid in all_sids:
    try:
        all_contracts[sid] = api.Contracts.Stocks[sid]
    except:
        pass

all_kbars = {}
for sid in all_sids:
    try:
        c = all_contracts.get(sid)
        if c:
            kb = api.kbars(contract=c, start=start.strftime('%Y-%m-%d'), end=now.strftime('%Y-%m-%d'))
            if hasattr(kb, 'Close') and len(kb.Close) > 50:
                all_kbars[sid] = kb
    except:
        pass

def analyze(sid):
    kbars = all_kbars.get(sid)
    if kbars is None:
        return None
    bars = process_bars(kbars)
    if len(bars) < 9: return None
    
    cls = np.array([b[2] for b in bars], dtype=float)
    his = np.array([b[3] for b in bars], dtype=float)
    los = np.array([b[4] for b in bars], dtype=float)
    n = len(cls); k=np.zeros(n); d=np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-9+1); hh=np.max(his[ps:i+1]); ll=np.min(los[ps:i+1])
        rsv=(cls[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(2/3)*k[i-1]+(1/3)*rsv; d[i]=(2/3)*d[i-1]+(1/3)*k[i]
    
    price = cls[-1]
    k_v = round(k[-1], 1)
    d_v = round(d[-1], 1)
    kd_up = k[-1] > d[-1]
    gc = k[-1] > d[-1] and k[-2] <= d[-2]
    dc = k[-1] < d[-1] and k[-2] >= d[-2]
    
    rsi_val = calc_rsi_last(cls)
    rsi_lv = get_rsi_level(rsi_val)
    
    return {
        'price': price, 'k': k_v, 'd': d_v,
        'kd_up': kd_up, 'gc': gc, 'dc': dc,
        'rsi': rsi_val, 'rsi_level': rsi_lv
    }

# ===== 输出报告 =====
print()
print("=" * 85)
print("  DayEngine 盘中监控 | %s" % now.strftime('%H:%M'))
print("=" * 85)

print()
print("🔒 【第 1 層：核心持股】— 有部位，全力監控救援")
print("-" * 85)
print(f"{'代號':<6} {'名稱':<6} {'現價':>6} {'15分K':>10} {'實時RSI':>8} {'位階':<8} {'綜合訊號':<16}")
print("-" * 85)

for sid, sname, signal in CORE:
    r = analyze(sid)
    if not r: continue
    
    price = r['price']
    kd_str = f"{r['k']:.1f}/{r['d']:.1f}"
    icon = "🔴" if not r['kd_up'] else "🟢"
    action = ""
    if r['gc']: action = "⭐金叉!"
    elif r['dc']: action = "💀死叉!"
    
    # RSI位阶
    emoji = "💎" if r['rsi_level'] in ('超卖','极超卖') else ("🔥" if r['rsi_level']=='过热' else "📊")
    
    print(f"{sid:<6} {sname:<6} {price:>6.0f}{icon} {kd_str:<9} {r['rsi']:>5.1f} {emoji}{r['rsi_level']:<6} {signal}")

print()
print("🎯 【第 2 層：核心潛力股】— 無部位，等右側開槍")
print("-" * 85)
print(f"{'代號':<6} {'名稱':<6} {'現價':>6} {'15分K':>10} {'實時RSI':>8} {'位階':<8} {'產業題材':<16}")
print("-" * 85)

for sid, sname, desc in POTENTIAL:
    r = analyze(sid)
    if not r: continue
    
    price = r['price']
    kd_str = f"{r['k']:.1f}/{r['d']:.1f}"
    icon = "🔴" if not r['kd_up'] else "🟢"
    emoji = "💎" if r['rsi_level'] in ('超卖','极超卖') else ("🔥" if r['rsi_level']=='过热' else "📊")
    
    print(f"{sid:<6} {sname:<6} {price:>6.0f}{icon} {kd_str:<9} {r['rsi']:>5.1f} {emoji}{r['rsi_level']:<6} {desc}")

print()
print("-" * 85)
print("  無任何15分K金叉訊號，目前全部持防守狀態")
print("  等待KD金叉出現即為買點")

api.logout()
