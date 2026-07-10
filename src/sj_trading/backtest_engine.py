"""
TWSE 歷史資料回測引擎
回測「KD黃金交叉 + 大戶資金流向」策略（日K版）
─────────────────────────────────────────
策略（門檻版）:
  買入 → 當日 K ≤ 38 且 KD 黃金交叉（前一日 K≤D, 今日 K>D）
  賣出 → 當日 K ≥ 70 且 KD 死亡交叉 或 持有超過 5 天

對比基準:  單純 KD 黃金交叉買 / 死亡交叉賣（無門檻）

資料源:
  TWSE STOCK_DAY — 月日K線（所有月份）
  TWSE T86       — 三大法人買賣超（僅交易相關日期 lazy fetch）

輸出:
  - 每支股票交易記錄（日期、買/賣、價格、張數、報酬率）
  - 總報酬率、勝率、最大連續虧損
  - 門檻策略 vs 單純 KD 交叉對比
"""

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# ===== 設定 ==================================================================

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

STOCKS = [
    ("2337", "旺宏",   7),
    ("2436", "偉詮電", 3),
    ("5351", "鈺創",   9),
    ("8150", "南茂",   3),
    ("3711", "日月光", 3),
    ("3673", "TPKKY",  3),
    ("4958", "臻鼎KY", 3),
    ("3042", "晶技",   3),
]

BACKTEST_START = date(2024, 1, 1)
BACKTEST_END   = date(2026, 7, 3)

T86_CACHE = {}  # { "YYYY-MM-DD": { sid: {...} } }  — 懶載入


# ===== 工具函式 ==============================================================

def roc_to_ad(roc_year: int) -> int:
    return roc_year + 1911

def month_range(start: date, end: date):
    ym = []
    d = date(start.year, start.month, 1)
    while d <= end:
        ym.append((d.year, d.month))
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return ym

def _cp(prefix: str, *parts) -> Path:
    return CACHE_DIR / f"{prefix}_{'_'.join(str(p) for p in parts)}.json"

def _load_cache(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"    ⚠ 快取損毀, 重新下載: {path.name}")
        path.unlink()
        return None

def _save_cache(path: Path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)


# ===== 1) 個股日K線 (STOCK_DAY) =============================================

def fetch_stock_day(sid: str, year: int, month: int):
    """抓取 TWSE 月日K線"""
    pd_str = f"{year}{month:02d}01"
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={pd_str}&stockNo={sid}"
    cp = _cp("STOCK_DAY", sid, f"{year}{month:02d}")
    cached = _load_cache(cp)
    if cached:
        return cached
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("stat") == "OK":
                _save_cache(cp, data)
                return data
            return None
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return None

def parse_stock_day(raw) -> dict:
    """
    raw['fields']: 日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數
    → { date_str: {open,high,low,close,volume} }
    """
    rows = raw.get("data", [])
    result = {}
    for row in rows:
        y, m, d = row[0].split("/")
        ds = f"{roc_to_ad(int(y))}-{int(m):02d}-{int(d):02d}"
        def n(s):
            try:
                return float(str(s).replace(",", ""))
            except:
                return 0.0
        result[ds] = {
            "open": n(row[3]), "high": n(row[4]),
            "low": n(row[5]), "close": n(row[6]), "volume": n(row[1]),
        }
    return result

def load_all_stock_prices(sid: str):
    """載入完整日K, 回傳 (dates, prices)"""
    all_p = {}
    for y, m in month_range(BACKTEST_START, BACKTEST_END):
        raw = fetch_stock_day(sid, y, m)
        if raw:
            all_p.update(parse_stock_day(raw))
    if not all_p:
        return [], []
    sd = sorted(all_p.keys())
    return sd, [all_p[d] for d in sd]


# ===== 2) 三大法人買賣超 (T86) — 懶載入 ====================================

def _fetch_t86_single(trading_date: date):
    """抓取 T86 某一天的資料, 回傳 raw dict，自動 cache"""
    ds = trading_date.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={ds}&selectType=ALL"
    cp = _cp("T86", ds)
    cached = _load_cache(cp)
    if cached:
        return cached
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data.get("stat") == "OK":
                _save_cache(cp, data)
                return data
            return None
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return None

