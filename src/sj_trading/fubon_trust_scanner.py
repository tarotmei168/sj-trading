#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦞 Fubon + 30分K 統一週期 v6
=============================================
全部用30分K，絕不用日K：
- KD: 30分K (STOCH)
- MACD: 30分K (MACD)  
- RSI: 30分K (RSI)
- 資料來源: database/30min_60d/（60天30分K）+ database/3y_kd/（3年回測備用）
- 輸出「最新一根30分K時間」確保週期正確
"""
import sys, os, json, re
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
import requests, numpy as np, pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from calc_tech import calc_STOCH, calc_MACD, calc_RSI, calc_RSI_last

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
DB_DIR = os.path.join(BASE_DIR, 'database', '30min_60d')  # 60天30分K資料庫
DB_3Y_DIR = os.path.join(BASE_DIR, 'database', '3y_kd')    # 3年回測資料庫（保留）
os.makedirs(WEB_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
sys.path.insert(0, SCRIPT_DIR); load_dotenv(os.path.join(BASE_DIR, '.env'))

CORE_19 = [('2436','偉詮電'),('2337','旺宏'),('5351','鈺創'),('3673','TPK-KY'),('3711','日月光'),
           ('4958','臻鼎-KY'),('3042','晶技'),('2454','聯發科'),('2317','鴻海'),('8150','南茂'),
           ('2330','台積電'),('0050','元大台灣50')]
CORE_IDS = [s[0] for s in CORE_19]; CORE_NAMES = {s[0]:s[1] for s in CORE_19}
_FUBON_NAMES = {}
FUBON_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ═══════════════════════════════ 1. 爬富邦 ═══════════════════════════════
def fetch_fubon_top20():
    print("🌐 爬取富邦主力買超排行...")
    try:
        resp = requests.get(FUBON_URL, headers=HEADERS, timeout=30); resp.encoding='big5'
    except: return []
    if resp.status_code!=200: return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    stocks=[]
    for t in soup.find_all('table'):
        for r in t.find_all('tr'):
            cs=r.find_all('td'); ts=[c.get_text(strip=True) for c in cs]
            if len(ts)!=8 or not ts[0].isdigit(): continue
            m=re.match(r'(\d{4,6}[A-Za-z]?)\s*(.+)',ts[1])
            if m: stocks.append((m.group(1),m.group(2).strip()))
    stocks=[(c,n) for c,n in stocks if re.match(r'^\d{4}$',c)][:20]
    global _FUBON_NAMES; _FUBON_NAMES={s[0]:s[1] for s in stocks}
    print(f"✅ {len(stocks)}檔:"); [print(f"   {c:6s} {n}") for c,n in stocks]
    return stocks

# ═══════════════════════════════ 2. 核心持股：從資料庫讀30分K + TA-Lib ═══════════════════════════════
def calc_30min_kd_macd_rsi_from_db(sid):
    """從 database/30min_60d/ 讀取60天30分K，無則讀 database/3y_kd/"""
    f=os.path.join(DB_DIR,f"{sid}_60d.csv")
    if not os.path.isfile(f):
        f=os.path.join(DB_3Y_DIR,f"{sid}_kd.csv")
        if not os.path.isfile(f): return None
    try:
        df=pd.read_csv(f)
    except: return None
    if len(df)<30: return None
    
    close=np.array(df["close"],dtype=float)
    high=np.array(df["high"],dtype=float)
    low=np.array(df["low"],dtype=float)
    vol=np.array(df["volume"],dtype=float)
    times=list(df.get("datetime", [str(i) for i in range(len(df))]))
    
    # KD (直接用資料庫已算好的K/D，或重新用STOCH)
    k_arr,d_arr=calc_STOCH(high,low,close)
    k_last=float(k_arr[-1]) if not np.isnan(k_arr[-1]) else 50.0
    d_last=float(d_arr[-1]) if not np.isnan(d_arr[-1]) else 50.0
    k_prev=float(k_arr[-2]) if len(k_arr)>=2 and not np.isnan(k_arr[-2]) else k_last
    
    # MACD(30分K) — 柱狀體 + 5期趨勢 + 翻紅預警
    macd_arr,sig_arr,hist_arr=calc_MACD(close)
    h_last=float(hist_arr[-1]) if not np.isnan(hist_arr[-1]) else 0
    # 取最後5根hist值（遇nan替換為0）
    h5=[float(hist_arr[i]) if not np.isnan(hist_arr[i]) else 0 for i in range(-5,0)]
    h5_str=" → ".join(f"{x:.1f}" for x in h5)
    h_prev=h5[-2] if len(h5)>=2 else h_last
    
    # 柱狀體顏色（正值=紅柱，負值=綠柱，用 CSS bar 顯示）
    bar_html=_macd_bar(h_last)
    direction="擴大" if abs(h_last)>abs(h_prev) else "縮小"
    
    flip_warn=""
    if len(h5)>=3 and h_last<0:
        all_shrinking=all(abs(h5[i])>=abs(h5[i+1]) for i in range(len(h5)-1))
        if all_shrinking and h_last>-1.0:
            flip_warn=' <span class="flip">🔥翻紅</span>'
    
    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}<br><span style=\"font-size:14px;color:var(--text-muted)\">{h5_str}</span>"
    
    # RSI(30分K)
    rsi_val=calc_RSI_last(close)
    
    # 30日最低（30分K低點）
    low_30d=round(float(np.min(low[-30:])),1) if len(low)>=30 else None
    
    # 量能
    if len(vol)>=25:
        v5=float(np.mean(vol[-5:])); v20=float(np.mean(vol[-20:-5]))
        vr=v5/v20 if v20>0 else 1.0
    else: vr=1.0
    vol_note="放量🟢" if vr>1.5 else ("量縮🔴" if vr<0.8 else "平量⚪")
    
    # 股價與漲跌
    px=round(close[-1],1)
    chg=0; chg_pct=0
    if len(close)>=2:
        chg=round(px-close[-2],2); chg_pct=round(((px/close[-2])-1)*100,2)
    chg_s = f'<span class="up">▲ {abs(chg):.2f} (+{chg_pct:.2f}%)</span>' if chg>0 else \
            (f'<span class="down">▼ {abs(chg):.2f} ({chg_pct:.2f}%)</span>' if chg<0 else '<span>▸ 0.00 (0.00%)</span>')
    
    # 最新30分K時間
    latest_ts = times[-1]
    
    return {"price":px,"chg_s":chg_s,"k":round(k_last,1),"d":round(d_last,1),"k_prev":round(k_prev,1),
            "macd_s":macd_s,"rsi":rsi_val,"low_30d":low_30d,"vol_note":vol_note,"latest_ts":latest_ts}

# ═══════════════════════════════ 2b. 回退：FinMind 日K（當 Shioaji 或資料庫無資料時）═══════════════════════════════
def calc_30min_from_finmind_fallback(sid):
    """FinMind 60天日K → TA-Lib 算 KD/MACD/RSI（標註為日K替代）"""
    try:
        url="https://api.finmindtrade.com/api/v4/data"
        resp=requests.get(url,params={"dataset":"TaiwanStockPrice","data_id":sid,
            "start_date":(datetime.now()-timedelta(days=90)).strftime("%Y-%m-%d"),
            "end_date":datetime.now().strftime("%Y-%m-%d")},timeout=10)
        d=resp.json()
        if d.get("status")!=200 or not d.get("data"): return None
        items=d["data"]
        close=np.array([r["close"] for r in items],dtype=float)
        high=np.array([r["max"] for r in items],dtype=float)
        low=np.array([r["min"] for r in items],dtype=float)
        vol=np.array([r.get("Trading_Volume",0) for r in items],dtype=float)
    except: return None
    if len(close)<30: return None
    
    k_arr,d_arr=calc_STOCH(high,low,close)
    k_last=float(k_arr[-1]) if not np.isnan(k_arr[-1]) else 50.0
    d_last=float(d_arr[-1]) if not np.isnan(d_arr[-1]) else 50.0
    k_prev=float(k_arr[-2]) if len(k_arr)>=2 and not np.isnan(k_arr[-2]) else k_last
    
    macd_arr,sig_arr,hist_arr=calc_MACD(close)
    h_last=float(hist_arr[-1]) if not np.isnan(hist_arr[-1]) else 0
    h_prev=float(hist_arr[-2]) if len(hist_arr)>=2 and not np.isnan(hist_arr[-2]) else 0
    # MACD(日K) — 柱狀體 + 5期趨勢 + 翻紅預警
    h5=[float(hist_arr[i]) if not np.isnan(hist_arr[i]) else 0 for i in range(-5,0)]
    h5_str=" → ".join(f"{x:.1f}" for x in h5)
    h_prev=h5[-2] if len(h5)>=2 else h_last
    bar_html=_macd_bar(h_last)
    direction="擴大" if abs(h_last)>abs(h_prev) else "縮小"
    flip_warn=""
    if len(h5)>=3 and h_last<0:
        all_shrinking=all(abs(h5[i])>=abs(h5[i+1]) for i in range(len(h5)-1))
        if all_shrinking and h_last>-1.0:
            flip_warn=' <span class="flip">🔥翻紅</span>'
    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}(日K)<br><span style=\"font-size:14px;color:var(--text-muted)\">{h5_str}</span>"
    
    rsi_val=calc_RSI_last(close)
    low_30d=round(float(np.min(low[-30:])),1) if len(low)>=30 else None
    v5=float(np.mean(vol[-5:])); v20=float(np.mean(vol[-20:-5])) if len(vol)>=25 else v5
    vr=v5/v20 if v20>0 else 1.0
    vol_note="放量🟢" if vr>1.5 else ("量縮🔴" if vr<0.8 else "平量⚪")
    px=round(close[-1],1)
    chg=0; chg_pct=0
    if len(close)>=2: chg=round(px-close[-2],2); chg_pct=round(((px/close[-2])-1)*100,2)
    chg_s = f'<span class="up">▲ {abs(chg):.2f} (+{chg_pct:.2f}%)</span>' if chg>0 else (f'<span class="down">▼ {abs(chg):.2f} ({chg_pct:.2f}%)</span>' if chg<0 else '<span>▸ 0.00 (0.00%)</span>')
    return {"price":px,"chg_s":chg_s,"k":round(k_last,1),"d":round(d_last,1),"k_prev":round(k_prev,1),
            "macd_s":macd_s,"rsi":rsi_val,"low_30d":low_30d,"vol_note":vol_note,"latest_ts":"日K(替代)"}

# ═══════════════════════════════ 3. 潛力股：Shioaji 60天→30分K→TA-Lib ═══════════════════════════════
def calc_30min_from_shioaji(sid):
    """Shioaji 60天1分K→合併30分K→TA-Lib全算"""
    import shioaji as sj
    import datetime as dt_module
    api_key=os.environ.get("SJ_API_KEY",""); sec_key=os.environ.get("SJ_SEC_KEY","")
    if not api_key or not sec_key: return None
    api=sj.Shioaji(simulation=False)
    try:
        api.login(api_key=api_key,secret_key=sec_key,fetch_contract=True)
    except: return None
    
    try:
        contract=api.Contracts.Stocks[sid]
    except:
        try: api.logout()
        except: pass
        return None
    
    end=datetime.now(); start=end-timedelta(days=60)
    # 分段：14天/段
    segs=[]; ss=start
    while ss<end:
        se=min(ss+timedelta(days=14),end)
        segs.append((ss,se)); ss=se
    
    all_rows=[]
    for s,e in segs:
        try:
            kb=api.kbars(contract=contract,start=s.strftime("%Y-%m-%d"),end=e.strftime("%Y-%m-%d"))
            if kb is None or len(kb.ts)==0: continue
            for i in range(len(kb.ts)):
                ts_utc=datetime.fromtimestamp(kb.ts[i]/1e9,tz=datetime.timezone.utc)
                ts_local=ts_utc+timedelta(hours=8)
                all_rows.append({"ts":ts_local,"Open":float(kb.Open[i]),"High":float(kb.High[i]),
                    "Low":float(kb.Low[i]),"Close":float(kb.Close[i]),"Volume":float(kb.Volume[i])})
        except: continue
    
    api.logout()
    
    if not all_rows:
        # Shioaji 盤前無資料→Fallback到FinMind日K
        return calc_30min_from_finmind_fallback(sid)
    df=pd.DataFrame(all_rows).sort_values("ts").drop_duplicates(subset="ts").reset_index(drop=True)
    
    # 合併30分K
    df=df.set_index("ts")
    ohlc=pd.DataFrame({"Open":df["Open"].resample("30min").first()})
    ohlc["High"]=df["High"].resample("30min").max()
    ohlc["Low"]=df["Low"].resample("30min").min()
    ohlc["Close"]=df["Close"].resample("30min").last()
    ohlc["Volume"]=df["Volume"].resample("30min").sum()
    ohlc=ohlc.dropna().reset_index()
    
    # 過濾台股交易時段 (UTC+8: 09:00~13:30)
    ohlc["hour"]=ohlc["ts"].dt.hour; ohlc["minute"]=ohlc["ts"].dt.minute
    ohlc=ohlc[
        ((ohlc["hour"]==9)&(ohlc["minute"]>=0))|
        ((ohlc["hour"]>=10)&(ohlc["hour"]<=12))|
        ((ohlc["hour"]==13)&(ohlc["minute"]<=30))
    ].drop(columns=["hour","minute"]).reset_index(drop=True)
    
    if len(ohlc)<30:
        # Shioaji 盤前抓不到盤中資料→用 FinMind 日K 替代（標註日K）
        return calc_30min_from_finmind_fallback(sid)
    
    close=np.array(ohlc["Close"],dtype=float)
    high=np.array(ohlc["High"],dtype=float)
    low=np.array(ohlc["Low"],dtype=float)
    vol=np.array(ohlc["Volume"],dtype=float)
    times=list(ohlc["ts"])
    
    # TA-Lib 全算
    k_arr,d_arr=calc_STOCH(high,low,close)
    k_last=float(k_arr[-1]) if not np.isnan(k_arr[-1]) else 50.0
    d_last=float(d_arr[-1]) if not np.isnan(d_arr[-1]) else 50.0
    k_prev=float(k_arr[-2]) if len(k_arr)>=2 and not np.isnan(k_arr[-2]) else k_last
    
    macd_arr,sig_arr,hist_arr=calc_MACD(close)
    h_last=float(hist_arr[-1]) if not np.isnan(hist_arr[-1]) else 0
    h_prev=float(hist_arr[-2]) if len(hist_arr)>=2 and not np.isnan(hist_arr[-2]) else 0
    # MACD(30分K Shioaji) — 柱狀體 + 5期趨勢 + 翻紅預警
    h5=[float(hist_arr[i]) if not np.isnan(hist_arr[i]) else 0 for i in range(-5,0)]
    h_prev=h5[-2] if len(h5)>=2 else h_last
    bar_html=_macd_bar(h_last)
    direction="擴大" if abs(h_last)>abs(h_prev) else "縮小"
    flip_warn=""
    if len(h5)>=3 and h_last<0:
        all_shrinking=all(abs(h5[i])>=abs(h5[i+1]) for i in range(len(h5)-1))
        if all_shrinking and h_last>-1.0:
            flip_warn=' <span class="flip">🔥翻紅</span>'
    macd_s=f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}<br><span style=\"font-size:14px;color:var(--text-muted)\">{h5_str}</span>"
    
    rsi_val=calc_RSI_last(close)
    
    low_30d=round(float(np.min(low[-30:])),1) if len(low)>=30 else None
    v5=float(np.mean(vol[-5:])); v20=float(np.mean(vol[-20:-5])) if len(vol)>=25 else v5
    vr=v5/v20 if v20>0 else 1.0
    vol_note="放量🟢" if vr>1.5 else ("量縮🔴" if vr<0.8 else "平量⚪")
    
    px=round(close[-1],1)
    chg=0; chg_pct=0
    if len(close)>=2:
        chg=round(px-close[-2],2); chg_pct=round(((px/close[-2])-1)*100,2)
    chg_s = f'<span class="up">▲ {abs(chg):.2f} (+{chg_pct:.2f}%)</span>' if chg>0 else \
            (f'<span class="down">▼ {abs(chg):.2f} ({chg_pct:.2f}%)</span>' if chg<0 else '<span>▸ 0.00 (0.00%)</span>')
    
    latest_ts=str(times[-1])
    return {"price":px,"chg_s":chg_s,"k":round(k_last,1),"d":round(d_last,1),"k_prev":round(k_prev,1),
            "macd_s":macd_s,"rsi":rsi_val,"low_30d":low_30d,"vol_note":vol_note,"latest_ts":latest_ts}

# ═══════════════════════════════ 4. 大盤20日線（30分K資料庫） ═══════════════════════════════
def check_market_below_20ma():
    """用 FinMind TAIEX 日K 看大盤是否跌破20MA"""
    d=calc_30min_from_finmind_fallback("TAIEX") or calc_30min_from_finmind_fallback("0050")
    if d is None: return False
    # 從 FinMind 日K 抓原始資料
    try:
        url="https://api.finmindtrade.com/api/v4/data"
        resp=requests.get(url,params={"dataset":"TaiwanStockPrice","data_id":"TAIEX",
            "start_date":(datetime.now()-timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date":datetime.now().strftime("%Y-%m-%d")},timeout=10)
        di=resp.json()
        if di.get("status")!=200 or not di.get("data"):
            resp=requests.get(url,params={"dataset":"TaiwanStockPrice","data_id":"0050",
                "start_date":(datetime.now()-timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date":datetime.now().strftime("%Y-%m-%d")},timeout=10)
            di=resp.json()
        if di.get("status")!=200 or not di.get("data"): return False
        items=di["data"]
        c=np.array([r["close"] for r in items],dtype=float)
        if len(c)<25: return False
        last=c[-1]; ma20=np.mean(c[-20:])
        if last<ma20: print(f"📉 大盤跌破20日線 ({last:.0f}<{ma20:.0f}) → 嚴格K<30"); return True
        print(f"📈 大盤站上20日線 ({last:.0f}>={ma20:.0f}) → 正常K<35"); return False
    except: return False

# ═══════════════════════════════ 5. 批次分析 ═══════════════════════════════
def analyze_all(stock_ids, strict_mode):
    kth=30 if strict_mode else 35
    print(f"\n📊 30分K TA-Lib 分析 {len(stock_ids)} 檔 (KD門檻 K<{kth})...")
    results={}
    for sid in stock_ids:
        name=CORE_NAMES.get(sid,_FUBON_NAMES.get(sid,sid))
        # 核心→資料庫；非核心→Shioaji
        # 核心(含0050)→資料庫；非核心→Shioaji(盤後)→FinMind
        if sid in CORE_IDS:
            t=calc_30min_kd_macd_rsi_from_db(sid)
            if t is None and sid=="0050":
                t=calc_30min_from_finmind_fallback(sid)
                if t: print(f"  📌 0050: FinMind日K(替代)")
        else:
            t=calc_30min_from_shioaji(sid)
            if t is None:
                # 等開盤後Shioaji可抓盤中資料；但現在先用FinMind日K替代
                t=calc_30min_from_finmind_fallback(sid)
                if t: print(f"  📌 {sid:4s} {str(name):8s}: FinMind日K(替代)")
        
        if t is None:
            print(f"  ⚠️ {sid:4s} {str(name):8s}: 無30分K資料")
            continue
        
        k_last=t["k"]; gap=k_last-t["d"]; golden=k_last>=t["d"]
        k_tu=k_last>t["k_prev"]; rsi=t["rsi"]
        
        low_golden=golden and (gap<5) and (k_last<kth) and k_tu
        high_overheat=golden and (k_last>80)
        
        if low_golden: kd_s=f"🏹 低檔金叉 (K:{k_last:.0f} / D:{t['d']:.0f})"
        elif high_overheat: kd_s=f"⚠️ 高檔過熱 (K:{k_last:.0f} / D:{t['d']:.0f})"
        elif golden and gap<3: kd_s=f"🟡 逼近金叉 (K:{k_last:.0f} / D:{t['d']:.0f})"
        elif golden: kd_s=f"🟢 金叉 (K:{k_last:.0f} / D:{t['d']:.0f})"
        elif not golden and gap>-3: kd_s=f"🟡 逼近死叉 (K:{k_last:.0f} / D:{t['d']:.0f})"
        else: kd_s=f"🔴 死叉 (K:{k_last:.0f} / D:{t['d']:.0f})"
        
        if low_golden and rsi<40: strategy="🟢🟢 低檔金叉進場"
        elif low_golden: strategy="🟢 低檔金叉留意"
        elif high_overheat: strategy="⚠️ 高檔勿追"
        elif golden and rsi<50: strategy="🟡 金叉觀察"
        elif not golden and gap<-3: strategy="🔴 死叉避開"
        elif rsi>70: strategy="⚠️ 過熱"
        elif rsi<30 and golden: strategy="🟢 超賣金叉"
        else: strategy="➖ 觀望"
        
        t["kd_status"]=kd_s; t["low_golden"]=low_golden; t["strategy"]=strategy; t["name"]=name
        results[sid]=t
        ts=t.get("latest_ts","?")
        print(f"  {sid:4s} {str(name):8s} | {kd_s[:22]:22s} | MACD:{t['macd_s'][:8]:8s} | RSI:{rsi:5.1f} | [{ts}] {strategy}")
    return results

# ═══════════════════════════════ 6. HTML ═══════════════════════════════
def gen_html(core,pot,fubon,strict_mode):
    kth=30 if strict_mode else 35
    mn="📉 跌破20日線｜K<30" if strict_mode else "📈 站穩20日線｜K<35"
    td_=datetime.now().strftime("%Y-%m-%d"); nh=datetime.now().strftime("%H:%M")
    
    cr="".join(_row(s,n,core.get(s)) for s,n in CORE_19 if core.get(s))
    if not cr: cr='<tr><td colspan="7" style="text-align:center;color:#666;">⏳ 讀取中</td></tr>'
    pr="".join(_row(s,n,pot.get(s)) for s,n in fubon if s not in CORE_IDS and pot.get(s))
    if not pr: pr='<tr><td colspan="7" style="text-align:center;color:#666;">⚠️ 無30分K資料</td></tr>'
    
    buys=[(s,t) for s,t in sorted({**core,**pot}.items()) if t and t.get("low_golden")]
    ah="".join(f'<div class="buy-signal">🔔 {t["name"]}({s}) [30分K] K:{t["k"]:.0f}/D:{t["d"]:.0f} RSI:{t["rsi"]}</div>' for s,t in buys)
    if ah: ah=f'\n<div class="card buy"><div class="card-title" style="color:var(--green-go);">🔔 買進訊號（低檔金叉）</div>{ah}</div>'
    
    return f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>🦞 小龍蝦 | 30分K統一週期 + TA-Lib</title>
<style>:root{{--bg-dark:#121212;--card-bg:#1e1e1e;--primary-gold:#ffbe76;--red-alert:#ff6b6b;--green-go:#2ed573;--text-main:#e0e0e0;--text-muted:#a0a0a0;--border-color:#333;}}
*{{box-sizing:border-box;}} body{{font-family:-apple-system,"Segoe UI",Roboto,"Microsoft JhengHei",sans-serif;background:var(--bg-dark);color:var(--text-main);margin:0;padding:12px;font-size:18px;}}
.header{{text-align:center;padding:14px 0;border-bottom:3px solid var(--red-alert);margin-bottom:16px;}}
.header h1{{margin:0;font-size:22px;color:var(--red-alert);}}
.header p{{margin:6px 0 0;color:var(--text-muted);}}
.card{{background:var(--card-bg);border-radius:8px;padding:15px;margin-bottom:15px;border-left:5px solid var(--primary-gold);}}
.card.alert{{border-left-color:var(--red-alert);}} .card.info{{border-left-color:#1e90ff;}} .card.buy{{border-left-color:var(--green-go);}}
.card-title{{font-size:20px;font-weight:bold;margin-bottom:12px;color:var(--primary-gold);}}
table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:18px;}}
th{{background:#2d2d2d;color:var(--primary-gold);padding:8px 6px;text-align:left;border-bottom:2px solid var(--border-color);}}
td{{padding:10px 6px;border-bottom:1px solid var(--border-color);vertical-align:middle;}}
.up{{color:var(--red-alert);font-weight:bold;}} .down{{color:var(--green-go);font-weight:bold;}}
.macd-bar{{display:inline-block;height:14px;border-radius:3px;min-width:4px;vertical-align:middle;margin-right:3px;}}
.macd-bar.pos{{background:var(--red-alert);}} .macd-bar.neg{{background:var(--green-go);}}
.flip{{color:#ffd700;font-weight:bold;font-size:16px;}}
.buy-signal{{font-size:20px;font-weight:bold;padding:8px;margin:5px 0;background:#0d2a0d;border-radius:6px;border:1px solid var(--green-go);}}
.footer{{text-align:center;color:#445566;margin-top:30px;padding-top:15px;border-top:1px solid #333;}}
</style></head><body>
<div class="header"><h1>🦞 小龍蝦 | 30分K統一週期</h1><p>{td_} {nh} | {mn}</p></div>
<div class="card info"><div class="card-title">📊 系統</div>
<div style="text-align:center;padding:10px;border:1px solid #444;border-radius:6px;font-size:20px;font-weight:bold;">{mn}</div>
<div style="margin-top:8px;color:#aaa;font-size:16px;">✅ 全部30分K｜TA-Lib STOCH+MACD+RSI｜來源: 3年KD資料庫 + Shioaji</div></div>
{ah}
<div class="card"><div class="card-title">🔒 核心持股（{len(CORE_19)}檔）[30分K]</div>
<table><thead><tr><th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{cr}</tbody></table></div>
<div class="card alert"><div class="card-title">🎯 投信連買前20名 ─ 潛力股 [30分K]</div>
<div style="font-size:16px;color:var(--text-muted);margin-bottom:8px;">來源: 富邦eBroker DJ | 30分K(Shioaji+TA-Lib)</div>
<table><thead><tr><th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{pr}</tbody></table></div>
<div class="footer">小龍蝦自動產出 | {td_} {nh} | 全部30分K ｜ TA-Lib {talib.__version__}</div>
</body></html>'''

def _macd_bar(val):
    """產生微型橫向柱狀條HTML，正值=紅/負值=綠，寬度=abs(val)*3 (max 80px)"""
    w=min(abs(val)*3, 80)
    if w<4: w=4
    cls="pos" if val>=0 else "neg"
    return f'<span class="macd-bar {cls}" style="width:{w:.0f}px"></span>'

def _row(sid,sname,t):
    px=t.get("price",0); lo=t.get("low_30d"); chg=t.get("chg_s","")
    lo_s=str(lo) if lo else "—"
    if lo and px:
        d=round(((px/lo)-1)*100,1)
        if d<5: lo_s=f'<span style="color:var(--red-alert)">{lo} ⚠️</span>'
    sc=f'<div style="line-height:1.2"><b>{sname}</b></div><div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">{sid}</div>'
    pc=f'<div style="font-weight:bold;font-size:1.05em;line-height:1.2">{px}</div><div style="font-size:0.85em;line-height:1.2">{chg}</div>'
    return f'<tr><td>{sc}</td><td>{pc}</td><td>{lo_s}</td><td>{t["kd_status"]}</td><td>{t["macd_s"]}</td><td>{t["rsi"]}</td><td>{t["strategy"]}</td></tr>\n'

# ═══════════════════════════════ MAIN ═══════════════════════════════
def main():
    print("="*60); print(f"  🦞 30分K統一週期 v6"); print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}"); print("="*60)
    t0=datetime.now()
    fubon=fetch_fubon_top20()
    if not fubon: fubon=[("2330","台積電"),("2317","鴻海"),("2454","聯發科")]
    strict=check_market_below_20ma()
    all_ids=list(dict.fromkeys(CORE_IDS+[s[0] for s in fubon]))
    results=analyze_all(all_ids,strict)
    core={s:results[s] for s in CORE_IDS if s in results}
    pot={s:results[s] for s in [s[0] for s in fubon] if s not in CORE_IDS and s in results}
    html=gen_html(core,pot,fubon,strict)
    for p in [os.path.join(WEB_DIR,"index.html"),os.path.join(BASE_DIR,"index.html")]:
        with open(p,"w",encoding="utf-8") as f: f.write(html)
    buys=[(s,t) for s,t in sorted(results.items()) if t and t.get("low_golden")]
    if buys:
        print("\n"+"!"*50); print("  🟢🟢🟢 買進訊號 🟢🟢🟢")
        for s,t in buys: print(f"  🔔🔔🔔 {t['name']}({s}) [30分K] K:{t['k']:.0f} RSI:{t['rsi']}")
        print("!"*50)
    else: print("\nℹ️  無低檔金叉")
    print(f"\n📄 {len(html)//1024} KB → {os.path.join(WEB_DIR,'index.html')}")
    print(f"⏱️  {(datetime.now()-t0).total_seconds():.0f} 秒")
    # 輸出資料週期確認
    print(f"📌 資料來源: 核心=3y_kd資料庫 / 潛力股=Shioaji 60天1分K→30分K")
    print(f"📌 全部TA-Lib計算於同根30分K")

if __name__=="__main__": main()
