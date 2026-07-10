"""
KD 訊號監控 + 4次提醒通知系統
每當黃金交叉/死亡交叉發生時，自動發送4次提醒
並在接近買賣門檻時發出預警
"""
import os, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()

# ===== 從 watchlist.txt 讀取自選清單 =====
HOLDING_COST = {}

def load_watchlist():
    watchlist_path = os.path.join(os.path.dirname(__file__), "..", "..", "watchlist.txt")
    holdings, watches = [], []
    try:
        with open(watchlist_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    sid = parts[0]
                    name = parts[1]
                    k = int(parts[2]) if parts[2] else 9
                    buy_th = int(parts[3]) if parts[3] else None
                    sell_th = int(parts[4]) if len(parts) > 4 and parts[4] else None
                    cost = HOLDING_COST.get(sid, None)
                    if cost is not None:
                        holdings.append((sid, name, k, buy_th, sell_th, cost))
                    else:
                        watches.append((sid, name, k, buy_th, sell_th, None))
    except FileNotFoundError:
        pass
    return holdings, watches

HOLDINGS, WATCHES = load_watchlist()
ALL_STOCKS = HOLDINGS + WATCHES

SIGNAL_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "signal_states.json")

def load_signal_states():
    if os.path.exists(SIGNAL_STATE_FILE):
        try:
            with open(SIGNAL_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_signal_states(states):
    with open(SIGNAL_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_daily(api, stock_id, days=60):
    contract = api.Contracts.Stocks[stock_id]
    end = datetime.now()
    start = end - timedelta(days=days)
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        try:
            kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
            if len(kbars.ts) == 0:
                break
            df = pd.DataFrame({"datetime": pd.to_datetime(kbars.ts), "open": kbars.Open, "high": kbars.High, "low": kbars.Low, "close": kbars.Close, "volume": kbars.Volume})
            all_dfs.append(df)
            seg_end = seg_start - timedelta(seconds=1)
        except:
            break
    if not all_dfs:
        return pd.DataFrame()
    min_df = pd.concat(all_dfs)
    min_df.drop_duplicates(subset=["datetime"], inplace=True)
    min_df.sort_values("datetime", inplace=True)
    min_df.set_index("datetime", inplace=True)
    daily = min_df.resample("D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    daily.index.name = "date"
    return daily

def compute_kd(df, k_period):
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    df["RSV"] = ((df["close"] - low_min) / (high_max - low_min)) * 100
    df["RSV"] = df["RSV"].fillna(50)
    df["K"] = 50.0
    df["D"] = 50.0
    for i in range(k_period, len(df)):
        df.iloc[i, df.columns.get_loc("K")] = (2/3) * df.iloc[i-1]["K"] + (1/3) * df.iloc[i]["RSV"]
        df.iloc[i, df.columns.get_loc("D")] = (2/3) * df.iloc[i-1]["D"] + (1/3) * df.iloc[i]["K"]
    return df

def check_signals(stock_id, name, k_period, buy_threshold, sell_threshold, cost):
    try:
        api = login()
        daily = fetch_daily(api, stock_id, days=60)
        api.logout()
        if daily.empty or len(daily) < k_period + 5:
            return None
        daily = compute_kd(daily, k_period)
        valid = daily.dropna(subset=["K", "D"]).copy()
        if len(valid) < 3:
            return None
        last, prev, prev2 = valid.iloc[-1], valid.iloc[-2], valid.iloc[-3]
        k_now, d_now, k_prev, d_prev = round(last["K"], 1), round(last["D"], 1), round(prev["K"], 1), round(prev["D"], 1)
        close_now = round(last["close"], 2)
        result = {"stock_id": stock_id, "name": name, "k_period": k_period, "price": close_now, "k": k_now, "d": d_now, "cost": cost, "pnl_pct": round((close_now - cost) / cost * 100, 2) if cost else None}
        # 黃金交叉
        is_golden = k_prev <= d_prev and k_now > d_now
        if buy_threshold:
            is_golden = is_golden and k_now < buy_threshold
        # 死亡交叉
        is_death = k_prev >= d_prev and k_now < d_now
        if sell_threshold:
            is_death = is_death and k_now > sell_threshold
        result["signal"] = "GOLDEN" if is_golden else ("DEATH" if is_death else "NONE")
        
        # ===== 新增：接近門檻預警 =====
        result["warnings"] = []
        
        # 超買/超賣
        if k_now > 80:
            result["warnings"].append("超買區 K>80")
        elif k_now < 20:
            result["warnings"].append("超賣區 K<20")
        
        # 接近賣出門檻 (K值在門檻±10內)
        if sell_threshold is not None:
            diff = sell_threshold - k_now
            if 0 < diff <= 10:
                result["warnings"].append(f"⚠️ 接近賣點! K值({k_now})距門檻({sell_threshold})差{diff}")
            elif diff <= 0:
                result["warnings"].append(f"🔴 K值已達賣出條件! K({k_now}) > 門檻({sell_threshold})")
        
        # 接近買入門檻
        if buy_threshold is not None:
            diff = k_now - buy_threshold
            if 0 < diff <= 10:
                result["warnings"].append(f"💡 接近買點! K值({k_now})距門檻({buy_threshold})差{diff}")
            elif diff <= 0:
                result["warnings"].append(f"🟢 K值已達買入條件! K({k_now}) < 門檻({buy_threshold})")
        
        return result
    except Exception as e:
        return None


def send_alert(alert_type, stock, message_num=1, total=4):
    if alert_type == "GOLDEN":
        icon, title = "🟢", f"🔔 黃金交叉提醒 ({message_num}/{total})"
        msgs = [
            f"【首次提醒】{stock['name']} K值({stock['k']})向上突破D值({stock['d']})！黃金交叉出現！建議：考慮買進",
            f"【二次提醒】{stock['name']} K({stock['k']}) > D({stock['d']}) 確認黃金交叉有效，建議：可分批建立部位",
            f"【三次提醒】{stock['name']} 黃金交叉後續觀察，建議：設定停損點，留意是否能站穩",
            f"【最終提醒】{stock['name']} 黃金交叉確認完成，記得設定好停利停損再進場"
        ]
    else:
        icon, title = "🔴", f"🔔 死亡交叉提醒 ({message_num}/{total})"
        msgs = [
            f"【首次提醒】{stock['name']} K值({stock['k']})向下跌破D值({stock['d']})！死亡交叉出現！建議：考慮減碼或停損",
            f"【二次提醒】{stock['name']} K({stock['k']}) < D({stock['d']}) 死亡交叉確認，建議：執行減碼操作",
            f"【三次提醒】{stock['name']} 死亡交叉後續觀察，建議：確認是否已跌破支撐",
            f"【最終提醒】{stock['name']} 死亡交叉確認完成，請確實執行風險控管"
        ]
    cost_info = f" | 成本:{stock['cost']}" if stock.get('cost') else ""
    pnl_info = f" | 損益:{stock['pnl_pct']}%" if stock.get('pnl_pct') else ""
    msg = f"""
{icon} {title}
━━━━━━━━━━━━━
股票: {stock['name']}({stock['stock_id']})
K值: {stock['k']} | D值: {stock['d']}
股價: {stock['price']}{cost_info}{pnl_info}
━━━━━━━━━━━━━
{msgs[message_num-1]}
"""
    return msg


def scan_all_stocks(show_detail=True):
    print("\n" + "=" * 55)
    print(f"📡 KD 訊號掃描 {datetime.now().strftime('%m/%d %H:%M')}")
    print("=" * 55)
    states = load_signal_states()
    alerts = []
    threshold_alerts = []
    
    for sid, name, kp, bt, st, cost in ALL_STOCKS:
        result = check_signals(sid, name, kp, bt, st, cost)
        if not result:
            continue
        key = f"{sid}_{kp}"
        prev_signal = states.get(key, "NONE")
        current_signal = result["signal"]
        
        pnl = f"損益:{result['pnl_pct']}%" if result['pnl_pct'] is not None else ""
        warn_str = " | " + " | ".join(result["warnings"]) if result["warnings"] else ""
        icon = "🟢" if current_signal == "GOLDEN" else ("🔴" if current_signal == "DEATH" else "⚪")
        print(f"  {icon} {name}({sid}) K={result['k']} D={result['d']} @{result['price']} {pnl}{warn_str}")
        
        # 新訊號 → 提醒
        if current_signal != "NONE" and current_signal != prev_signal:
            alerts.append(result)
            states[key] = current_signal
        elif current_signal != "NONE" and current_signal == prev_signal:
            states[key] = current_signal
        elif current_signal == "NONE" and prev_signal != "NONE":
            states[key] = "NONE"
        
        # 接近門檻預警
        threshold_warnings = [w for w in result["warnings"] if "接近" in w or "已達" in w or "超買" in w or "超賣" in w]
        if threshold_warnings:
            threshold_alerts.append(result)
    
    save_signal_states(states)
    return alerts, threshold_alerts


def run_monitor():
    print("\n🔔 KD 交叉訊號監控系統")
    print(f"庫存股: {len(HOLDINGS)} 支 | 觀察股: {len(WATCHES)} 支 (從 watchlist.txt 讀取)")
    
    alerts, threshold_alerts = scan_all_stocks()
    
    # 黃金/死亡交叉的4次提醒
    if alerts:
        print(f"\n{'!' * 55}")
        print(f"⚠️  偵測到 {len(alerts)} 個新訊號!")
        print(f"{'!' * 55}")
        for stock in alerts:
            for i in range(4):
                print(send_alert(stock["signal"], stock, i + 1))
                time.sleep(0.3)
    
    # 接近門檻預警
    if threshold_alerts:
        print(f"\n{'~' * 55}")
        print(f"⚠️  偵測到 {len(threshold_alerts)} 個門檻預警!")
        print(f"{'~' * 55}")
        for stock in threshold_alerts:
            for w in stock["warnings"]:
                if "接近" in w or "已達" in w or "超買" in w or "超賣" in w:
                    print(f"\n{'~' * 45}")
                    pnl = f"損益:{stock['pnl_pct']}%" if stock.get('pnl_pct') else ""
                    print(f"  {stock['name']}({stock['stock_id']}) K={stock['k']} @{stock['price']} {pnl}")
                    print(f"  ⚠️ {w}")
    
    if not alerts and not threshold_alerts:
        print(f"\n✅ 無新訊號")


if __name__ == "__main__":
    run_monitor()