def _parse_t86_for_stock(raw, sid):
    """從 T86 raw 中濾出特定 sid 的三大法人資料"""
    rows = raw.get("data", [])
    for row in rows:
        row0 = str(row[0]).strip()
        if row0 != sid:
            continue
        def p(i):
            try:
                v = str(row[i]).replace(",", "")
                if v in ("", "--", "-"):
                    return 0.0
                return float(v)
            except:
                return 0.0
        return {
            "foreign_net":  p(4),   # 外資買賣超
            "inv_trust_net": p(7),  # 投信買賣超
            "dealer_net":   p(8),   # 自營商買賣超
            "total_net":    p(9),   # 三大法人買賣超
        }
    return None

def get_institutional_data(date_str: str, sid: str):
    """懶載入: 取得某日某股的三大法人資料"""
    if date_str not in T86_CACHE:
        # 只 cache raw，不 cache parsed（節省記憶體）
        dt = date.fromisoformat(date_str)
        raw = _fetch_t86_single(dt)
        if raw:
            T86_CACHE[date_str] = raw
        else:
            T86_CACHE[date_str] = None
    raw = T86_CACHE[date_str]
    if raw is None:
        return None
    return _parse_t86_for_stock(raw, sid)


# ===== 3) KD 計算 ===========================================================

def compute_kd(closes, highs, lows, k_period=9):
    """標準 KD 計算, 回傳 (k_list, d_list)"""
    n = len(closes)
    k = [50.0] * n
    d = [50.0] * n
    for i in range(k_period, n):
        lo = min(lows[i - k_period + 1: i + 1])
        hi = max(highs[i - k_period + 1: i + 1])
        rsv = 50.0
        if hi != lo:
            rsv = (closes[i] - lo) / (hi - lo) * 100
        k[i] = (2/3) * k[i-1] + (1/3) * rsv
        d[i] = (2/3) * d[i-1] + (1/3) * k[i]
    return k, d


# ===== 4) 策略回測 ===========================================================

def run_strategy(dates, closes, k_vals, d_vals, k_period, strategy="threshold"):
    """
    strategy="threshold" → 門檻版
    strategy="simple"    → 單純 KD 交叉
    回傳 trade dict 列表
    """
    trades = []
    position = 0
    buy_price = buy_date = entry_k = 0.0
    hold_days = 0

    for i in range(k_period, len(dates)):
        k, d = k_vals[i], d_vals[i]
        pk, pd = k_vals[i-1], d_vals[i-1]
        price = closes[i]
        cur_date = dates[i]

        golden = pk <= pd and k > d
        death  = pk >= pd and k < d

        if position == 0:
            if golden:
                if strategy == "threshold":
                    if k <= 38:
                        position = 1; buy_price = price; buy_date = cur_date
                        hold_days = 0; entry_k = k
                else:
                    position = 1; buy_price = price; buy_date = cur_date
                    hold_days = 0; entry_k = k
        else:
            hold_days += 1
            sell = False
            if strategy == "threshold":
                if (k >= 70 and death) or hold_days > 5:
                    sell = True
            else:
                if death:
                    sell = True
            if sell:
                pnl = (price - buy_price) / buy_price * 100
                trades.append({
                    "buy_date": buy_date, "sell_date": cur_date,
                    "buy_price": round(buy_price,2), "sell_price": round(price,2),
                    "pnl_pct": round(pnl,2), "hold_days": hold_days,
                    "entry_k": round(entry_k,1), "exit_k": round(k,1),
                })
                position = 0

    if position == 1:
        cur_pnl = (closes[-1] - buy_price) / buy_price * 100
        trades.append({
            "buy_date": buy_date, "sell_date": "持有中",
            "buy_price": round(buy_price,2), "sell_price": round(closes[-1],2),
            "pnl_pct": round(cur_pnl,2), "hold_days": hold_days,
            "entry_k": round(entry_k,1), "exit_k": "-",
        })
    return trades


def calc_stats(trades, name):
    """計算績效統計"""
    closed = [t for t in trades if t["sell_date"] != "持有中"]
    n = len(closed)
    if n == 0:
        return {"name": name, "trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0, "total_pnl_pct": 0, "total_pnl_pts": 0,
                "avg_pnl": 0, "max_loss_pct": 0, "max_consec_loss": 0,
                "profit_factor": 0}
    pts_sum = sum(t["sell_price"] - t["buy_price"] for t in closed)
    pct_sum = sum(t["pnl_pct"] for t in closed)
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    losses = n - wins
    wr = wins / n * 100
    gp = sum(t["pnl_pct"] for t in closed if t["pnl_pct"] > 0)
    gl = abs(sum(t["pnl_pct"] for t in closed if t["pnl_pct"] < 0))
    pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0)
    max_cl = 0; cur_cl = 0; max_lp = 0.0
    for t in closed:
        if t["pnl_pct"] < 0:
            cur_cl += 1; max_cl = max(max_cl, cur_cl)
        else:
            cur_cl = 0
        max_lp = min(max_lp, t["pnl_pct"])
    return {
        "name": name, "trades": n, "wins": wins, "losses": losses,
        "win_rate": round(wr,1), "total_pnl_pct": round(pct_sum,2),
        "total_pnl_pts": round(pts_sum,2), "avg_pnl": round(pct_sum/n,2),
        "max_loss_pct": round(max_lp,2), "max_consec_loss": max_cl,
        "profit_factor": round(pf,2) if pf != float("inf") else "∞",
    }


