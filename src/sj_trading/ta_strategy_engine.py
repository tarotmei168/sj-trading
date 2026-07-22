#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════╗
║  ta_strategy_engine.py  —  量化策略核心引擎  ║
║  0 Token 本地高速運算                         ║
║  資料: Shioaji 60天1分K → 30分K              ║
║  計算: TA-Lib STOCH / MACD / RSI            ║
║  輸出: today_signal.json + 早報 HTML         ║
╚═══════════════════════════════════════════════╝

執行流程:
  1. Shioaji 登入
  2. 爬富邦主力買超排行（BS4）→ 取得潛力股清單
  3. 下載 32 檔標的 60 天 1分K（分段14天）
  4. 合併 30分K，過濾台股交易時段 09:00~13:30
  5. TA-Lib 計算:
     - STOCH() → 30分K KD
     - MACD() → 30分K MACD（含柱狀體）
     - RSI() → 30分K RSI
  6. 數據防呆: K>50 絕不判定低檔金叉; K>80 標示高檔過熱
  7. 輸出 today_signal.json + web/index.html
"""
import sys, os, json, re, time
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import talib

# ═══════════════════════════ 路徑 ═══════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
DB_DIR = os.path.join(BASE_DIR, 'database', '30min_60d')
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

sys.path.insert(0, SCRIPT_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

import shioaji as sj

# ═══════════════════════════ 股票清單 ═══════════════════════════
CORE_19 = [
    ('2436','偉詮電'), ('2337','旺宏'), ('5351','鈺創'),
    ('3673','TPK-KY'), ('3711','日月光'), ('4958','臻鼎-KY'),
    ('3042','晶技'), ('2454','聯發科'), ('2317','鴻海'),
    ('8150','南茂'), ('2330','台積電'), ('0050','元大台灣50'),
]
CORE_IDS = [s[0] for s in CORE_19]
CORE_NAMES = {s[0]: s[1] for s in CORE_19}

# KD 參數
KD_PARAMS = {
    "2436":5, "2337":21, "5351":14, "3673":14, "3711":21,
    "4958":21, "3042":14, "2454":21, "2317":14, "8150":21,
    "2330":9, "0050":9,
}

FUBON_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ═══════════════════════════ 1. 爬富邦排行 ═══════════════════════════
def fetch_fubon_top20():
    """爬富邦DJ主力買超排行，回傳 [(代號, 名稱), ...]"""
    print("🌐 爬取富邦主力買超排行...")
    try:
        resp = requests.get(FUBON_URL, headers=HEADERS, timeout=30)
        resp.encoding = 'big5'
    except:
        return []
    if resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    stocks = []
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            texts = [c.get_text(strip=True) for c in cells]
            if len(texts) != 8 or not texts[0].isdigit():
                continue
            m = re.match(r'(\d{4,6}[A-Za-z]?)\s*(.+)', texts[1])
            if m:
                stocks.append((m.group(1), m.group(2).strip()))
    # 只留 4 碼個股
    stocks = [(c, n) for c, n in stocks if re.match(r'^\d{4}$', c)][:20]
    print(f"✅ 富邦排行 {len(stocks)} 檔")
    for c, n in stocks:
        print(f"   {c:6s} {n}")
    return stocks


# ═══════════════════════════ 2. Shioaji 登入 + 資料下載 ═══════════════════════════
def login_shioaji():
    api_key = os.environ.get("SJ_API_KEY", "")
    sec_key = os.environ.get("SJ_SEC_KEY", "")
    if not api_key or not sec_key:
        print("❌ 無 API Key")
        return None
    api = sj.Shioaji(simulation=False)
    try:
        api.login(api_key=api_key, secret_key=sec_key, fetch_contract=True)
        print("✅ Shioaji 登入成功")
        return api
    except Exception as e:
        print(f"❌ Shioaji 登入失敗: {e}")
        return None


def download_60d_1min(api, sid):
    """
    下載 60 天 1分K，分段 14天/段
    Shioaji ts 為 UTC → 轉台北時間
    """
    end = datetime.now()
    start = end - timedelta(days=60)
    segs = []
    s = start
    while s < end:
        e = min(s + timedelta(days=14), end)
        segs.append((s, e))
        s = e
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        print(f"  ⚠️ {sid}: 無合約")
        return None
    rows = []
    for ss, se in segs:
        for retry in range(3):
            try:
                kb = api.kbars(contract=contract, start=ss.strftime("%Y-%m-%d"),
                               end=se.strftime("%Y-%m-%d"), timeout=15000)
                if kb and len(kb.ts) > 0:
                    for i in range(len(kb.ts)):
                        utc = datetime.fromtimestamp(kb.ts[i] / 1e9)
                        local = utc + timedelta(hours=8)
                        rows.append({
                            "ts": local,
                            "Open": float(kb.Open[i]),
                            "High": float(kb.High[i]),
                            "Low": float(kb.Low[i]),
                            "Close": float(kb.Close[i]),
                            "Volume": float(kb.Volume[i]),
                        })
                break
            except:
                if retry < 2:
                    time.sleep(2 * (retry + 1))
                else:
                    break
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("ts").drop_duplicates(subset="ts").reset_index(drop=True)


def merge_30min(df):
    """1分K → 30分K，過濾台股交易時段 09:00~13:30（台北時間）"""
    if df is None or df.empty:
        return None
    d = df.set_index("ts")
    o = pd.DataFrame({"open": d["Open"].resample("30min").first()})
    o["high"] = d["High"].resample("30min").max()
    o["low"] = d["Low"].resample("30min").min()
    o["close"] = d["Close"].resample("30min").last()
    o["volume"] = d["Volume"].resample("30min").sum()
    o = o.dropna().reset_index()
    o["h"] = o["ts"].dt.hour
    o["m"] = o["ts"].dt.minute
    o = o[((o["h"] == 9) & (o["m"] >= 0)) |
          ((o["h"] >= 10) & (o["h"] <= 12)) |
          ((o["h"] == 13) & (o["m"] <= 30))]
    o = o.drop(columns=["h", "m"]).reset_index(drop=True)
    if len(o) < 25:
        return None
    return o


# ═══════════════════════════ 3. TA-Lib 指標計算 ═══════════════════════════
def calc_talib(sid, df30):
    """
    TA-Lib 全指標計算:
      - STOCH → KD
      - MACD → MACD + MACD_hist
      - RSI → RSI
    數據防呆:
      - K>50 絕不判定低檔金叉
      - K>80 強制標示高檔過熱
    回傳 dict 或 None
    """
    close = np.array(df30["close"], dtype=float)
    high = np.array(df30["high"], dtype=float)
    low = np.array(df30["low"], dtype=float)
    vol = np.array(df30["volume"], dtype=float)

    kp = KD_PARAMS.get(sid, 9)

    # KD
    k_arr, d_arr = talib.STOCH(high, low, close, fastk_period=kp, slowk_period=3, slowd_period=3)
    k_last = float(k_arr[-1]) if not np.isnan(k_arr[-1]) else 50.0
    d_last = float(d_arr[-1]) if not np.isnan(d_arr[-1]) else 50.0
    k_prev = float(k_arr[-2]) if len(k_arr) >= 2 and not np.isnan(k_arr[-2]) else k_last
    gap = k_last - d_last
    golden = k_last >= d_last
    k_trend_up = k_last > k_prev

    # MACD
    macd_arr, sig_arr, hist_arr = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    h_last = float(hist_arr[-1]) if not np.isnan(hist_arr[-1]) else 0

    # 5 期趨勢
    h5 = [float(hist_arr[i]) if not np.isnan(hist_arr[i]) else 0 for i in range(-5, 0)]
    h_prev = h5[-2] if len(h5) >= 2 else h_last
    h5_str = " → ".join(f"{x:.1f}" for x in h5)

    direction = "擴大" if abs(h_last) > abs(h_prev) else "縮小"
    flip_warn = ""
    if len(h5) >= 3 and h_last < 0:
        all_shrinking = all(abs(h5[i]) >= abs(h5[i+1]) for i in range(len(h5)-1))
        if all_shrinking and h_last > -1.0:
            flip_warn = ' <span class="flip">🔥翻紅</span>'

    bar_html = _macd_bar(h_last)
    macd_s = f"{bar_html} Hist:{h_last:.1f} {direction}{flip_warn}<br><span style=\"font-size:14px;color:var(--text-muted)\">{h5_str}</span>"

    # RSI
    rsi_arr = talib.RSI(close, timeperiod=14)
    rsi_val = round(float(rsi_arr[-1]) if not np.isnan(rsi_arr[-1]) else 50, 1)

    # 30日低價
    low_30d = round(float(np.min(low[-30:])), 1) if len(low) >= 30 else None

    # 量能
    v5 = float(np.mean(vol[-5:]))
    v20 = float(np.mean(vol[-20:-5])) if len(vol) >= 25 else v5
    vr = v5 / v20 if v20 > 0 else 1.0
    vol_note = "放量🟢" if vr > 1.5 else ("量縮🔴" if vr < 0.8 else "平量⚪")

    # 股價與漲跌
    px = round(close[-1], 1)
    chg = 0
    chg_pct = 0.0
    if len(close) >= 2:
        chg = round(px - close[-2], 2)
        chg_pct = round(((px / close[-2]) - 1) * 100, 2)
    if chg > 0:
        chg_s = f'▲ {abs(chg):.2f} (+{chg_pct:.2f}%)'
    elif chg < 0:
        chg_s = f'▼ {abs(chg):.2f} ({chg_pct:.2f}%)'
    else:
        chg_s = '▸ 0.00 (0.00%)'

    # K 值防呆
    k_threshold = 30  # 嚴格模式 (跌破20日線時)
    low_golden = False
    high_overheat = False

    if k_last > 80 and golden:
        high_overheat = True
    elif golden and gap < 5 and k_last < k_threshold and k_trend_up:
        low_golden = True

    if low_golden:
        kd_s = f"🏹 低檔金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif high_overheat:
        kd_s = f"⚠️ 高檔過熱 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif golden and gap < 3:
        kd_s = f"🟡 逼近金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif golden:
        kd_s = f"🟢 金叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    elif not golden and gap > -3:
        kd_s = f"🟡 逼近死叉 (K:{k_last:.0f} / D:{d_last:.0f})"
    else:
        kd_s = f"🔴 死叉 (K:{k_last:.0f} / D:{d_last:.0f})"

    if low_golden and rsi_val < 40:
        strategy = "🟢🟢 低檔金叉進場"
    elif low_golden:
        strategy = "🟢 低檔金叉留意"
    elif high_overheat:
        strategy = "⚠️ 高檔勿追"
    elif golden and rsi_val < 50:
        strategy = "🟡 金叉觀察"
    elif not golden and gap < -3:
        strategy = "🔴 死叉避開"
    elif rsi_val > 70:
        strategy = "⚠️ 過熱"
    elif rsi_val < 30 and golden:
        strategy = "🟢 超賣金叉"
    else:
        strategy = "➖ 觀望"

    return {
        "sid": sid,
        "price": px,
        "chg": chg,
        "chg_pct": chg_pct,
        "chg_s": chg_s,
        "k": round(k_last, 1),
        "d": round(d_last, 1),
        "gap": round(gap, 1),
        "golden": golden,
        "k_trend_up": k_trend_up,
        "low_golden": low_golden,
        "high_overheat": high_overheat,
        "kd_s": kd_s,
        "macd_s": macd_s,
        "rsi": rsi_val,
        "low_30d": low_30d,
        "vol_note": vol_note,
        "strategy": strategy,
        "latest_ts": str(df30["ts"].iloc[-1]) if "ts" in df30.columns else "—",
    }


def _macd_bar(val):
    w = min(abs(val) * 3, 80)
    if w < 4:
        w = 4
    cls = "pos" if val >= 0 else "neg"
    return f'<span class="macd-bar {cls}" style="width:{w:.0f}px"></span>'


# ═══════════════════════════ 4. 大盤20日線檢查 ═══════════════════════════
def check_market_below_20ma():
    """FinMind TAIEX 日K → 判斷大盤是否跌破20MA"""
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        resp = requests.get(url, params={
            "dataset": "TaiwanStockPrice", "data_id": "TAIEX",
            "start_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
        }, timeout=10)
        d = resp.json()
        if d.get("status") != 200 or not d.get("data"):
            resp = requests.get(url, params={
                "dataset": "TaiwanStockPrice", "data_id": "0050",
                "start_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d"),
            }, timeout=10)
            d = resp.json()
        if d.get("status") != 200 or not d.get("data"):
            return False
        items = d["data"]
        closes = np.array([r["close"] for r in items], dtype=float)
        if len(closes) < 25:
            return False
        last = closes[-1]
        ma20 = np.mean(closes[-20:])
        if last < ma20:
            print(f"📉 大盤跌破20日線 ({last:.0f}<{ma20:.0f}) → 嚴格模式 K<30")
            return True
        print(f"📈 大盤站上20日線 ({last:.0f}>={ma20:.0f}) → 正常模式 K<35")
        return False
    except:
        return False


# ═══════════════════════════ 5. 批次處理 ═══════════════════════════
def analyze_stocks(api, stock_ids, strict_mode):
    """從 database/30min_60d/ 讀取資料 + Shioaji snapshot 即時更新 + TA-Lib"""
    kth = 30 if strict_mode else 35
    results = {}
    print(f"\n📊 讀取 30min_60d DB + TA-Lib {len(stock_ids)} 檔 (K<{kth} 低檔金叉)")

    for sid in stock_ids:
        name = CORE_NAMES.get(sid, sid)
        print(f"\n  {sid} {name}...", end=" ", flush=True)

        # 讀資料庫
        f = os.path.join(DB_DIR, f"{sid}_60d.csv")
        if not os.path.isfile(f):
            print("❌ 無資料庫檔案")
            continue
        try:
            df = pd.read_csv(f)
        except:
            print("❌ 讀取失敗")
            continue
        if len(df) < 25:
            print("❌ 資料不足")
            continue

        # Shioaji snapshot 更新最後一筆收盤價
        try:
            contract = api.Contracts.Stocks[sid]
            snaps = api.snapshots([contract])
            if snaps and len(snaps) > 0 and snaps[0].close:
                live_px = round(float(snaps[0].close), 1)
                df.loc[df.index[-1], "close"] = live_px
                print(f"snapshot:{live_px}", end=" ", flush=True)
        except:
            print(f"({df.iloc[-1]["close"]})", end=" ", flush=True)

        t = calc_talib(sid, df)
        if t:
            t["name"] = name
            results[sid] = t
            print(f"K:{t['k']:.1f}/D:{t['d']:.1f} RSI:{t['rsi']} | {t['strategy']}")
    return results


# ═══════════════════════════ 6. JSON 輸出 ═══════════════════════════
def save_signal_json(results):
    """輸出精簡 today_signal.json"""
    signals = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "stocks": {}
    }
    for sid, t in results.items():
        signals["stocks"][sid] = {
            "name": t.get("name", sid),
            "price": t["price"],
            "chg": t["chg"],
            "chg_pct": t["chg_pct"],
            "k": t["k"],
            "d": t["d"],
            "golden": t["golden"],
            "low_golden": t["low_golden"],
            "high_overheat": t["high_overheat"],
            "rsi": t["rsi"],
            "low_30d": t["low_30d"],
            "strategy": t["strategy"],
        }
    path = os.path.join(OUTPUT_DIR, "today_signal.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    print(f"\n📄 today_signal.json ({len(results)} 檔)")


# ═══════════════════════════ 7. HTML 輸出 ═══════════════════════════
def generate_html(core, pot, fubon_stocks, strict_mode):
    kth = 30 if strict_mode else 35
    mn = "📉 跌破20日線｜K<30" if strict_mode else "📈 站穩20日線｜K<35"
    td = datetime.now().strftime("%Y-%m-%d")
    nh = datetime.now().strftime("%H:%M")

    cr = "".join(_row(s, n, core.get(s)) for s, n in CORE_19 if core.get(s))
    if not cr:
        cr = '<tr><td colspan="7" style="text-align:center;color:#666;">⏳ 讀取中</td></tr>'
    pr = "".join(_row(s, n, pot.get(s)) for s, n in fubon_stocks if s not in CORE_IDS and pot.get(s))
    if not pr:
        pr = '<tr><td colspan="7" style="text-align:center;color:#666;">⚠️ 無資料</td></tr>'

    buys = [(s, t) for s, t in sorted({**core, **pot}.items()) if t and t.get("low_golden")]
    ah = "".join(
        f'<div class="buy-signal">🔔 {t["name"]}({s}) K:{t["k"]:.0f}/D:{t["d"]:.0f} RSI:{t["rsi"]}</div>'
        for s, t in buys
    )
    if ah:
        ah = f'\n<div class="card buy"><div class="card-title" style="color:var(--green-go);">🔔 買進訊號（低檔金叉）</div>{ah}</div>'

    return f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>🦞 小龍蝦 | ta_strategy_engine</title>
<style>
:root{{--bg-dark:#121212;--card-bg:#1e1e1e;--primary-gold:#ffbe76;--red-alert:#ff6b6b;--green-go:#2ed573;--text-main:#e0e0e0;--text-muted:#a0a0a0;--border-color:#333;}}
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
<div class="header"><h1>🦞 小龍蝦 | 30分K統一週期 + TA-Lib</h1><p>{td} {nh} | {mn}</p></div>
<div class="card info"><div class="card-title">📊 系統</div>
<div style="text-align:center;padding:10px;border:1px solid #444;border-radius:6px;font-size:20px;font-weight:bold;">{mn}</div>
<div style="margin-top:8px;color:#aaa;font-size:16px;">✅ Shioaji 60天1分K→30分K｜TA-Lib STOCH+MACD+RSI｜K<{kth}低檔金叉</div></div>
{ah}
<div class="card"><div class="card-title">🔒 核心持股（{len(CORE_19)}檔）[30分K]</div>
<table><thead><tr><th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{cr}</tbody></table></div>
<div class="card alert"><div class="card-title">🎯 富邦主力買超排行 ─ 潛力股 [30分K]</div>
<div style="font-size:16px;color:var(--text-muted);margin-bottom:8px;">來源: 富邦eBroker DJ</div>
<table><thead><tr><th>股票</th><th>股價</th><th>30日低</th><th>KD</th><th>MACD</th><th>RSI</th><th>策略</th></tr></thead><tbody>{pr}</tbody></table></div>
<div class="footer">小龍蝦自動產出 | {td} {nh} | ta_strategy_engine | 全部30分K</div>
</body></html>'''


def _row(sid, sname, t):
    px = t.get("price", 0)
    lo = t.get("low_30d")
    chg = t.get("chg_s", "")
    cls = "up" if t.get("chg", 0) > 0 else ("down" if t.get("chg", 0) < 0 else "")
    if cls:
        chg = f'<span class="{cls}">{chg}</span>'
    lo_s = str(lo) if lo else "—"
    if lo and px:
        d = round(((px / lo) - 1) * 100, 1)
        if d < 5:
            lo_s = f'<span style="color:var(--red-alert)">{lo} ⚠️</span>'
    sc = (f'<div style="line-height:1.2"><b>{sname}</b></div>'
          f'<div style="font-size:0.85em;color:var(--text-muted);line-height:1.2">{sid}</div>')
    pc = (f'<div style="font-weight:bold;font-size:1.05em;line-height:1.2">{px}</div>'
          f'<div style="font-size:0.85em;line-height:1.2">{chg}</div>')
    return (f'<tr><td>{sc}</td><td>{pc}</td><td>{lo_s}</td>'
            f'<td>{t["kd_s"]}</td><td>{t["macd_s"]}</td><td>{t["rsi"]}</td><td>{t["strategy"]}</td></tr>\n')


# ═══════════════════════════ ⚙️ MAIN ═══════════════════════════
def main():
    print("=" * 60)
    print("  🦞 ta_strategy_engine — 量化核心引擎")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    t0 = datetime.now()

    # 1. 爬富邦排行
    fubon_stocks = fetch_fubon_top20()
    if not fubon_stocks:
        fubon_stocks = [("2330", "台積電"), ("2317", "鴻海"), ("2454", "聯發科")]

    # 2. 大盤檢查
    strict_mode = check_market_below_20ma()

    # 3. Shioaji 登入
    api = login_shioaji()
    if api is None:
        print("❌ Shioaji 登入失敗")
        return

    try:
        # 4. 分析所有股票
        all_ids = list(dict.fromkeys(CORE_IDS + [s[0] for s in fubon_stocks]))
        results = analyze_stocks(api, all_ids, strict_mode)

        # 5. 分核心/潛力
        core = {s: results[s] for s in CORE_IDS if s in results}
        pot = {s: results[s] for s in [s[0] for s in fubon_stocks]
               if s not in CORE_IDS and s in results}

        # 6. 輸出 JSON
        save_signal_json(results)

        # 7. 輸出 HTML
        html = generate_html(core, pot, fubon_stocks, strict_mode)
        for p in [os.path.join(WEB_DIR, "index.html"), os.path.join(BASE_DIR, "index.html")]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)

        # 8. 買進提醒
        buys = [(s, t) for s, t in sorted(results.items()) if t and t.get("low_golden")]
        if buys:
            print("\n" + "!" * 50)
            print("  🟢🟢🟢 買進訊號 🟢🟢🟢")
            for s, t in buys:
                print(f"  🔔🔔🔔 {t['name']}({s}) [30分K] K:{t['k']:.0f} RSI:{t['rsi']}")
            print("!" * 50)
        else:
            print("\nℹ️  無低檔金叉")
    finally:
        try:
            api.logout()
        except:
            pass

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\n📄 HTML {len(html)//1024} KB | JSON {os.path.join(OUTPUT_DIR,'today_signal.json')}")
    print(f"⏱️  {elapsed:.0f} 秒")
    print("📌 全部 30分K | TA-Lib | 0 Token 本機運算")


if __name__ == "__main__":
    main()
