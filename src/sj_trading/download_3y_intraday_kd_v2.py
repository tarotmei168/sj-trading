#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦞 高效版 3年30分K KD 資料下載器 v2
======================================
優化策略（省 token、省時間、省連線次數）：

1. 加大分段：100天/段 vs 舊版14天/段
   → 3年約 80段 → 11段，連線次數剩 1/7

2. 逐檔串聯下載（Shioaji 限制無法平行，但減少分段數已大幅優化）

3. 先下1分K原始資料，再合併30分K、算KD、存CSV

4. 支援增量更新：只補缺少的天數

核心持股12檔（含0050）：
  2436偉詮電、2337旺宏、5351鈺創、3673TPK、3711日月光、
  4958臻鼎、3042晶技、2454聯發科、2317鴻海、8150南茂、2330台積電、0050元大台灣50

使用方式：
  python src/sj_trading/download_3y_intraday_kd_v2.py
    --freq 30         # 預設30分K
    --days 100        # 每段天數（預設100，可調）
    --update          # 增量更新（預設）
    --force           # 全部重抓
    --years 3         # 往回抓幾年（預設3年）

輸出位置：
  database/30min_kd/  每檔一個 CSV, 欄位: ts,open,high,low,close,volume,K,D
"""

import os, sys, time, argparse
from datetime import datetime, timedelta, date
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from dotenv import load_dotenv
import shioaji as sj

load_dotenv()

# ── 核心持股12檔（新增0050）──
CORE_STOCKS = {
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "3711": "日月光", "4958": "臻鼎-KY",
    "3042": "晶技",   "2454": "聯發科", "2317": "鴻海",
    "8150": "南茂",   "2330": "台積電", "0050": "元大台灣50",
}

BASE_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BASE_DIR / "database"
os.makedirs(DB_DIR, exist_ok=True)

MAX_RETRY = 3
RETRY_DELAY = 2.0

# ── 參數解析 ──
def parse_args():
    parser = argparse.ArgumentParser(description="高效版 3年30分K KD 下載器")
    parser.add_argument("--freq", type=int, default=30, choices=[15, 30],
                        help="K線頻率：15分K或30分K（預設30）")
    parser.add_argument("--days", type=int, default=100,
                        help="每次拉幾天的1分K（預設100天，Shioaji 可拉更長）")
    parser.add_argument("--update", action="store_true", default=True,
                        help="增量更新（只補缺的天數，預設）")
    parser.add_argument("--force", action="store_true",
                        help="強制全部重抓")
    parser.add_argument("--years", type=int, default=3,
                        help="往回抓幾年（預設3年）")
    return parser.parse_args()


# ═══════════════════════════════════════════
#  Shioaji 登入
# ═══════════════════════════════════════════
def login():
    api_key = os.environ.get("SJ_API_KEY")
    sec_key = os.environ.get("SJ_SEC_KEY")
    if not api_key or not sec_key:
        print("❌ 找不到 SJ_API_KEY / SJ_SEC_KEY (.env)")
        sys.exit(1)
    api = sj.Shioaji(simulation=True)
    api.login(api_key=api_key, secret_key=sec_key, contracts_timeout=15000)
    return api


# ═══════════════════════════════════════════
#  1分K 下載（單段，支援重試）
# ═══════════════════════════════════════════
def fetch_1min_segment(api, contract, start: date, end: date) -> pd.DataFrame | None:
    for attempt in range(MAX_RETRY):
        try:
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            kbars = api.kbars(contract=contract, start=start_str, end=end_str)
            if kbars is None:
                return None
            ts = getattr(kbars, 'ts', None)
            if ts is None or len(ts) == 0:
                return None
            ts = pd.to_datetime(ts)
            df = pd.DataFrame({
                "datetime": ts,
                "open": [float(x) for x in kbars.Open],
                "high": [float(x) for x in kbars.High],
                "low": [float(x) for x in kbars.Low],
                "close": [float(x) for x in kbars.Close],
                "volume": [float(x) for x in kbars.Volume],
            })
            return df
        except Exception as e:
            if attempt < MAX_RETRY - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            print(f" ❌ 重試{attempt+1}次仍失敗: {e}")
            return None


# ═══════════════════════════════════════════
#  完整下載一檔股票
# ═══════════════════════════════════════════
def download_stock(api, sid: str, lookback_days: int, seg_days: int,
                   existing_df: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """下載一檔股票歷史1分K（大段，每段 seg_days 天）"""
    # 取得合約
    contract = getattr(api.Contracts.Stocks, sid, None)
    if contract is None:
        try:
            contract = api.Contracts.Stocks[sid]
        except (KeyError, AttributeError):
            print(f"  ⚠️ {sid}: 找不到合約")
            return None

    now = datetime.now()
    end_date = now.date()
    start_date = end_date - timedelta(days=lookback_days)

    # 已存在日期
    if existing_df is not None and not existing_df.empty:
        existing_dates = set(existing_df["datetime"].dt.date.unique())
    else:
        existing_dates = set()

    # 產生大段
    segments = []
    seg_start = start_date
    while seg_start <= end_date:
        seg_end = min(seg_start + timedelta(days=seg_days - 1), end_date)
        segments.append((seg_start, seg_end))
        seg_start = seg_end + timedelta(days=1)

    # 增量過濾
    if len(existing_dates) > 0:
        filtered = []
        for ss, se in segments:
            all_exist = True
            d = ss
            while d <= se and d <= end_date:
                if d not in existing_dates:
                    all_exist = False
                    break
                d += timedelta(days=1)
            if not all_exist:
                filtered.append((ss, se))
        segments = filtered
        if not segments:
            print(f"  ✅ 資料完整，無需更新")
            return existing_df

    all_chunks = [existing_df] if existing_df is not None and not existing_df.empty else []
    total = len(segments)

    for idx, (ss, se) in enumerate(segments, 1):
        print(f"    [{idx}/{total}] {ss} ~ {se}", end="", flush=True)
        chunk = fetch_1min_segment(api, contract, ss, se)
        if chunk is not None and not chunk.empty:
            all_chunks.append(chunk)
            print(f" → {len(chunk)} 筆")
        else:
            print(f" → 無資料")
        time.sleep(0.3)  # 冷卻

    if not all_chunks:
        return None

    result = pd.concat(all_chunks, ignore_index=True)
    result.drop_duplicates(subset=["datetime"], inplace=True)
    result.sort_values("datetime", inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


# ═══════════════════════════════════════════
#  合併成 N分K + 計算KD
# ═══════════════════════════════════════════
def aggregate_to_nmin(min1_df: pd.DataFrame, freq_min: int = 30) -> pd.DataFrame:
    if min1_df is None or min1_df.empty:
        return pd.DataFrame()
    df = min1_df.copy()
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    df = df.between_time("08:45", "13:31")
    freq_str = f"{freq_min}min"
    resampled = df.resample(freq_str).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    resampled = resampled[resampled["volume"] > 0]
    resampled.reset_index(inplace=True)
    return resampled


def compute_kd(df: pd.DataFrame, k_period: int = 9) -> pd.DataFrame:
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


# ═══════════════════════════════════════════
#  讀寫歷史KD CSV
# ═══════════════════════════════════════════
def get_kd_dir(freq_min: int) -> Path:
    d = DB_DIR / f"{freq_min}min_kd"
    os.makedirs(d, exist_ok=True)
    return d


def load_existing_kd(sid: str, freq_min: int) -> pd.DataFrame | None:
    path = get_kd_dir(freq_min) / f"{sid}_kd.csv"
    if path.exists():
        try:
            df = pd.read_csv(path, parse_dates=["datetime"])
            if not df.empty:
                return df
        except:
            pass
    return None


def save_kd_csv(sid: str, df: pd.DataFrame, freq_min: int):
    path = get_kd_dir(freq_min) / f"{sid}_kd.csv"
    cols = ["datetime", "open", "high", "low", "close", "volume", "K", "D"]
    if "K" not in df.columns:
        df = compute_kd(df, k_period=9)
    out = df[cols].copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    out.sort_values("datetime", inplace=True)
    out.drop_duplicates(subset=["datetime"], inplace=True)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  💾 已儲存 {len(out)} 根 {freq_min}分K → {path}")


# ═══════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════
def main():
    args = parse_args()
    freq_min = args.freq
    seg_days = args.days
    force = args.force
    lookback_days = args.years * 365
    freq_label = f"{freq_min}分K"

    # 估算段數
    total_segments_per_stock = (lookback_days // seg_days) + 1
    total_calls = len(CORE_STOCKS) * total_segments_per_stock
    est_minutes = round(total_calls * 3 / 60, 1)  # 每段約3秒含冷卻

    print("=" * 65)
    print(f"  🦞 高效 3年 {freq_label} KD 下載器 v2")
    print(f"  {len(CORE_STOCKS)} 檔核心持股（含0050）")
    print(f"  往回抓 {lookback_days} 天（{args.years}年）")
    print(f"  每段 {seg_days} 天 × {total_segments_per_stock} 段/檔")
    print(f"  總計約 {total_calls} 次 API 呼叫")
    print(f"  預估時間: ~{est_minutes} 分鐘")
    print(f"  模式: {'🔄 增量更新' if not force else '⚠️ 強制全部重抓'}")
    print(f"  輸出: {DB_DIR / f'{freq_min}min_kd/'}")
    print("=" * 65)
    print()

    # 登入
    print("🔑 登入 Shioaji...", end=" ", flush=True)
    api = login()
    print("✅ 成功\n")

    start_time = time.time()
    succeeded = []
    failed = []

    for sid, name in CORE_STOCKS.items():
        t0 = time.time()
        print(f"\n{'─'*60}")
        print(f"📈 {name}({sid})")

        existing = None
        if not force:
            existing = load_existing_kd(sid, freq_min)

        print(f"  下載1分K（{lookback_days}天, {seg_days}天/段）...")
        min1_df = download_stock(api, sid, lookback_days, seg_days, existing)

        if min1_df is None or min1_df.empty:
            print(f"  ❌ 失敗")
            failed.append(sid)
            continue

        # 若已有KD資料，跳過合併
        if existing is not None and "K" in existing.columns:
            print(f"  ✅ 已存在 {len(existing)} 筆 KD 資料")
            succeeded.append(sid)
            elapsed = time.time() - t0
            print(f"  ⏱ {elapsed:.0f}秒")
            continue

        print(f"  合併 {freq_label}...")
        kline = aggregate_to_nmin(min1_df, freq_min)
        if kline.empty or len(kline) < 30:
            print(f"  ⚠️ 資料不足（{len(kline)}根）")
            failed.append(sid)
            continue

        print(f"  計算 KD(K=9)...")
        kline = compute_kd(kline, k_period=9)

        print(f"  儲存...")
        save_kd_csv(sid, kline, freq_min)
        succeeded.append(sid)
        elapsed = time.time() - t0
        print(f"  ⏱ {elapsed:.0f}秒")

    api.logout()

    total_elapsed = time.time() - start_time
    print(f"\n{'='*65}")
    print(f"  ✅ 完成！")
    print(f"  成功: {len(succeeded)}/{len(CORE_STOCKS)} 檔")
    print(f"  失敗: {len(failed)}/{len(CORE_STOCKS)} 檔")
    if failed:
        print(f"  失敗: {', '.join(failed)}")
    print(f"  總耗時: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分鐘)")
    print(f"{'='*65}")
    print()
    print(f"💡 用法:")
    print(f"  python src/sj_trading/download_3y_intraday_kd_v2.py              # 預設3年30分K")
    print(f"  python src/sj_trading/download_3y_intraday_kd_v2.py --days 100   # 100天/段")
    print(f"  python src/sj_trading/download_3y_intraday_kd_v2.py --freq 15    # 15分K")
    print(f"  python src/sj_trading/download_3y_intraday_kd_v2.py --force      # 全部重抓")
    print(f"  python src/sj_trading/download_3y_intraday_kd_v2.py --years 1    # 只抓1年")


if __name__ == "__main__":
    main()