def print_trades(trades, stats, detail=True, sid="", name=""):
    """標出交易明細 + 三大法人資料"""
    closed = [t for t in trades if t["sell_date"] != "持有中"]
    holding = [t for t in trades if t["sell_date"] == "持有中"]
    print(f"   交易次數: {len(closed)}{' (1筆持有中)' if holding else ''}")
    if detail and closed:
        # 可先批次 fetch 三大法人資料
        if sid:
            inst_dates = set()
            for t in closed:
                inst_dates.add(t["buy_date"])
                inst_dates.add(t["sell_date"])
            for ds in inst_dates:
                get_institutional_data(ds, sid)  # pre-cache
        hdr = (f"   {'買入日期':<12} {'賣出日期':<12} {'買價':>8} {'賣價':>8} "
               f"{'報酬%':>8} {'持有':>4} {'入K':>5} {'法人買':>8} {'法人賣':>8}")
        print(hdr)
        print(f"   {'━' * len(hdr)}")
        for t in closed:
            # 獲取三大法人資料
            b_inst = get_institutional_data(t["buy_date"], sid) if sid else None
            s_inst = get_institutional_data(t["sell_date"], sid) if sid else None
            bi = f"{b_inst['total_net']:+.0f}" if b_inst else "  N/A"
            si = f"{s_inst['total_net']:+.0f}" if s_inst else "  N/A"
            print(f"   {t['buy_date']:<12} {t['sell_date']:<12} "
                  f"{t['buy_price']:>8.2f} {t['sell_price']:>8.2f} "
                  f"{t['pnl_pct']:>+7.2f}% {t['hold_days']:>4d} "
                  f"{t['entry_k']:>5.1f} {bi:>8} {si:>8}")
    elif closed:
        for t in closed:
            print(f"   {t['buy_date']}→{t['sell_date']}  {t['pnl_pct']:+.2f}%")
    if closed:
        print(f"\n   📊 績效:")
        print(f"   總報酬率: {stats['total_pnl_pct']:+.2f}%  ({stats['total_pnl_pts']:+.2f} 點)")
        print(f"   勝率: {stats['win_rate']}%  ({stats['wins']}勝/{stats['losses']}敗)")
        print(f"   平均報酬: {stats['avg_pnl']:+.2f}%")
        print(f"   最大虧損: {stats['max_loss_pct']:.2f}%")
        print(f"   最大連續虧損: {stats['max_consec_loss']} 次")
        print(f"   獲利因子: {stats['profit_factor']}")


