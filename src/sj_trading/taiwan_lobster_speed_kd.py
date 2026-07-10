"""
🦞 taiwan_lobster_speed_kd.py
30分K KD極速預警大腦
────────────────────────────
核心能力：提前 3~5 分鐘通知「即將黃金交叉 / 即將死亡交叉」
不是等交叉才通知，而是用斜率+速度+距離來預判

低檔金叉預警（第25~27分鐘）：
  - KD處於低檔(K≤30)
  - K線下挫力道消失 → 斜率由負轉正
  - K線與D線距離縮小到接近0
  - → 小龍蝦語音：「注意！XXX快要黃金交叉！準備低接！」

高檔死叉預警（第25~27分鐘）：
  - KD處於高檔(K≥70)
  - K線上衝動能減弱 → 斜率明顯下降
  - K線與D線距離極度縮小
  - → 小龍蝦語音：「注意！XXX快要死交了！準備賣出！」

真正的交叉確認（第30分鐘）：
  - K正式穿D → 「🔴 買入！買入！」
  - K正式跌破D → 「🟢 趕快賣出！趕快賣出！」
"""
import os, sys, json, time, math
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', buffering=1)
load_dotenv()

# ============================================================
# 設定
# ============================================================
WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "watchlist.txt")
SIGNAL_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "lobster_alert_states.json")
APPROACHING_LOG = os.path.join(os.path.dirname(__file__), "..", "..", "lobster_approaching_log.json")

# 預警參數
SLOPE_WINDOW = 3          # 用最近3根30分K算斜率
PREMATURE_DISTANCE = 1.5  # K與D差距 < 1.5 視為「即將交叉」
EXHAUSTION_THRESHOLD = 2  # 斜率下降超過2 = 動能衰竭
UPWARD_SLOPE_MIN = 0.5    # 斜率向上 > 0.5 = 往上拐

# ============================================================
# 讀取自選清單
# ============================================================
def load_watchlist():
    """從 watchlist.txt 讀取所有股票（庫存+觀察），全掃"""
    stocks = []
    if not os.path.exists(WATCHLIST_PATH):
        return stocks
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                sid = parts[0]
                name = parts[1]
                kp = int(parts[2]) if len(parts) > 2 and parts[2] else 9
                buy_th = int(parts[3]) if len(parts) > 3 and parts[3] else None
                sell_th = int(parts[4]) if len(parts) > 4 and parts[4] else None
                stocks.append((sid, name, kp, buy_th, sell_th))
    return stocks

ALL_STOCKS = load_watchlist()

