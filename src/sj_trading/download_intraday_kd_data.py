#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🦞 下載核心11檔歷史分鐘K → 合併30分K/15分K → 存KD資料
=========================================================
用途：
  建立30分K（或15分K）的歷史KD資料庫，用來回測黃金交叉參數，
  並在盤中即時監控時能以正確的KD值提前發出預警。

做法：
  1. 用 Shioaji 每次拉14天1分K，逐段推進（每次約14天，3年約80段）
  2. 合併成30分K（或15分K）
  3. 計算KD值並存成 CSV
  4. 支援增量更新：只下載缺少的天數

核心持股11檔：
  2436偉詮電、2337旺宏、5351鈺創、3673TPK、3711日月光、
  4958臻鼎、3042晶技、2454聯發科、2317鴻海、8150南茂、2330台積電

使用方式：
  python src/sj_trading/download_intraday_kd_data.py
    --freq 30        # 預設30分K，可改15
    --update         # 僅更新遺漏天數（預設）
    --force          # 強制全部重抓

輸出位置：
  database/30min_kd/  或  database/15min_kd/
  每檔一個 CSV，欄位: ts,open,high,low,close,volume,K,D
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

# ── 核心持股11檔 ──
CORE_STOCKS = {
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "3711": "日月光", "4958": "臻鼎-KY",
    "3042": "晶技",   "2454": "聯發科", "2317": "鴻海",
    "8150": "南茂",   "2330": "台積電",
}

BASE_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BASE_DIR / "database"
os.makedirs(DB_DIR, exist_ok=True)

# ── 分段參數 ──
SEGMENT_DAYS = 14       # Shioaji 一次拉14天1分K
MAX_RETRY = 3
RETRY_DELAY = 2.0       # 重試間隔秒


def parse_args():
    parser = argparse.ArgumentParser(description="下載核心持股歷史分鐘K並合併KD")
    parser.add_argument("--freq", type=int, default=30, choices=[15, 30],
                        help="K線頻率：15分K或30分K（預設30）")
    parser.add_argument("--update", action="store_true", default=True,
                        help="增量更新（只補缺的天數，預設）")
    parser.add_argument("--force", action="store_true",
                        help="強制全部重抓")
    parser.add_argument("--years", type=int, default=3,
                        help="往回抓幾年（預設3年）")
    parser.add_argument("--days", type=int, default=0,
                        help="往回抓幾天（優先於--years）")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════
#  Shioaji 登入
# ═══════════════════════════════════════════════════════

def login():
    """登入 Shioaji，失敗時重試"""
    api_key = os.environ.get("SJ_API_KEY")
    sec_key = os.environ.get("SJ_SEC_KEY")
    if not api_key or not sec_key:
        print("❌ 找不到 SJ_API_KEY / SJ_SEC_KEY (.env)")
        sys.exit(1)
    api = sj.Shioaji(simulation=True)
    api.login(api_key=api_key, secret_key=sec_key, contracts_timeout=15000)
    return api


# ═══════════════════════════════════════════════════════
#  分批下載1分K
# ═══════════════════════════════════════════════════════

def fetch_1min_segment(api, contract, start: date, end: date) -> pd.DataFrame | None:
    """抓一段1分K，回傳 DataFrame (ts, open, high, low, close, volume)"""
    for attempt in range(MAX_RETRY):
        try:
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            kbars = api.kbars(contract=contract, start=start_str, end=end_str)
            if kbars is None or len(getattr(kbars, 'ts', kbars if isinstance(kbars, list) else [])) == 0:
                return None
            ts = pd.to_datetime(kbars.ts)
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
            print(f"    ❌ 第{attempt+1}次重試仍失敗: {e}")
            return None


