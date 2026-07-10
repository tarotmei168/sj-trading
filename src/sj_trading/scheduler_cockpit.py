#!/usr/bin/env python3
"""
🦞 scheduler_cockpit.py — 小龍蝦排程駕駛艙
==============================================
統一排程入口，08:30 及 16:30 由 Windows 工作排程器觸發，
盤中持續檢查 KD 訊號與投信滲透率變動，自動 Git Push。

使用方式:
    python scheduler_cockpit.py              → 完整晨報模式 (08:30/16:30)
    python scheduler_cockpit.py --monitor    → 純盤中監控模式 (手動啟動)

Windows 排程設定:
    觸發條件: 每日 08:30, 16:30
    動作: python C:\\path\\to\\scheduler_cockpit.py
"""

import os, sys, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from datetime import datetime, timedelta

# ─── 路徑 ─────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))

from intraday_git_pusher import quick_push, push_with_alert

# ─── 狀態檔案 ─────────────────────────────────
TRUST_STATE_FILE = os.path.join(OUTPUT_DIR, 'trust_penetration_state.json')
KD_STATE_FILE = os.path.join(OUTPUT_DIR, 'kd_state.json')
SCHEDULER_LOG = os.path.join(OUTPUT_DIR, 'scheduler.log')


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(SCHEDULER_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


# ══════════════════════════════════════════════
#  晨報產出
# ══════════════════════════════════════════════

def run_morning_report():
    """產出完整晨報 HTML，自動 Git Push"""
    log('🚀 啟動晨報產出...')

    sys.path.insert(0, SCRIPT_DIR)
    if 'daily_web_report' in sys.modules:
        del sys.modules['daily_web_report']
    from daily_web_report import run

    try:
        html = run()  # run() 內部已呼叫 push_to_github()
        log('✅ 晨報完成，已 Git Push')
        return True
    except Exception as e:
        log(f'❌ 晨報失敗: {str(e)[:120]}')
        quick_push('⚠️ 晨報產出異常，強制存檔推送')
        return False


# ══════════════════════════════════════════════
#  投信滲透率監控
# ══════════════════════════════════════════════

def load_trust_state():
    if os.path.exists(TRUST_STATE_FILE):
        try:
            with open(TRUST_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_trust_state(state):
    with open(TRUST_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_trust_change():
    """檢查投信滲透率是否有新增加/變動，回傳 True 如果已推"""
    try:
        from calc_trust_rate import calc_rates
    except ImportError:
        return False

    old_state = load_trust_state()
    new_rates = calc_rates()

    if not new_rates:
        return False

    changes = []
    for sid, data in new_rates.items():
        old_pct = old_state.get(sid, {}).get('p_day', 0) if isinstance(old_state.get(sid), dict) else 0
        new_pct = data.get('p_day', 0)
        diff = new_pct - old_pct
        name = data.get('name', sid)

        if diff > 0.1:
            changes.append(f"{name}({sid}) +{diff:.2f}%")
        elif old_pct == 0 and new_pct > 0.05:
            changes.append(f"{name}({sid}) 新進 {new_pct:.2f}%")

    if changes:
        detail = ' | '.join(changes[:5])
        log(f'🏦 投信滲透率變動: {detail}')
        pushed = push_with_alert('TRUST', detail)
        save_trust_state(new_rates)
        return pushed

    return False


# ══════════════════════════════════════════════
#  KD 訊號監控（15分K）
# ══════════════════════════════════════════════

def load_kd_state():
    if os.path.exists(KD_STATE_FILE):
        try:
            with open(KD_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"notified": []}


def save_kd_state(state):
    with open(KD_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_trading_time(now):
    if now.weekday() >= 5:
        return False
    if now.hour < 8 or now.hour > 13:
        return False
    if now.hour == 13 and now.minute > 35:
        return False
    return True


def kd_monitor_cycle(cycle_limit=999):
    """盤中 KD 監控循環（每 2 分鐘），金叉/死叉觸發 Git Push"""
    try:
        import shioaji as sj
        from dotenv import load_dotenv
        load_dotenv(os.path.join(BASE_DIR, '.env'))
        AK = os.environ.get('SJ_API_KEY', '')
        SK = os.environ.get('SJ_SEC_KEY', '')
        api = sj.Shioaji(simulation=True)
        api.login(api_key=AK, secret_key=SK)
        log('🔌 Shioaji 盤中監控連線成功')
    except Exception as e:
        log(f'❌ Shioaji 盤中連線失敗: {str(e)[:80]}')
        return

    # 核心監控股
    WATCH = {
        "3711": "日月光", "4958": "臻鼎-KY", "3042": "晶技",
        "2337": "旺宏", "2436": "偉詮電", "3673": "TPK-KY",
        "5351": "鈺創", "8150": "南茂",
        "2454": "聯發科", "2317": "鴻海",
    }

    import numpy as np
    kd_state = load_kd_state()
    notified = set(kd_state.get('notified', []))

    cycle = 0
    while cycle < cycle_limit:
        now = datetime.now()
        if not is_trading_time(now):
            log('⏰ 收盤時間到，停止監控')
            break

        for sid, sname in WATCH.items():
            try:
                contract = api.Contracts.Stocks[sid]
                start = now.replace(hour=8, minute=30, second=0, microsecond=0)
                kbars = api.kbars(
                    contract=contract,
                    start=start.strftime('%Y-%m-%d'),
                    end=now.strftime('%Y-%m-%d')
                )
                if not hasattr(kbars, 'Close') or len(kbars.Close) < 20:
                    continue

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
                if cur and (now - cur[1]).seconds < 1800:
                    bars.append(cur)
                if len(bars) < 9:
                    continue

                # 算KD
                cls = np.array([b[2] for b in bars], dtype=float)
                his = np.array([b[3] for b in bars], dtype=float)
                los = np.array([b[4] for b in bars], dtype=float)
                n = len(cls)
                ks = np.zeros(n)
                ds = np.zeros(n)
                ks[0] = 50
                ds[0] = 50
                for i in range(1, n):
                    ps = max(0, i - 9 + 1)
                    hh = np.max(his[ps:i+1])
                    ll = np.min(los[ps:i+1])
                    rsv = (cls[i] - ll) / (hh - ll) * 100 if hh - ll > 0 else 50
                    ks[i] = (2/3) * ks[i-1] + (1/3) * rsv
                    ds[i] = (2/3) * ds[i-1] + (1/3) * ks[i]

                k_now = ks[-1]
                d_now = ds[-1]

                gc = ks[-1] > ds[-1] and ks[-2] <= ds[-2]
                dc = ks[-1] < ds[-1] and ks[-2] >= ds[-2]
                hour_key = now.strftime('%H')

                if gc:
                    sig_key = f"{sid}_gc_{hour_key}"
                    if sig_key not in notified:
                        notified.add(sig_key)
                        detail = f"{sname}({sid}) K={k_now:.1f}>D={d_now:.1f}"
                        log(f'⭐ 15分K 金叉: {detail}')
                        push_with_alert('GC_15K', detail)

                if dc and k_now > 55:
                    sig_key = f"{sid}_dc_{hour_key}"
                    if sig_key not in notified:
                        notified.add(sig_key)
                        detail = f"{sname}({sid}) K={k_now:.1f}<D={d_now:.1f}"
                        log(f'💀 15分K 死叉: {detail}')
                        push_with_alert('DC_15K', detail)

            except Exception:
                continue

        if cycle % 3 == 0:
            check_trust_change()

        if cycle % 15 == 0:
            save_kd_state({"notified": list(notified)})

        cycle += 1
        time.sleep(120)  # 2分鐘

    save_kd_state({"notified": list(notified)})
    try:
        api.logout()
    except:
        pass
    log('📴 KD監控結束')


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "--monitor":
        log('🔍 啟動盤中監控模式 (KD+投信)')
        kd_monitor_cycle()
    elif mode == "--morning":
        run_morning_report()
    else:
        now = datetime.now()
        hour = now.hour

        if 8 <= hour < 9:
            log('🌅 08:30 晨報模式')
            run_morning_report()
            log('📡 啟動盤中監控...')
            kd_monitor_cycle()
        elif 16 <= hour < 17:
            log('🌇 16:30 盤後更新模式')
            run_morning_report()
        elif 9 <= hour <= 13:
            log('📡 盤中純監控模式')
            kd_monitor_cycle()
        else:
            log(f'⏰ 目前時間 {hour}:{now.minute:02d}，非交易時段，不執行')