# ============================================================
# Shioaji 登入 + 抓資料
# ============================================================
def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_30min_k(api, sid, days_back=20):
    """
    抓 days_back 天的1分K，合併為30分K，只保留交易時間 09:00~13:30
    確保有足夠歷史算KD + 斜率
    """
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        return None

    end = datetime.now()
    start = end - timedelta(days=days_back)

    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        try:
            kbars = api.kbars(
                contract=contract,
                start=seg_start.strftime("%Y-%m-%d"),
                end=seg_end.strftime("%Y-%m-%d")
            )
            if len(kbars.ts) == 0:
                seg_end = seg_start - timedelta(seconds=1)
                continue
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open, "high": kbars.High,
                "low": kbars.Low, "close": kbars.Close,
                "volume": kbars.Volume,
            })
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except:
            break

    if not all_dfs:
        return None

    raw = pd.concat(all_dfs)
    raw.drop_duplicates(subset=["datetime"], inplace=True)
    raw.sort_values("datetime", inplace=True)
    raw.set_index("datetime", inplace=True)

    # 合併30分K
    df_30 = raw.resample("30min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    df_30 = df_30.between_time("09:00", "13:30")
    if len(df_30) < 20:
        return None
    return df_30


# ============================================================
# KD計算（支援自訂K值）
# ============================================================
def compute_kd(df, k_period):
    """給定 DataFrame + K值，回傳帶有 K/D 欄位的 DataFrame"""
    close = df["close"].values
    low = df["low"].values
    high = df["high"].values
    n = len(close)

    low_min = pd.Series(low).rolling(k_period).min().values
    high_max = pd.Series(high).rolling(k_period).max().values
    denom = high_max - low_min
    rsv = np.where(denom != 0, ((close - low_min) / denom) * 100, 50.0)

    k_vals = np.full(n, 50.0)
    d_vals = np.full(n, 50.0)

    for i in range(k_period, n):
        k_new = (2/3) * k_vals[i-1] + (1/3) * rsv[i]
        d_new = (2/3) * d_vals[i-1] + (1/3) * k_new
        k_vals[i] = k_new
        d_vals[i] = d_new

    df = df.copy()
    df["K"] = k_vals
    df["D"] = d_vals
    return df


# ============================================================
# 核心：斜率 + 速度 + 距離分析
# ============================================================
def compute_slope(series, window=SLOPE_WINDOW):
    """
    用最小平方法算最近 window 根的斜率
    正值 = 向上，負值 = 向下
    """
    if len(series) < window:
        return 0.0
    recent = series[-window:].values
    x = np.arange(window)
    if np.std(recent) == 0:
        return 0.0
    slope = np.polyfit(x, recent, 1)[0]
    return slope


def analyze_stock_advanced(api, sid, name, k_period, buy_threshold, sell_threshold):
    """
    完整分析一檔股票：
    1. 計算KD
    2. 計算K線斜率（速度）
    3. 判斷交叉狀態
    4. 判斷即將交叉（提前預警）
    5. 判斷交叉確認
    """
    try:
        df = fetch_30min_k(api, sid)

        if df is None or len(df) < k_period + 5:
            return None

        df = compute_kd(df, k_period)
        df = df.dropna(subset=["K", "D"])
        if len(df) < 8:
            return None

        # ---------- 核心數據 ----------
        last5 = df.tail(5)
        last = last5.iloc[-1]
        prev = last5.iloc[-2]

        k_now = round(last["K"], 2)
        d_now = round(last["D"], 2)
        k_prev = round(prev["K"], 2)
        d_prev = round(prev["D"], 2)
        close_now = round(last["close"], 2)
        time_label = last.name.strftime("%H:%M")

        # K線斜率（最近3根）
        k_series = df["K"].tail(SLOPE_WINDOW + 1).iloc[:-1]  # 不含當前
        k_slope = round(compute_slope(k_series), 2)
        d_slope = round(compute_slope(df["D"].tail(SLOPE_WINDOW + 1).iloc[:-1]), 2)

        # 前一個斜率（用來判斷轉折）
        k_slope_prev_series = df["K"].tail(SLOPE_WINDOW + 2).iloc[:-2]
        k_slope_prev = round(compute_slope(k_slope_prev_series), 2)

        # K-D 距離
        kd_distance = round(abs(k_now - d_now), 2)
        kd_distance_prev = round(abs(k_prev - d_prev), 2)
        distance_shrinking = kd_distance < kd_distance_prev  # 距離在縮小

        # K值動能變化（前一根K vs 當前K）
        k_diff = round(k_now - k_prev, 2)
        k_diff_prev = round(k_prev - df.tail(5).iloc[-3]["K"], 2)
        momentum_fading = abs(k_diff) < abs(k_diff_prev)  # 動能減弱

        # ========== 判斷區域 ==========
        zone = "NORMAL"
        if k_now <= 30:
            zone = "OVERSOLD_LOW"    # 低檔超賣區
        elif k_now >= 70:
            zone = "OVERBOUGHT_HIGH" # 高檔超買區
        elif k_now >= 85:
            zone = "EXTREME_HIGH"    # 極高檔

        # ========== 交叉狀態 ==========
        is_golden_now = k_now > d_now       # 目前金叉狀態
        is_death_now = k_now < d_now        # 目前死叉狀態
        golden_cross_just_now = k_prev <= d_prev and k_now > d_now  # 這根剛金叉
        death_cross_just_now = k_prev >= d_prev and k_now < d_now   # 這根剛死叉

        # ========== 提前預警邏輯 ==========
        pre_golden_alert = False
        pre_death_alert = False
        alert_reason = ""

        # ---------- 低檔金叉預警（第25~27分鐘） ----------
        if zone in ("OVERSOLD_LOW",):
            # 條件1: K線斜率由負轉正（往上拐）或已明顯上升
            k_turning_up = k_slope > UPWARD_SLOPE_MIN and k_slope_prev <= 0
            # 條件2: K與D距離縮小中
            close_to_cross = kd_distance < PREMATURE_DISTANCE and distance_shrinking
            # 條件3: 目前還是K<D（還沒正式交叉）
            still_death = k_now <= d_now
            # 條件4（輔助）: K值不再往下掉
            k_stable = k_diff >= -0.3

            if k_turning_up and close_to_cross and still_death and k_stable:
                pre_golden_alert = True
                alert_reason = "低檔金叉預警"

        # ---------- 高檔死叉預警（第25~27分鐘） ----------
        if zone in ("OVERBOUGHT_HIGH", "EXTREME_HIGH"):
            # 條件1: K線斜率正在下降（動能衰竭）
            k_fading = k_slope < k_slope_prev and momentum_fading
            k_slope_down = k_slope < UPWARD_SLOPE_MIN
            # 條件2: K與D距離極度縮小
            close_to_death = kd_distance < PREMATURE_DISTANCE and distance_shrinking
            # 條件3: 目前還是K>D（還沒正式交叉）
            still_golden = k_now >= d_now

            if (k_fading or k_slope_down) and close_to_death and still_golden:
                pre_death_alert = True
                alert_reason = "高檔死叉預警"

        # ========== 彙整結果 ==========
        result = {
            "sid": sid,
            "name": name,
            "k_period": k_period,
            "buy_th": buy_threshold,
            "sell_th": sell_threshold,
            "timestamp": time_label,
            "price": close_now,
            "K": k_now,
            "D": d_now,
            "K_slope": k_slope,
            "D_slope": d_slope,
            "K_slope_prev": k_slope_prev,
            "K_diff": k_diff,
            "K_diff_prev": k_diff_prev,
            "KD_distance": kd_distance,
            "KD_distance_prev": kd_distance_prev,
            "distance_shrinking": distance_shrinking,
            "momentum_fading": momentum_fading,
            "zone": zone,
            "is_golden": is_golden_now,
            "is_death": is_death_now,
            "golden_cross_just_now": golden_cross_just_now,
            "death_cross_just_now": death_cross_just_now,
            "pre_golden_alert": pre_golden_alert,
            "pre_death_alert": pre_death_alert,
            "alert_reason": alert_reason,
        }

        return result

    except Exception as e:
        return None


# ============================================================
# 語音提醒訊息
# ============================================================
def build_alert_message(result):
    """根據分析結果，生成語音/文字提醒"""
    sid = result["sid"]
    name = result["name"]
    k = result["K"]
    d = result["D"]
    price = result["price"]
    slope = result["K_slope"]
    kd_dist = result["KD_distance"]
    zone = result["zone"]

    if result["golden_cross_just_now"]:
        # ===== 真正的黃金交叉確認（第30分鐘） =====
        return (
            f"🔴 買入！買入！\n"
            f"━━━━━━━━━━━━━\n"
            f"{name}({sid}) @{price}\n"
            f"30分K KD黃金交叉確認！\n"
            f"K={k:.1f} 正式穿 D={d:.1f}\n"
            f"━━━━━━━━━━━━━\n"
            f"小龍蝦即時亮燈：買入訊號！"
        )

    if result["death_cross_just_now"]:
        # ===== 真正的死亡交叉確認（第30分鐘） =====
        return (
            f"🟢 趕快賣出！趕快賣出！\n"
            f"━━━━━━━━━━━━━\n"
            f"{name}({sid}) @{price}\n"
            f"30分K KD死亡交叉確認！\n"
            f"K={k:.1f} 正式跌破 D={d:.1f}\n"
            f"━━━━━━━━━━━━━\n"
            f"小龍蝦即時亮燈：賣出訊號！"
        )

    if result["pre_golden_alert"]:
        # ===== 低檔金叉提前預警（第25~27分鐘） =====
        msg = (
            f"🦞 注意！{name}快要黃金交叉！\n"
            f"━━━━━━━━━━━━━\n"
            f"K={k:.1f} D={d:.1f} 距離只剩 {kd_dist:.1f}\n"
            f"K線斜率 +{slope:.2f}，開始往上拐了！\n"
        )
        if zone == "OVERSOLD_LOW":
            msg += f"低檔區（K≤30）沒人願意賣更低！\n"
        msg += (
            f"━━━━━━━━━━━━━\n"
            f"小龍蝦提醒：準備平倉低接！"
        )
        return msg

    if result["pre_death_alert"]:
        # ===== 高檔死叉提前預警（第25~27分鐘） =====
        msg = (
            f"🦞 注意！{name}快要死交了！\n"
            f"━━━━━━━━━━━━━\n"
            f"K={k:.1f} D={d:.1f} 距離只剩 {kd_dist:.1f}\n"
            f"K線斜率 {slope:.2f}，動能在減弱了！\n"
        )
        if zone == "EXTREME_HIGH":
            msg += f"極高檔區（K≥85），準備反轉！\n"
        elif zone == "OVERBOUGHT_HIGH":
            msg += f"高檔區（K≥70），上衝力道減弱！\n"
        msg += (
            f"━━━━━━━━━━━━━\n"
            f"小龍蝦提醒：準備賣出！"
        )
        return msg

    return None


# ============================================================
# 主掃描 + 狀態管理
# ============================================================
def load_states():
    if os.path.exists(SIGNAL_STATE_FILE):
        try:
            with open(SIGNAL_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_states(states):
    with open(SIGNAL_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)

def log_approaching(result):
    """紀錄預警事件，避免同一支重複發送"""
    logs = {}
    if os.path.exists(APPROACHING_LOG):
        try:
            with open(APPROACHING_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = {}

    key = f"{result['sid']}_{result['k_period']}"
    now_ts = int(time.time())

    if key not in logs:
        logs[key] = {"last_alert_type": "", "last_alert_ts": 0}

    # 同一種類型的預警，10分鐘內不重複
    alert_type = result["alert_reason"]
    cooldown = 600  # 10分鐘

    if logs[key]["last_alert_type"] == alert_type and (now_ts - logs[key]["last_alert_ts"]) < cooldown:
        return False

    logs[key]["last_alert_type"] = alert_type
    logs[key]["last_alert_ts"] = now_ts

    with open(APPROACHING_LOG, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    return True


def scan_all():
    """
    掃描所有自選股：
    1. 建立 Shioaji 連線（只用一次）
    2. 計算每支的KD + 斜率
    3. 檢查交叉/預警
    4. 輸出結果 + 語音提醒
    """
    print(f"\n{'='*60}")
    print(f"  🦞 小龍蝦 30分K KD極速預警大腦")
    print(f"  掃描時間: {datetime.now().strftime('%m/%d %H:%M:%S')}")
    print(f"  自選股數: {len(ALL_STOCKS)} 支")
    print(f"{'='*60}")

    api = login()
    states = load_states()
    alerts = []

    for sid, name, kp, bt, st in ALL_STOCKS:
        result = analyze_stock_advanced(api, sid, name, kp, bt, st)
        if result is None:
            continue

        key = f"{sid}_{kp}"
        prev_state = states.get(key, "NONE")

        # ─── 顯示狀態行 ───
        k_str = f"K={result['K']:.1f}"
        d_str = f"D={result['D']:.1f}"
        slope_str = f"斜率={result['K_slope']:+.2f}"
        dist_str = f"距={result['KD_distance']:.1f}"

        if result["golden_cross_just_now"]:
            icon = "🔴🟡"  # 剛金叉
        elif result["death_cross_just_now"]:
            icon = "🟢🔴"  # 剛死叉
        elif result["pre_golden_alert"]:
            icon = "💡🟢"  # 金叉預警
        elif result["pre_death_alert"]:
            icon = "⚠️🔴"  # 死叉預警
        elif result["is_golden"]:
            icon = "🟢"
        else:
            icon = "🔴"

        zone_icon = {"OVERSOLD_LOW": "⬇️", "OVERBOUGHT_HIGH": "⬆️", "EXTREME_HIGH": "🔥", "NORMAL": ""}
        zi = zone_icon.get(result["zone"], "")

        print(f"  {icon}{zi} {name}({sid}) {k_str} {d_str} @{result['price']} | {slope_str} {dist_str} | {result['timestamp']}")

        # ─── 檢查需要提醒的事件 ───
        # 1. 交叉確認（狀態改變）
        if result["golden_cross_just_now"]:
            if prev_state != "GOLDEN_CONFIRMED":
                msg = build_alert_message(result)
                if msg:
                    alerts.append({"type": "GOLDEN_CONFIRMED", "msg": msg, "result": result})
                    states[key] = "GOLDEN_CONFIRMED"

        elif result["death_cross_just_now"]:
            if prev_state != "DEATH_CONFIRMED":
                msg = build_alert_message(result)
                if msg:
                    alerts.append({"type": "DEATH_CONFIRMED", "msg": msg, "result": result})
                    states[key] = "DEATH_CONFIRMED"

        # 2. 提前預警（避免重複發送）
        if result["pre_golden_alert"]:
            if prev_state != "PRE_GOLDEN":
                if log_approaching(result):
                    msg = build_alert_message(result)
                    if msg:
                        alerts.append({"type": "PRE_GOLDEN", "msg": msg, "result": result})
                        states[key] = "PRE_GOLDEN"

        elif result["pre_death_alert"]:
            if prev_state != "PRE_DEATH":
                if log_approaching(result):
                    msg = build_alert_message(result)
                    if msg:
                        alerts.append({"type": "PRE_DEATH", "msg": msg, "result": result})
                        states[key] = "PRE_DEATH"

        # 3. 狀態回復（交叉消失時重置）
        if not result["golden_cross_just_now"] and not result["death_cross_just_now"]:
            if prev_state in ("GOLDEN_CONFIRMED", "DEATH_CONFIRMED"):
                if result["is_golden"] != ("GOLDEN_CONFIRMED" in prev_state):
                    states[key] = "NONE"

    api.logout()
    save_states(states)

    # ─── 輸出提醒 ───
    if alerts:
        print(f"\n{'='*60}")
        print(f"  ⚠️ 觸發 {len(alerts)} 個提醒!")
        print(f"{'='*60}")
        for a in alerts:
            print(f"\n{a['msg']}\n")
    else:
        print(f"\n  ✅ 無新訊號或預警")

    print(f"{'='*60}")
    print(f"  掃描完成\n")

    return alerts


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    scan_all()