# ===== 5) 主流程 =============================================================

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        TWSE 歷史資料回測引擎                           ║")
    print(f"║        區間: {BACKTEST_START} ~ {BACKTEST_END}                  ║")
    print("║        策略: KD 黃金交叉 (門檻版 vs 單純交叉)          ║")
    print("║        三大法人: T86 懶載入 (僅交易相關日期)           ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print(f"\n📥 下載個股日K線資料 ({BACKTEST_START.year}~{BACKTEST_END.year})...")
    print(f"   受測股數: {len(STOCKS)} 支, 每支約31個月資料\n")

    all_threshold = []
    all_simple = []

    for sid, name, kp in STOCKS:
        print(f"{'═' * 62}")
        print(f"  📊 {name} ({sid}) — K={kp}")
        print(f"{'═' * 62}")

        dates, prices = load_all_stock_prices(sid)
        if not dates:
            print(f"  ❌ 無資料")
            all_threshold.append((name, calc_stats([], name), []))
            all_simple.append((name, calc_stats([], name), []))
            continue

        n = len(dates)
        last_p = prices[-1]["close"]
        print(f"  區間: {dates[0]} ~ {dates[-1]} ({n} 天)")
        print(f"  最新價: {last_p:.2f}")

        closes = [p["close"] for p in prices]
        highs  = [p["high"] for p in prices]
        lows   = [p["low"] for p in prices]

        k_vals, d_vals = compute_kd(closes, highs, lows, kp)

        # 門檻策略
        trades_t = run_strategy(dates, closes, k_vals, d_vals, kp, "threshold")
        stats_t  = calc_stats(trades_t, name)
        print(f"\n  🎯 門檻策略 (K≤38買 / K≥70+死叉 or 5日賣):")
        print_trades(trades_t, stats_t, sid=sid, name=name)

        # 單純KD交叉
        trades_s = run_strategy(dates, closes, k_vals, d_vals, kp, "simple")
        stats_s  = calc_stats(trades_s, name)
        print(f"\n  🔄 對比：單純 KD 交叉:")
        print_trades(trades_s, stats_s, detail=True, sid=sid, name=name)

        all_threshold.append((name, stats_t, trades_t))
        all_simple.append((name, stats_s, trades_s))

    # ═══ 彙總對比表 ═══
    print(f"\n\n{'=' * 70}")
    print("  📋 彙總比較")
    print(f"{'=' * 70}")
    hdr = (f"  {'股票':<10} {'K':<4} {'策略':<26} {'交易':>5} "
           f"{'勝率':>6} {'總報酬%':>9} {'均報酬':>8} {'最大連虧':>5}")
    print(hdr)
    print(f"  {'─' * 70}")

    sum_t1 = sum_t2 = 0.0
    sum_w1 = sum_l1 = sum_w2 = sum_l2 = 0

    for (sid, name, kp), (_, s1, _), (_, s2, _) in zip(STOCKS, all_threshold, all_simple):
        print(f"  {name:<10} {kp:<4} {'門檻(K≤38/K≥70+5D)':<26} "
              f"{s1['trades']:>5d} {s1['win_rate']:>5.1f}% {s1['total_pnl_pct']:>+8.2f}% "
              f"{s1['avg_pnl']:>+7.2f}% {s1['max_consec_loss']:>4d}")
        print(f"  {'':<10} {'':<4} {'單純KD交叉':<26} "
              f"{s2['trades']:>5d} {s2['win_rate']:>5.1f}% {s2['total_pnl_pct']:>+8.2f}% "
              f"{s2['avg_pnl']:>+7.2f}% {s2['max_consec_loss']:>4d}")
        sum_t1 += s1["total_pnl_pct"]
        sum_t2 += s2["total_pnl_pct"]
        sum_w1 += s1["wins"]; sum_l1 += s1["losses"]
        sum_w2 += s2["wins"]; sum_l2 += s2["losses"]

    print(f"  {'─' * 70}")
    c = len(STOCKS)
    w1r = sum_w1 / (sum_w1 + sum_l1) * 100 if (sum_w1 + sum_l1) else 0
    w2r = sum_w2 / (sum_w2 + sum_l2) * 100 if (sum_w2 + sum_l2) else 0
    print(f"  {'總計':<10} {'':<4} {'門檻策略':<26} {sum_w1+sum_l1:>5d} "
          f"{w1r:>5.1f}% {sum_t1/c:>+8.2f}% {sum_t1/(sum_w1+sum_l1 or 1):>+7.2f}%")
    print(f"  {'':<10} {'':<4} {'單純KD交叉':<26} {sum_w2+sum_l2:>5d} "
          f"{w2r:>5.1f}% {sum_t2/c:>+8.2f}% {sum_t2/(sum_w2+sum_l2 or 1):>+7.2f}%")
    print(f"  {'─' * 70}")

    # 結論
    avg1 = sum_t1 / c
    avg2 = sum_t2 / c
    print(f"\n  📌 結論:")
    if avg1 > avg2:
        print(f"     ✅ 門檻策略表現優於單純交叉（均報酬 {avg1:+.2f}% vs {avg2:+.2f}%）")
    elif avg1 < avg2:
        print(f"     ⚠ 單純交叉表現優於門檻策略（均報酬 {avg2:+.2f}% vs {avg1:+.2f}%）")
    else:
        print(f"     ➖ 兩者表現相當")
    print(f"     門檻策略總勝率: {w1r:.1f}% ({sum_w1}勝/{sum_l1}敗)")
    print(f"     單純交叉總勝率: {w2r:.1f}% ({sum_w2}勝/{sum_l2}敗)")

    # 輸出抓到多少 T86 cache
    cached_t86 = list(CACHE_DIR.glob("T86_*.json"))
    print(f"\n  📦 已快取 {len(cached_t86)} 天的三大法人資料")


if __name__ == "__main__":
    main()
