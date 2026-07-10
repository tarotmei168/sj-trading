# -*- coding: utf-8 -*-
"""
DayEngine 盤中監控永續迴圈
===========================
每天 09:00 ~ 13:30 每2分鐘檢查一次所有核心持股的15分K金叉/死叉
發現訊號時輸出 NOTIFY: 給外部系統擷取，同時寫入 log 檔
"""
import os, sys, time, json, urllib.request
from datetime import datetime, timedelta
import numpy as np

# ── 載入永豐金 API ──
try:
    from dotenv import load_dotenv
    load_dotenv()
    import shioaji as sj
    AK = os.environ.get('SJ_API_KEY', '')
    SK = os.environ.get('SJ_SEC_KEY', '')
    api = sj.Shioaji(simulation=True)
    api.login(api_key=AK, secret_key=SK)
    API_READY = True
except Exception as e:
    print(f"[FATAL] 永豐API連線失敗: {e}")
    API_READY = False
    api = None

# ── 路徑設定 ──
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE, "output")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "day_signals.log")
HISTORY_FILE = os.path.join(LOG_DIR, "day_signals_history.json")

# ── 監控標的（第1層核心 + 第2層潛力）──
ALL_STOCKS = [
    # 第1層：核心持股
    ("2436", "偉詮電", 1),
    ("2337", "旺宏",   1),
    ("5351", "鈺創",   1),
    ("3673", "TPK-KY", 1),
    ("3711", "日月光", 1),
    ("4958", "臻鼎-KY",1),
    ("3042", "晶技",   1),
    ("2454", "聯發科", 1),
    ("2317", "鴻海",   1),
    # 第2層：潛力股
    ("3443", "創意",   2),
    ("3661", "世芯",   2),
    ("3035", "智原",   2),
    ("3231", "緯創",   2),
    ("2382", "廣達",   2),
    ("3017", "奇鋐",   2),
    ("2451", "創見",   2),
    ("8150", "南茂",   2),
    # 記憶體
    ("2344", "華邦電", 2),
    ("6770", "力積電", 2),
]

# ── 已通知過的訊號（避免重複）──
notified = set()

