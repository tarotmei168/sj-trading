"""
大型回測腳本 — 30分K KD策略 6個月
回測對象：
  1. 永豐金最熱門20支股票（即時動態池 top 20 by 成交量/成交值）
  2. 0050 所有成分股
  3. + 亞翔(6139)

策略 (根據 7/3 更新)：
  - 使用 30分K 全面取代日K
  - 每支股票獨立找最佳 KD 參數 (K值, 買入門檻, 賣出門檻)
  - 黃金交叉且 K<買入門檻 = 買進
  - 死亡交叉且 K>賣出門檻 = 賣出
  - 找 6 個月內最佳參數組合
"""
import os, sys, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

# Fix Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# ============================================================
# 1. 股票清單
# ============================================================

# --- 0050 成分股 (元大台灣50) ---
STOCK_0050 = [
    ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"),
    ("2308", "台達電"), ("2881", "富邦金"), ("2882", "國泰金"),
    ("2412", "中華電"), ("1301", "台塑"), ("1303", "南亞"),
    ("1326", "台化"), ("2002", "中鋼"), ("2303", "聯電"),
    ("2886", "兆豐金"), ("2891", "中信金"), ("2884", "玉山金"),
    ("2887", "台新金"), ("2885", "元大金"), ("2301", "光寶科"),
    ("2357", "華碩"), ("2382", "廣達"), ("3231", "緯創"),
    ("2356", "英業達"), ("2353", "宏碁"), ("3008", "大立光"),
    ("3034", "聯詠"), ("3711", "日月光"), ("4904", "遠傳"),
    ("4906", "正文"), ("4958", "臻鼎-KY"), ("5871", "中租-KY"),
    ("5880", "合庫金"), ("6005", "群益證"), ("8046", "南電"),
    ("8454", "富邦媒"), ("9921", "巨大"), ("9933", "中鼎"),
    ("1101", "台泥"), ("1216", "統一"), ("1402", "遠東新"),
    ("1476", "儒鴻"), ("1590", "亞德客-KY"), ("2049", "上銀"),
    ("2105", "正新"), ("2207", "和泰車"), ("2227", "裕日車"),
    ("2395", "研華"), ("2408", "南亞科"), ("2474", "可成"),
    ("2603", "長榮"), ("2610", "華航"),
]

# --- 永豐金熱門池 (即時動態前20名 by 成交量+成交值) ---
# 這是典型的熱門股池（高成交量/成交值常駐熱門）
STOCK_HOT = [
    ("2330", "台積電"), ("2454", "聯發科"), ("2317", "鴻海"),
    ("2303", "聯電"), ("2344", "華邦電"), ("2408", "南亞科"),
    ("6770", "力積電"), ("2603", "長榮"), ("2609", "陽明"),
    ("2618", "長榮航"), ("2610", "華航"), ("2888", "新光金"),
    ("2892", "第一金"), ("2881", "富邦金"), ("2882", "國泰金"),
    ("3037", "欣興"), ("3189", "景碩"), ("8046", "南電"),
    ("3711", "日月光"), ("2382", "廣達"),
]

# --- 亞翔 ---
STOCK_EXTRA = [("6139", "亞翔")]

def get_full_stock_list():
    """合併所有股票，去除重複"""
    seen = set()
    result = []
    for sid, name in STOCK_0050 + STOCK_HOT + STOCK_EXTRA:
        if sid not in seen:
            seen.add(sid)
            result.append((sid, name, "0050" if (sid, name) in STOCK_0050 else ("熱門" if (sid, name) in STOCK_HOT else "亞翔")))
    return result

