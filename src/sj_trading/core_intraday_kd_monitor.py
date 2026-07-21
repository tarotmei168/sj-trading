#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦞 核心11檔 30分K KD 盤中即時監控 ⚠️ WeChat 通知版
=========================================================
使用本地 database/30min_kd/*_kd.csv 歷史KD資料，
盤中每5分鐘掃一次，偵測30分K KD黃金/死亡交叉。

通知規則：
  - 只發送黃金交叉（K穿D）和死亡交叉（K跌破D）
  - 每個交叉事件連續發 3 次 WeChat 訊息（間隔1秒）
  - 逼近金叉/逼近死叉不發 WeChat，僅顯示在控制台
  - 平常完全不發 → 避免封號

用法：
  python src/sj_trading/core_intraday_kd_monitor.py          # 一次性掃描
  python src/sj_trading/core_intraday_kd_monitor.py --loop   # 每5分鐘循環
"""

import os, sys, json, time, argparse
from datetime import datetime, timedelta, date
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from dotenv import load_dotenv
import shioaji as sj

load_dotenv()

# ── 核心持股11檔（與 download_intraday_kd_data.py 一致）──
CORE_STOCKS = {
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "3711": "日月光", "4958": "臻鼎-KY",
    "3042": "晶技",   "2454": "聯發科", "2317": "鴻海",
    "8150": "南茂",   "2330": "台積電",
}

BASE_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BASE_DIR / "database" / "30min_kd"
OUTPUT_DIR = BASE_DIR / "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALERTS_FILE = OUTPUT_DIR / "core_kd_alerts.json"

# ── WeChat 通知設定 ──
WECHAT_TARGET = None  # 由 send_wechat_alert() 自動從 message 工具發送
WECHAT_CHANNEL = "openclaw-weixin"


# ═══════════════════════════════════════════════════════
#  載入歷史KD
# ═══════════════════════════════════════════════════════

def load_kd_history(sid: str) -> pd.DataFrame | None:
    """載入本地 30分K KD 歷史資料"""
    path = DB_DIR / f"{sid}_kd.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, parse_dates=["datetime"])
        df.sort_values("datetime", inplace=True)
        return df
    except Exception as e:
        return None


# ═══════════════════════════════════════════════════════
#  Shioaji 登入 + 即時1分K
# ═══════════════════════════════════════════════════════

def login():
    api_key = os.environ.get("SJ_API_KEY")
    sec_key = os.environ.get("SJ_SEC_KEY")
    if not api_key or not sec_key:
        return None
    api = sj.Shioaji(simulation=True)
    api.login(api_key=api_key, secret_key=sec_key, contracts_timeout=10000)
    return api


def fetch_today_1min(api, sid: str) -> pd.DataFrame | None:
    """抓今天（或最近2天）的1分K"""
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        return None

    today = datetime.now()
    start = today - timedelta(days=2)  # 多抓一天確保有跨日
    start_str = start.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    try:
        kbars = api.kbars(contract=contract, start=start_str, end=end_str)
        if kbars is None or len(getattr(kbars, 'ts', [])) == 0:
            return None
        df = pd.DataFrame({
            "datetime": pd.to_datetime(kbars.ts),
            "open": [float(x) for x in kbars.Open],
            "high": [float(x) for x in kbars.High],
            "low": [float(x) for x in kbars.Low],
            "close": [float(x) for x in kbars.Close],
            "volume": [float(x) for x in kbars.Volume],
        })
        return df
    except:
        return None


# ═══════════════════════════════════════════════════════
#  30分K即時更新 + KD計算
# ═══════════════════════════════════════════════════════

def resample_30min(min1_df: pd.DataFrame) -> pd.DataFrame:
    """將1分K合併成30分K"""
    if min1_df is None or min1_df.empty:
        return pd.DataFrame()

    df = min1_df.copy()
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    # 過濾盤中時間
    df = df.between_time("08:45", "13:31")

    resampled = df.resample("30min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    resampled = resampled[resampled["volume"] > 0]
    resampled.reset_index(inplace=True)
    return resampled


def compute_kd(df: pd.DataFrame, k_period: int = 9) -> pd.DataFrame:
    """計算KD"""
    if df is None or df.empty or len(df) < k_period + 3:
        return df

    close = df["close"].values
    low_min = pd.Series(df["low"].values).rolling(k_period).min().values
    high_max = pd.Series(df["high"].values).rolling(k_period).max().values
    denom = high_max - low_min
    rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50.0)

    n = len(close)
    k_vals = np.full(n, 50.0)
    d_vals = np.full(n, 50.0)
    for i in range(k_period, n):
        k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
        d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
        k_vals[i] = k_new
        d_vals[i] = d_new

    df = df.copy()
    df["K"] = np.round(k_vals, 2)
    df["D"] = np.round(d_vals, 2)
    return df


# ═══════════════════════════════════════════════════════
#  核心分析
# ═══════════════════════════════════════════════════════

def analyze_stock(api, sid: str, name: str) -> dict:
    """
    分析一檔股票的30分K KD即時狀態。
    步驟：
    1. 載入本地歷史 KD（已有完整K/D值）
    2. 抓今天1分K，合成最新的30分K
    3. 用歷史KD的後段 + 最新1根，重算KD確保連續性
    4. 判斷交叉/逼近狀態
    """
    # 載入歷史
    hist = load_kd_history(sid)
    if hist is None or hist.empty:
        return {"sid": sid, "name": name, "error": "無歷史KD資料", "status": "NO_DATA"}

    # 抓即時1分K
    today_1min = fetch_today_1min(api, sid)
    if today_1min is None or today_1min.empty:
        return {"sid": sid, "name": name, "error": "無法取得即時資料", "status": "NO_DATA"}

    # 合併成30分K
    today_30min = resample_30min(today_1min)
    if today_30min.empty:
        return {"sid": sid, "name": name, "error": "即時30分K為空", "status": "NO_DATA"}

    # 取歷史的最後9根（用來維持KD連續性）+
    last_hist_ts = hist["datetime"].max() if not hist.empty else None
    # 取最近的歷史段：取最後20根 + 今天的即時段
    hist_tail = hist.tail(30)  # 取30根確保足夠

    # 合併歷史尾段 + 今天即時30分K
    combined = pd.concat([hist_tail, today_30min], ignore_index=True)
    combined.drop_duplicates(subset=["datetime"], inplace=True)
    combined.sort_values("datetime", inplace=True)
    combined.reset_index(drop=True, inplace=True)

    # 重算KD（確保用同一套邏輯）
    combined = compute_kd(combined, k_period=9)
    combined = combined.dropna(subset=["K", "D"])

    if len(combined) < 5:
        return {"sid": sid, "name": name, "error": "KD資料不足", "status": "NO_DATA"}

    # ── 取最後3根判斷狀態 ──
    last3 = combined.tail(3)
    last_row = last3.iloc[-1]
    prev_row = last3.iloc[-2]

    k_now = round(last_row["K"], 1)
    d_now = round(last_row["D"], 1)
    k_prev = round(prev_row["K"], 1)
    d_prev = round(prev_row["D"], 1)
    close_now = round(last_row["close"], 2)
    ts_now = last_row["datetime"]
    ts_str = pd.to_datetime(ts_now).strftime("%m/%d %H:%M")

    # K值趨勢
    k3 = last3["K"].values
    k_trend_up = k3[-1] > k3[-2] > k3[-3]   # 連續3根往上
    k_up = k_now > k_prev                     # 這根往上

    kd_gap = round(d_now - k_now, 1)

    # ── 判斷 ──
    result = {
        "sid": sid, "name": name,
        "datetime": ts_str,
        "price": close_now,
        "K": k_now, "D": d_now,
        "kd_gap": kd_gap,
        "K_prev": k_prev, "D_prev": d_prev,
        "k_up": k_up,
        "k_trend_up": k_trend_up,
        "status": "NORMAL",
        "signal": None,
        "message": "",
    }

    # === 狀況1：正式黃金交叉（K穿D）===
    if k_prev <= d_prev and k_now > d_now:
        result["status"] = "GOLDEN_CROSS"
        result["signal"] = "BUY"
        result["message"] = f"🔴 {name}({sid}) 30分K KD黃金交叉確認！K={k_now}穿D={d_now} @{close_now}"
        return result

    # === 狀況2：正式死亡交叉（K跌破D）===
    if k_prev >= d_prev and k_now < d_now:
        result["status"] = "DEATH_CROSS"
        result["signal"] = "SELL"
        result["message"] = f"🟢 {name}({sid}) 30分K KD死亡交叉確認！K={k_now}跌破D={d_now} @{close_now}"
        return result

    # === 狀況3：逼近金叉（K<D 但差距≤3 且 K往上追）===
    if k_now < d_now and kd_gap <= 3.0 and k_up:
        result["status"] = "APPROACHING_GOLDEN"
        result["signal"] = "WATCH_BUY"
        result["message"] = f"💡 {name}({sid}) ⚠️逼近金叉! K={k_now} D={d_now} 差距={kd_gap} K往上追 @{close_now}"
        return result

    # === 狀況4：逼近死叉（K>D 但差距≤3 且 K往下掉）===
    if k_now > d_now and kd_gap >= -3.0 and not k_up:
        result["status"] = "APPROACHING_DEATH"
        result["signal"] = "WATCH_SELL"
        result["message"] = f"⚠️ {name}({sid}) 逼近死叉! K={k_now} D={d_now} 差距={abs(kd_gap)} K往下掉 @{close_now}"
        return result

    # === 狀況5：金叉持倉中 ===
    if k_now > d_now:
        result["status"] = "IN_GOLDEN"
        result["signal"] = "HOLD"
        return result

    # === 狀況6：死叉持倉中 ===
    result["status"] = "IN_DEATH"
    result["signal"] = "WAIT"
    return result


# ═══════════════════════════════════════════════════════
#  Alert 管理（避免重複發送）
# ═══════════════════════════════════════════════════════

def load_alerts() -> dict:
    if ALERTS_FILE.exists():
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_alerts(alerts: dict):
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


def should_alert(sid: str, status: str, alerts: dict) -> bool:
    """檢查是否已經發過同樣的警報（避免重複）"""
    key = sid
    if key not in alerts:
        alerts[key] = {"last_status": "", "last_ts": 0}
    last = alerts[key]
    # 同一個狀態不重複，除非超過30分鐘
    cooldown = 1800  # 30分鐘
    now_ts = int(time.time())
    if last["last_status"] == status and (now_ts - last["last_ts"]) < cooldown:
        return False
    last["last_status"] = status
    last["last_ts"] = now_ts
    return True


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def scan_once():
    """執行一次掃描（用於cron或一次性觸發）"""
    now = datetime.now()
    print(f"\n{'='*65}")
    print(f"  🦞 核心11檔 30分K KD 即時掃描")
    print(f"  時間: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    api = login()
    if api is None:
        print("❌ 無法登入 Shioaji")
        return

    alerts = load_alerts()
    new_alerts = []

    results = []
    for sid, name in CORE_STOCKS.items():
        result = analyze_stock(api, sid, name)
        results.append(result)

        # 顯示狀態
        if result.get("error"):
            print(f"  ⚠️ {name}({sid}): {result['error']}")
        elif result["status"] == "GOLDEN_CROSS":
            print(f"  🔴 {name}({sid}) K={result['K']} 穿 D={result['D']} ✅ 黃金交叉 @{result['price']}!")
            if should_alert(sid, "GOLDEN_CROSS", alerts):
                new_alerts.append(result)
        elif result["status"] == "DEATH_CROSS":
            print(f"  🟢 {name}({sid}) K={result['K']} 跌破 D={result['D']} ❌ 死亡交叉 @{result['price']}!")
            if should_alert(sid, "DEATH_CROSS", alerts):
                new_alerts.append(result)
        elif result["status"] == "APPROACHING_GOLDEN":
            print(f"  💡 {name}({sid}) ⚠️逼近金叉! K={result['K']} D={result['D']} 差距={result['kd_gap']} @{result['price']}")
            if should_alert(sid, "APPROACHING_GOLDEN", alerts):
                new_alerts.append(result)
        elif result["status"] == "APPROACHING_DEATH":
            print(f"  ⚠️ {name}({sid}) 逼近死叉! K={result['K']} D={result['D']} @{result['price']}")
            if should_alert(sid, "APPROACHING_DEATH", alerts):
                new_alerts.append(result)
        elif result["status"] == "IN_GOLDEN":
            print(f"  🟢 {name}({sid}) K={result['K']} > D={result['D']} 金叉維持中")
        elif result["status"] == "IN_DEATH":
            print(f"  🔴 {name}({sid}) K={result['K']} < D={result['D']} 死叉維持中")
        else:
            print(f"  ⚪ {name}({sid}) K={result['K']} D={result['D']} 無信號")

    save_alerts(alerts)
    api.logout()

    # 重點彙總 + WeChat 發送（只發黃金交叉和死亡交叉，連續3次）
    if new_alerts:
        print(f"\n{'='*65}")
        print(f"  ⚠️ 新觸發 {len(new_alerts)} 個警報!")
        print(f"{'='*65}")
        for a in new_alerts:
            msg = a['message']
            print(f"  {msg}")
            
            # 只對正式交叉發 WeChat（逼近不發），連續3次
            if a["status"] in ("GOLDEN_CROSS", "DEATH_CROSS"):
                send_wechat_alert(msg, repeat=3, delay=1)

    print(f"\n{'='*65}")
    print(f"  掃描完成\n")

    return results


def loop_mode(interval_minutes: int = 5):
    """循環監控模式（每 N 分鐘掃描一次）"""
    print(f"🦞 核心11檔 30分K KD 循環監控啟動")
    print(f"  掃描間隔: {interval_minutes} 分鐘")
    print(f"  ⌛ 等待第一根30分K完成...\n")

    while True:
        now = datetime.now()
        minute = now.minute
        second = now.second

        # 只在盤中時間執行 (09:00~13:30)
        hour = now.hour
        if hour < 9 or (hour == 9 and minute == 0 and second < 30):
            # 還沒開盤
            next_run = now.replace(hour=9, minute=0, second=0) + timedelta(minutes=interval_minutes)
            wait = (next_run - now).total_seconds()
            if wait > 0:
                time.sleep(wait)
            continue
        if hour > 13 or (hour == 13 and minute >= 31):
            # 盤後
            next_run = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
            wait = (next_run - now).total_seconds()
            print(f"  💤 盤後休息，下次執行: {next_run.strftime('%m/%d %H:%M')}")
            time.sleep(min(wait, 3600))
            continue

        # 執行掃描
        scan_once()

        # 等待下一個間隔
        next_scan = now + timedelta(minutes=interval_minutes)
        wait_seconds = (next_scan - datetime.now()).total_seconds()
        if wait_seconds > 0:
            time.sleep(wait_seconds)


# ═══════════════════════════════════════════════════════
#  WeChat 發送
# ═══════════════════════════════════════════════════════

def send_wechat_alert(message: str, repeat: int = 3, delay: int = 1):
    """
    透過 OpenClaw message tool 發送 WeChat 通知。
    連續發 repeat 次，每次間隔 delay 秒。
    channel = openclaw-weixin
    """
    import subprocess, json, sys as _sys

    for i in range(repeat):
        try:
            # 用 openclaw msg 命令發送
            cmd = [
                "openclaw", "msg", "--channel", WECHAT_CHANNEL,
                "--target", "me", message
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"  📱 WeChat 第{i+1}次發送成功")
            else:
                print(f"  ⚠️ WeChat 第{i+1}次發送失敗: {result.stderr[:100]}")
        except Exception as e:
            print(f"  ⚠️ WeChat 第{i+1}次發送異常: {e}")
        
        if i < repeat - 1:
            time.sleep(delay)


# ═══════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="核心11檔30分K KD即時監控")
    parser.add_argument("--loop", action="store_true", help="循環監控模式")
    parser.add_argument("--interval", type=int, default=5, help="掃描間隔（分鐘，預設5）")
    args = parser.parse_args()

    # 檢查歷史KD資料是否存在
    missing = []
    for sid in CORE_STOCKS:
        if not (DB_DIR / f"{sid}_kd.csv").exists():
            missing.append(sid)
    if missing:
        print(f"❌ 缺少歷史KD資料: {', '.join(missing)}")
        print(f"   請先執行: python src/sj_trading/download_intraday_kd_data.py")
        sys.exit(1)

    if args.loop:
        loop_mode(args.interval)
    else:
        scan_once()