def download_all_1min_for_stock(api, sid: str, lookback_days: int,
                                existing_df: pd.DataFrame | None = None) -> pd.DataFrame | None:
    """
    下載一檔股票所有歷史1分K（從今天往回推 lookback_days 天）
    逐段拉取，每段 SEGMENT_DAYS 天
    """
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

    # 如果有已存在的資料，先找出還缺哪些天數
    if existing_df is not None and not existing_df.empty:
        existing_dates = set(
            existing_df["datetime"].dt.date.unique()
        )
    else:
        existing_dates = set()

    # 產生所有需要抓的日期段
    segments = []
    seg_start = start_date
    while seg_start <= end_date:
        seg_end = min(seg_start + timedelta(days=SEGMENT_DAYS - 1), end_date)
        segments.append((seg_start, seg_end))
        seg_start = seg_end + timedelta(days=1)

    # 過濾已存在的段（增量更新）
    if len(existing_dates) > 0:
        filtered = []
        for ss, se in segments:
            # 檢查這段日期是否已全部存在
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
            print(f"  ✅ {sid}: 資料已完整，無需更新")
            return existing_df

    # 逐段下載
    all_chunks = []
    if existing_df is not None and not existing_df.empty:
        all_chunks.append(existing_df)

    total_segments = len(segments)
    for idx, (ss, se) in enumerate(segments, 1):
        print(f"    [{idx}/{total_segments}] {ss} ~ {se}", end="", flush=True)
        df_chunk = fetch_1min_segment(api, contract, ss, se)
        if df_chunk is not None and not df_chunk.empty:
            all_chunks.append(df_chunk)
            print(f" → {len(df_chunk)} 筆")
        else:
            print(f" → 無資料")
        time.sleep(0.3)  # 避免打太急

    if not all_chunks:
        return None

    result = pd.concat(all_chunks, ignore_index=True)
    result.drop_duplicates(subset=["datetime"], inplace=True)
    result.sort_values("datetime", inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


# ═══════════════════════════════════════════════════════
#  合併成 N分K + 計算KD
# ═══════════════════════════════════════════════════════

def aggregate_to_nmin(min1_df: pd.DataFrame, freq_min: int = 30) -> pd.DataFrame:
    """從1分K合併成指定頻率的K線"""
    if min1_df is None or min1_df.empty:
        return pd.DataFrame()

    df = min1_df.copy()
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    # 過濾盤中時間 08:45 ~ 13:31（台股交易時間）
    df = df.between_time("08:45", "13:31")

    freq_str = f"{freq_min}min"
    resampled = df.resample(freq_str).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    # 過濾盤前集合(08:45)和尾盤空棒
    resampled = resampled[resampled["volume"] > 0]

    resampled.reset_index(inplace=True)
    return resampled


def compute_kd(df: pd.DataFrame, k_period: int = 9) -> pd.DataFrame:
    """計算KD值，支援自訂K值參數"""
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
#  存取歷史KD資料
# ═══════════════════════════════════════════════════════

def get_kd_dir(freq_min: int) -> Path:
    kd_dir = DB_DIR / f"{freq_min}min_kd"
    os.makedirs(kd_dir, exist_ok=True)
    return kd_dir


def load_existing_kd(sid: str, freq_min: int) -> pd.DataFrame | None:
    """載入已存好的KD歷史CSV"""
    kd_dir = get_kd_dir(freq_min)
    path = kd_dir / f"{sid}_kd.csv"
    if path.exists():
        try:
            df = pd.read_csv(path, parse_dates=["datetime"])
            if not df.empty:
                return df
        except Exception:
            pass
    return None


def save_kd_csv(sid: str, df: pd.DataFrame, freq_min: int):
    """儲存KD歷史資料"""
    kd_dir = get_kd_dir(freq_min)
    path = kd_dir / f"{sid}_kd.csv"
    
    # 確保欄位順序
    cols = ["datetime", "open", "high", "low", "close", "volume", "K", "D"]
    if "K" not in df.columns:
        df = compute_kd(df, k_period=9)

    out_df = df[cols].copy()
    out_df["datetime"] = pd.to_datetime(out_df["datetime"])
    out_df.sort_values("datetime", inplace=True)
    out_df.drop_duplicates(subset=["datetime"], inplace=True)
    out_df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  💾 寫入 {len(out_df)} 筆 → {path}")
    return out_df


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def main():
    args = parse_args()
    freq_min = args.freq
    force = args.force
    lookback_days = args.days if args.days > 0 else args.years * 365
    freq_label = f"{freq_min}分K"

    print("=" * 65)
    print(f"  🦞 下載核心11檔歷史 {freq_label} KD 資料")
    print(f"  往回抓 {lookback_days} 天（約 {lookback_days//365} 年）")
    if force:
        print(f"  ⚠️ 強制重抓全部資料")
    else:
        print(f"  📥 增量更新模式")
    print(f"  輸出: {DB_DIR / f'{freq_min}min_kd/'}")
    print("=" * 65)
    print()

    # 登入
    print("🔑 登入 Shioaji...")
    api = login()
    print("✅ 登入成功\n")

    succeeded = []
    failed = []

    for sid, name in CORE_STOCKS.items():
        print(f"\n{'─'*60}")
        print(f"📈 {name}({sid})")

        # 載入現有資料（若非強制重抓）
        existing = None
        if not force:
            existing = load_existing_kd(sid, freq_min)

        # 下載1分K原始資料
        print(f"  下載1分K原始資料（{lookback_days}天）...")
        min1_df = download_all_1min_for_stock(api, sid, lookback_days, existing)

        if min1_df is None or min1_df.empty:
            print(f"  ❌ {sid}: 下載失敗")
            failed.append(sid)
            continue

        # 如果是載入已存在的（有K/D欄位），直接存
        if existing is not None and "K" in existing.columns:
            # 檢查是否已有KD資料
            print(f"  ✅ {sid}: 資料已存在（{len(existing)}筆{existing.columns.tolist()[:5]}）")
            succeeded.append(sid)
            continue

        print(f"  合併成 {freq_label}...")
        kline = aggregate_to_nmin(min1_df, freq_min)

        if kline.empty or len(kline) < 30:
            print(f"  ⚠️ {sid}: {freq_label} 資料不足（{len(kline)}根）")
            failed.append(sid)
            continue

        print(f"  計算 KD (K=9)...")
        kline = compute_kd(kline, k_period=9)

        print(f"  儲存 {len(kline)} 根 {freq_label} KD...")
        save_kd_csv(sid, kline, freq_min)
        succeeded.append(sid)

    api.logout()

    # 總結
    print(f"\n{'='*65}")
    print(f"  完成！")
    print(f"  成功: {len(succeeded)}/{len(CORE_STOCKS)} 檔")
    print(f"  失敗: {len(failed)}/{len(CORE_STOCKS)} 檔")
    if failed:
        print(f"  失敗: {', '.join(failed)}")
    print(f"  輸出目錄: {DB_DIR / f'{freq_min}min_kd/'}")
    print(f"{'='*65}")
    print()
    print(f"💡 提示:")
    print(f"  下次執行 --update（增量更新）只補缺的天數")
    print(f"  若要改回測15分K: python ... --freq 15")
    print(f"  若要強制重抓: python ... --force")


if __name__ == "__main__":
    main()