# ============================================================
# 2. Shioaji 資料下載 (30分K)
# ============================================================

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def fetch_30min_kbars(api, sid, days=185):
    """抓取歷史30分K線 (合併1分K)"""
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        contract = api.Contracts.Stocks[sid]
    except:
        return None
    
    all_dfs = []
    seg_end = end
    while seg_end > start:
        seg_start = max(seg_end - timedelta(days=29), start)
        try:
            kbars = api.kbars(
                contract=contract,
                start=seg_start.strftime("%Y-%m-%d"),
                end=seg_end.strftime("%Y-%m-%d"),
            )
            if len(kbars.ts) == 0:
                break
            df = pd.DataFrame({
                "datetime": pd.to_datetime(kbars.ts),
                "open": kbars.Open,
                "high": kbars.High,
                "low": kbars.Low,
                "close": kbars.Close,
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
    
    # 合併成30分K
    _30min = raw.resample("30min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    
    # 只保留台股交易時間 09:00~13:30
    _30min = _30min.between_time("09:00", "13:30")
    
    if len(_30min) < 20:
        return None
    
    return _30min

# ============================================================
# 3. 30分K KD 計算
# ============================================================

def compute_30min_kd(df, k_period):
    """30分K 計算 KD 值"""
    df = df.copy()
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    rsv = ((df["close"] - low_min) / (high_max - low_min)) * 100
    rsv = rsv.fillna(50)
    
    k_vals = [50] * k_period
    d_vals = [50] * k_period
    for i in range(k_period, len(df)):
        r = rsv.iloc[i]
        k_new = (2/3) * k_vals[-1] + (1/3) * r
        d_new = (2/3) * d_vals[-1] + (1/3) * k_new
        k_vals.append(k_new)
        d_vals.append(d_new)
    
    df["K"] = k_vals[:len(df)]
    df["D"] = d_vals[:len(df)]
    return df

# ============================================================
# 4. 回測引擎 — 使用最佳參數
# ============================================================

def backtest_kd_30min(df, k_period, buy_threshold, sell_threshold):
    """30分K KD交叉回測"""
    df = compute_30min_kd(df, k_period)
    valid = df.dropna(subset=["K", "D"])
    
    if len(valid) < k_period + 5:
        return 0, 0, 0, 0, []
    
    position = 0
    buy_price = 0
    buy_date = None
    total_pnl = 0
    trades = 0
    wins = 0
    trade_list = []
    
    for i in range(k_period + 1, len(valid)):
        k_now = valid["K"].iloc[i]
        d_now = valid["D"].iloc[i]
        k_prev = valid["K"].iloc[i-1]
        d_prev = valid["D"].iloc[i-1]
        close = valid["close"].iloc[i]
        idx = valid.index[i]
        
        # 黃金交叉
        if position == 0 and k_prev <= d_prev and k_now > d_now:
            if buy_threshold is None or k_now < buy_threshold:
                position = 1
                buy_price = close
                buy_date = idx
                trades += 1
        
        # 死亡交叉
        elif position == 1 and k_prev >= d_prev and k_now < d_now:
            if sell_threshold is None or k_now > sell_threshold:
                position = 0
                pnl = ((close - buy_price) / buy_price) * 100
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                trade_list.append({
                    "buy": buy_date.strftime("%m/%d %H:%M"),
                    "sell": idx.strftime("%m/%d %H:%M"),
                    "buy_price": round(buy_price, 2),
                    "sell_price": round(close, 2),
                    "return_pct": round(pnl, 2),
                })
    
    # 最後持有未賣
    if position == 1:
        pnl = ((valid["close"].iloc[-1] - buy_price) / buy_price) * 100
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        trade_list.append({
            "buy": buy_date.strftime("%m/%d %H:%M"),
            "sell": "持有中",
            "buy_price": round(buy_price, 2),
            "sell_price": round(valid["close"].iloc[-1], 2),
            "return_pct": round(pnl, 2),
        })
    
    return total_pnl, trades, wins, len(valid), trade_list

# ============================================================
# 5. 參數優化
# ============================================================

def optimize_params_30min(daily_30min):
    """對 30分K 找最佳參數"""
    k_range = [3, 5, 7, 9, 12, 14]
    buy_range = [20, 25, 30, 35, 40, 45, 50, None]
    sell_range = [50, 55, 60, 65, 70, 75, 80, None]
    
    best = {"pnl": -99999, "k": 0, "buy": 0, "sell": 0, "trades": 0, "wins": 0, "total_bars": 0}
    all_results = []
    
    for k in k_range:
        for bt in buy_range:
            for st in sell_range:
                pnl, trades, wins, total_bars, _ = backtest_kd_30min(daily_30min, k, bt, st)
                sr = round(wins / max(trades, 1) * 100, 1) if trades > 0 else 0
                all_results.append({"k": k, "buy": bt, "sell": st, "pnl": round(pnl, 2), "trades": trades, "wins": wins, "sr": sr})
                if pnl > best["pnl"] and trades >= 2:
                    best = {"pnl": pnl, "k": k, "buy": bt, "sell": st, "trades": trades, "wins": wins, "total_bars": total_bars}
    
    # 找前5名（至少有2筆交易）
    top5 = sorted([r for r in all_results if r["trades"] >= 2], key=lambda x: x["pnl"], reverse=True)[:5]
    
    return best, top5

# ============================================================
# 6. 主流程
# ============================================================

def main():
    stocks = get_full_stock_list()
    
    print("=" * 70)
    print("  📊 大型 30分K KD 回測系統 v2")
    print(f"  時間範圍: 近6個月 (約185天)")
    print(f"  總股票數: {len(stocks)} 檔")
    print(f"  包含: 0050全成分股 + 永豐金熱門前20 + 亞翔")
    print(f"  策略: 30分K KD黃金/死亡交叉 + 每支獨立最佳參數")
    print("=" * 70)
    
    # 分類統計
    categories = {"0050": 0, "熱門": 0, "亞翔": 0, "重複": 0}
    
    print("\n📥 登入 Shioaji 並下載資料...")
    api = login()
    
    results = {}
    total = len(stocks)
    errors = []
    
    for idx, (sid, name, cat) in enumerate(stocks, 1):
        categories[cat] = categories.get(cat, 0) + 1
        print(f"\n[{idx}/{total}] 📈 {name}({sid}) [{cat}] ...", end=" ", flush=True)
        
        daily_30min = fetch_30min_kbars(api, sid, days=185)
        if daily_30min is None or len(daily_30min) < 20:
            print(f"❌ 資料不足")
            errors.append((sid, name, "資料不足"))
            continue
        
        bar_count = len(daily_30min)
        latest_price = daily_30min["close"].iloc[-1]
        print(f"{bar_count}根30分K 最新價={latest_price:.2f}")
        
        # 找最佳參數
        best, top5 = optimize_params_30min(daily_30min)
        
        results[sid] = {
            "name": name,
            "category": cat,
            "bars": bar_count,
            "latest_price": round(latest_price, 2),
            "best": best,
            "top5": [{
                "k": r["k"],
                "buy": r["buy"],
                "sell": r["sell"],
                "pnl": r["pnl"],
                "trades": r["trades"],
                "sr": r["sr"]
            } for r in top5],
        }
        
        # 顯示最佳結果
        if best["trades"] >= 1:
            bt_str = f"買<{best['buy']}" if best['buy'] else "買不限"
            st_str = f"賣>{best['sell']}" if best['sell'] else "賣不限"
            sr = round(best["wins"] / max(best["trades"], 1) * 100, 1)
            print(f"  🏆 K={best['k']} {bt_str} {st_str} → 報酬+{best['pnl']:.1f}% | {best['trades']}筆交易 | 勝率{sr}%")
            if top5:
                print(f"  📋 Top3:", end="")
                for tr in top5[:3]:
                    bt2 = f"買<{tr['buy']}" if tr['buy'] else "買不限"
                    st2 = f"賣>{tr['sell']}" if tr['sell'] else "賣不限"
                    print(f" [K={tr['k']} {bt2} {st2} → {tr['pnl']:.1f}%]", end="")
                print()
        else:
            print(f"  ❌ 無交易訊號")
        
        time.sleep(0.3)  # 避免 API 過載
    
    api.logout()
    
    # ============================================================
    # 7. 輸出最終報表
    # ============================================================
    
    summary_path = os.path.join(os.path.dirname(__file__), "..", "..", "backtest_6m_summary.txt")
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "backtest_6m_results.json")
    
    # 分類排序
    sorted_results_0050 = [(k, v) for k, v in results.items() if v["category"] == "0050"]
    sorted_results_hot = [(k, v) for k, v in results.items() if v["category"] == "熱門"]
    sorted_results_extra = [(k, v) for k, v in results.items() if v["category"] == "亞翔"]
    
    # 儲存 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    # 生成文字報表
    lines = []
    lines.append("=" * 75)
    lines.append("  📊 大型 30分K KD 策略 6個月回測報告")
    lines.append(f"  測試日期: {datetime.now().strftime('%Y/%m/%d')}")
    lines.append(f"  資料範圍: 近6個月 (約185天)")
    lines.append("=" * 75)
    
    # 統計摘要
    total_ok = len(results)
    total_err = len(errors)
    win_stocks = sum(1 for v in results.values() if v["best"]["pnl"] > 0)
    loss_stocks = sum(1 for v in results.values() if v["best"]["pnl"] <= 0)
    avg_pnl = round(sum(v["best"]["pnl"] for v in results.values()) / max(total_ok, 1), 2)
    avg_trades = round(sum(v["best"]["trades"] for v in results.values()) / max(total_ok, 1), 1)
    
    lines.append(f"\n📋 總計: {total_ok}檔成功 / {total_err}檔失敗")
    lines.append(f"✅ 正報酬: {win_stocks}檔  ❌ 負報酬: {loss_stocks}檔")
    lines.append(f"📊 平均報酬: +{avg_pnl:.2f}%  (使用最佳參數)")
    lines.append(f"📊 平均交易次數: {avg_trades}次/股")
    
    # 分類統計
    for cat_name, cat_stocks in [("0050 成分股", sorted_results_0050), ("永豐金熱門池", sorted_results_hot), ("亞翔", sorted_results_extra)]:
        if not cat_stocks:
            continue
        cat_ok = len(cat_stocks)
        cat_win = sum(1 for _, v in cat_stocks if v["best"]["pnl"] > 0)
        cat_avg = round(sum(v["best"]["pnl"] for _, v in cat_stocks) / cat_ok, 2)
        lines.append(f"\n{'='*75}")
        lines.append(f"  📂 {cat_name}: {cat_ok}檔 | 正報酬 {cat_win}檔 | 平均報酬 +{cat_avg:.2f}%")
        lines.append(f"{'='*75}")
        lines.append(f"  {'代號':<6} {'名稱':<8} {'類別':<6} {'最佳K':<6} {'買門檻':<8} {'賣門檻':<8} {'報酬率':<10} {'交易':<6} {'勝率':<8}")
        lines.append(f"  {'-'*65}")
        
        for sid, v in sorted(cat_stocks, key=lambda x: x[1]["best"]["pnl"], reverse=True):
            b = v["best"]
            bt = f"<{b['buy']}" if b['buy'] else "不限"
            st = f">{b['sell']}" if b['sell'] else "不限"
            sr = round(b["wins"] / max(b["trades"], 1) * 100, 1)
            sign = "+" if b["pnl"] > 0 else ""
            lines.append(f"  {sid:<6} {v['name']:<8} {v['category']:<6} K={b['k']:<4} {bt:<8} {st:<8} {sign}{b['pnl']:.2f}%  {b['trades']:<4}筆 {sr:<5}%")
    
    # 排名
    all_sorted = sorted(results.items(), key=lambda x: x[1]["best"]["pnl"], reverse=True)
    lines.append(f"\n{'='*75}")
    lines.append(f"  🏆 總排名 (前10名)")
    lines.append(f"{'='*75}")
    for rank, (sid, v) in enumerate(all_sorted[:10], 1):
        b = v["best"]
        bt = f"買<{b['buy']}" if b['buy'] else "買不限"
        st = f"賣>{b['sell']}" if b['sell'] else "賣不限"
        sr = round(b["wins"] / max(b["trades"], 1) * 100, 1)
        lines.append(f"  #{rank:<2} {v['name']}({sid}) K={b['k']} {bt} {st} → +{b['pnl']:.2f}% | {b['trades']}筆 | 勝率{sr}%")
    
    lines.append(f"\n{'='*75}")
    lines.append(f"  💀 最差 (後5名)")
    lines.append(f"{'='*75}")
    for rank, (sid, v) in enumerate(all_sorted[-5:], 1):
        b = v["best"]
        bt = f"買<{b['buy']}" if b['buy'] else "買不限"
        st = f"賣>{b['sell']}" if b['sell'] else "賣不限"
        lines.append(f"  #{rank:<2} {v['name']}({sid}) K={b['k']} {bt} {st} → {b['pnl']:.2f}% | {b['trades']}筆")
    
    if errors:
        lines.append(f"\n{'='*75}")
        lines.append(f"  ❌ 失敗清單 ({len(errors)}檔)")
        lines.append(f"{'='*75}")
        for sid, name, reason in errors:
            lines.append(f"  {name}({sid}): {reason}")
    
    report_text = "\n".join(lines)
    print(f"\n\n{report_text}")
    
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\n✅ 報表已儲存:")
    print(f"   📄 {summary_path}")
    print(f"   📊 {json_path}")


if __name__ == "__main__":
    main()