def load_history():
    """載入歷史訊號記錄"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_history():
    """儲存歷史訊號記錄（只保留今天）"""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(notified), f, ensure_ascii=False)
    except:
        pass

def analyze_15k(sid):
    """用永豐API抓15分K，回傳KD狀態"""
    if not API_READY or not api:
        return None
    
    now = datetime.now()
    start = now.replace(hour=8, minute=30, second=0, microsecond=0)
    
    try:
        contract = api.Contracts.Stocks[sid]
        kbars = api.kbars(contract=contract, start=start.strftime('%Y-%m-%d'), end=now.strftime('%Y-%m-%d'))
        if not hasattr(kbars, 'Close') or len(kbars.Close) < 50:
            return None
        
        # 組15分K棒
        bars = []
        cur = None
        for i in range(len(kbars.Close)):
            t = datetime.fromtimestamp(kbars.ts[i] / 1e9)
            slot = t.hour * 60 + t.minute
            sn = (slot // 15) * 15
            key = t.strftime('%Y%m%d') + f'{sn:03d}'
            c = float(kbars.Close[i])
            h = float(kbars.High[i])
            l = float(kbars.Low[i])
            
            if cur is None or cur[0] != key:
                if cur:
                    bars.append(cur)
                cur = [key, t, c, h, l, c]
            else:
                cur[3] = max(cur[3], h)
                cur[4] = min(cur[4], l)
                cur[5] = c
        
        if cur and (datetime.now() - cur[1]).seconds < 1800:
            bars.append(cur)
        
        if len(bars) < 9:
            return None
        
        # 算KD 9/3
        cls = np.array([b[2] for b in bars], dtype=float)
        his = np.array([b[3] for b in bars], dtype=float)
        los = np.array([b[4] for b in bars], dtype=float)
        n = len(cls)
        k = np.zeros(n)
        d = np.zeros(n)
        k[0] = 50
        d[0] = 50
        
        for i in range(1, n):
            ps = max(0, i - 9 + 1)
            hh = np.max(his[ps:i+1])
            ll = np.min(los[ps:i+1])
            rsv = (cls[i] - ll) / (hh - ll) * 100 if hh - ll > 0 else 50
            k[i] = (2/3) * k[i-1] + (1/3) * rsv
            d[i] = (2/3) * d[i-1] + (1/3) * k[i]
        
        # 算RSI(14) — 用最近30根K棒
        rsi_n = min(30, n)
        rsi_cls = cls[-rsi_n:]
        gains = 0; losses = 0
        for i in range(1, len(rsi_cls)):
            diff = rsi_cls[i] - rsi_cls[i-1]
            if diff > 0: gains += diff
            else: losses += abs(diff)
        p = 14
        avg_gain = gains / p
        avg_loss = losses / p
        rsi_val = round(100 - 100 / (1 + avg_gain/avg_loss), 1) if avg_loss > 0 else 100.0
        
        return {
            "price": cls[-1],
            "k": k[-1],
            "d": d[-1],
            "rsi": rsi_val,
            "k_up": k[-1] > d[-1],
            "gc": bool(k[-1] > d[-1] and k[-2] <= d[-2]),
            "dc": bool(k[-1] < d[-1] and k[-2] >= d[-2]),
            "low_today": min(los),
            "high_today": max(his),
        }
    except Exception as e:
        return None

def check_once():
    """執行一次全面檢查，回傳所有訊號"""
    signals = []
    now_ts = datetime.now().strftime("%H:%M")
    
    for sid, sname, layer in ALL_STOCKS:
        r = analyze_15k(sid)
        if r is None:
            continue
        
        # 黃金交叉
        if r["gc"]:
            key = f"{sid}_gc_{now_ts[:2]}"
            if key not in notified:
                notified.add(key)
                signals.append({
                    "type": "GC",
                    "sid": sid,
                    "name": sname,
                    "layer": layer,
                    "price": r["price"],
                    "k": round(r["k"], 1),
                    "d": round(r["d"], 1),
                    "rsi": round(r["rsi"], 1),
                    "time": now_ts,
                })
        
        # 死亡交叉
        if r["dc"] and r["k"] > 60:  # 高檔死叉才通知
            key = f"{sid}_dc_{now_ts[:2]}"
            if key not in notified:
                notified.add(key)
                signals.append({
                    "type": "DC",
                    "sid": sid,
                    "name": sname,
                    "layer": layer,
                    "price": r["price"],
                    "k": round(r["k"], 1),
                    "d": round(r["d"], 1),
                    "rsi": round(r["rsi"], 1),
                    "time": now_ts,
                })
    
    # 提前預警：K即將突破D（差距<1且K在上升）
    for sid, sname, layer in ALL_STOCKS:
        r = analyze_15k(sid)
        if r is None:
            continue
        # 如果K<D但差距小於1，且K在往上走 → 即將金叉
        if not r["k_up"] and (r["d"] - r["k"]) < 1.0:
            key = f"{sid}_pre_gc_{datetime.now().strftime('%H')}"
            if key not in notified:
                notified.add(key)
                signals.append({
                    "type": "PRE_GC",
                    "sid": sid,
                    "name": sname,
                    "layer": layer,
                    "price": r["price"],
                    "k": round(r["k"], 1),
                    "d": round(r["d"], 1),
                    "rsi": round(r["rsi"], 1),
                    "time": datetime.now().strftime("%H:%M"),
                })
        # 如果K>D但差距小於1，且K在往下走 → 即將死叉
        if r["k_up"] and (r["k"] - r["d"]) < 1.0:
            key = f"{sid}_pre_dc_{datetime.now().strftime('%H')}"
            if key not in notified:
                notified.add(key)
                signals.append({
                    "type": "PRE_DC",
                    "sid": sid,
                    "name": sname,
                    "layer": layer,
                    "price": r["price"],
                    "k": round(r["k"], 1),
                    "d": round(r["d"], 1),
                    "rsi": round(r["rsi"], 1),
                    "time": datetime.now().strftime("%H:%M"),
                })
    
    return signals

NOTIFY_MAJOR = {"GC", "DC"}  # 買賣訊號要發4次
NOTIFY_PRE = {"PRE_GC", "PRE_DC"}  # 提前預警也要發4次

def format_signal(sig):
    """格式化訊號文字（含RSI）"""
    layer_str = "🔒核心" if sig["layer"] == 1 else "🎯潛力"
    rsi_str = f"RSI:{sig['rsi']:.0f}"
    if sig["type"] == "GC":
        return f"⭐金叉 {sig['sid']} {sig['name']} P={sig['price']:.0f} K={sig['k']:.1f}>D={sig['d']:.1f} {rsi_str} {layer_str}"
    elif sig["type"] == "DC":
        return f"💀死叉 {sig['sid']} {sig['name']} P={sig['price']:.0f} K={sig['k']:.1f}<D={sig['d']:.1f} {rsi_str} {layer_str}"
    elif sig["type"] == "PRE_GC":
        return f"⏰預警 {sig['sid']} {sig['name']} P={sig['price']:.0f} K={sig['k']:.1f}即將突破D={sig['d']:.1f} {rsi_str} {layer_str}"
    else:
        return f"⏰預警 {sig['sid']} {sig['name']} P={sig['price']:.0f} K={sig['k']:.1f}即將跌破D={sig['d']:.1f} {rsi_str} {layer_str}"

def is_trading_time(now):
    """判斷是否在交易時間內"""
    if now.weekday() >= 5:
        return False
    if now.hour < 8 or now.hour > 13:
        return False
    if now.hour == 13 and now.minute > 35:
        return False
    return True


# ════════════════════════════════════════
#  主迴圈
# ════════════════════════════════════════
def main():
    global notified
    notified = load_history()
    
    now = datetime.now()
    
    # 非交易時間直接結束
    if not is_trading_time(now):
        print(f"[{now.strftime('%H:%M')}] 非交易時間，不啟動監控")
        if API_READY and api:
            api.logout()
        return
    
    print(f"[{now.strftime('%H:%M')}] DayMonitor 啟動 — 監控 {len(ALL_STOCKS)} 檔, 每2分鐘檢查一次")
    print(f"[{now.strftime('%H:%M')}] log: {LOG_FILE}")
    
    cycle = 0
    while True:
        now = datetime.now()
        
        # 時間到停止
        if not is_trading_time(now):
            print(f"[{now.strftime('%H:%M')}] 收盤，監控停止")
            break
        
        signals = check_once()
        
        for sig in signals:
            msg = format_signal(sig)
            # 寫log
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{now.strftime('%H:%M:%S')} {msg}\n")
            # 輸出給外部擷取
            # 買賣訊號和預警發4次，其他發1次
            repeat = 4 if sig["type"] in NOTIFY_MAJOR or sig["type"] in NOTIFY_PRE else 1
            for _ in range(repeat):
                print(f"NOTIFY:{msg}", flush=True)
        
        cycle += 1
        if cycle % 15 == 0:  # 每半小時存一次
            save_history()
        
        time.sleep(120)  # 2分鐘
    
    save_history()
    if API_READY and api:
        api.logout()
    print(f"[{datetime.now().strftime('%H:%M')}] DayMonitor 正常結束")

if __name__ == "__main__":
    main()
