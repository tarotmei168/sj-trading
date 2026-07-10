"""
30分K原生下載器 🦞
==============================
直接使用 sj.constant.KBarType.Min30 原生 30 分 K 格式，
永豐證券直拉，一秒內打包近一個月的純淨30分K線，存進本機 data/。

用法:
    uv run download_30k                     # 下載 watchlist.txt 全部 (預設近30天)
    uv run download_30k --sid 2330          # 只下載一支
    uv run download_30k --sid 2330,2454,3711  # 多支
    uv run download_30k --days 5            # 只抓近5天
    uv run download_30k --format csv        # 輸出 CSV (預設 parquet)
    uv run read_30k --read 2436             # 讀取已存檔摘要，不下載

小龍蝦版登入 (person_id + passwd) 範例:
    visit: https://sinopac.com/api/python
"""
import sys
import os
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[3] / '.env')
import shioaji as sj

load_dotenv()

# ── 檔案輸出 ───────────────────────────────────
DATA_DIR = Path(__file__).parents[2] / "data" / "kbar_30m"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── watchlist.txt 解析 ────────────────────────
def parse_watchlist(path: str = None) -> list[str]:
    if path is None:
        path = Path(__file__).parents[2] / "watchlist.txt"
    path = Path(path)
    if not path.exists():
        print(f"⚠️  找不到 watchlist: {path}")
        return []

    sids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if parts:
                sid = parts[0].strip()
                if sid.isdigit():
                    sids.append(sid)
    return sids


# ── 登入 (兩種模式) ────────────────────────────

def login_with_apikey() -> sj.Shioaji:
    """API Key 模擬環境登入"""
    api = sj.Shioaji(simulation=True)
    api.login(
        api_key=os.environ["SHIOAJI_API_KEY"],
        secret_key=os.environ["SHIOAJI_SECRET_KEY"],
    )
    return api


def login_with_account(person_id: str, passwd: str) -> sj.Shioaji:
    """person_id + passwd 正式環境登入（小龍蝦風格）"""
    api = sj.Shioaji()
    api.login(
        person_id=person_id,
        passwd=passwd,
        contracts_cb=lambda st: None,  # 靜默載入商品檔
    )
    return api


# ── 原生 30 分 K 下載 (核心) ───────────────────

def download_30k(
    api: sj.Shioaji,
    sid: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame | None:
    """
    🦞 永豐管線直拉原生 30分K，用 {**kbars} 解包一秒轉 DataFrame。

    參數:
        api:      已登入的 sj.Shioaji 實例
        sid:      股票代號，如 "2436"
        start_date / end_date: "YYYY-MM-DD"

    回傳:
        pd.DataFrame(columns=[datetime, open, high, low, close, volume])
        或 None（無資料 / 異常）
    """
    try:
        contract = api.Contracts.Stocks[sid]
        kbars = api.kbars(
            contract=contract,
            start_date=start_date,
            end_date=end_date,
            cb_type=sj.constant.KBarType.Min30,
        )
    except Exception as e:
        print(f"  ❌ {sid} 下載異常: {e}")
        return None

    if kbars is None or len(kbars.ts) == 0:
        print(f"  ⚠️  {sid} 無資料")
        return None

    # 🎯 {**kbars} 解包 → 正名時間戳 → 排序
    df = pd.DataFrame({**kbars})
    df["ts"] = pd.to_datetime(df["ts"])
    df.rename(columns={
        "ts": "datetime",
        "Open": "open", "High": "high",
        "Low": "low", "Close": "close",
        "Volume": "volume",
    }, inplace=True)
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df[["datetime", "open", "high", "low", "close", "volume"]]


# ── 存檔 ──────────────────────────────────────
def save_kbar(sid: str, df: pd.DataFrame, fmt: str = "parquet"):
    """存到 data/kbar_30m/ 下，支援 parquet / csv / json"""
    base = DATA_DIR / sid
    if fmt == "parquet":
        path = base.with_suffix(".parquet")
        df.to_parquet(path, index=False)
    elif fmt == "csv":
        path = base.with_suffix(".csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif fmt == "json":
        path = base.with_suffix(".json")
        records = []
        for _, r in df.iterrows():
            records.append({
                "datetime": r["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
                "o": round(r["open"], 2),
                "h": round(r["high"], 2),
                "l": round(r["low"], 2),
                "c": round(r["close"], 2),
                "v": int(r["volume"]),
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"不支援格式: {fmt}")

    print(f"  ✅ {sid}: {len(df)} 根 30分K → {path}")
    return path


# ── 讀取已存檔 ────────────────────────────────
def load_kbar(sid: str, fmt: str = None) -> pd.DataFrame | None:
    """
    從 data/kbar_30m/ 讀取先前存檔。
    自動依副檔名判斷格式，或指定 fmt。
    """
    base = DATA_DIR / sid
    if fmt is None:
        for ext in [".parquet", ".csv", ".json"]:
            p = base.with_suffix(ext)
            if p.exists():
                fmt = ext.lstrip(".")
                break
        if fmt is None:
            return None

    path = base.with_suffix(f".{fmt}")
    if not path.exists():
        return None

    if fmt == "parquet":
        return pd.read_parquet(path)
    elif fmt == "csv":
        df = pd.read_csv(path, parse_dates=["datetime"])
        return df
    elif fmt == "json":
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        df = pd.DataFrame(records)
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df
    return None


# ── 主程式入口 ─────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="🦞 30分K原生下載器 (sj.constant.KBarType.Min30)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  uv run download_30k                          # 全部 watchlist
  uv run download_30k --sid 2330 --days 5      # 只抓台積電近5天30分K
  uv run download_30k --sid 2436,3711 --format csv  # 多支輸出CSV
  uv run read_30k --read 2330                  # 讀取已存檔不重抓
        """
    )
    parser.add_argument("--sid", type=str, default=None,
                        help="股票代號,逗號分隔 (預設: 從 watchlist.txt 讀取)")
    parser.add_argument("--days", type=int, default=30,
                        help="抓取最近 N 天的 30分K (預設: 30)")
    parser.add_argument("--format", type=str, default="parquet",
                        choices=["parquet", "csv", "json"],
                        help="輸出格式 (預設: parquet)")
    parser.add_argument("--read", type=str, default=None, metavar="SID",
                        help="只讀取不重新下載, 顯示摘要資訊")
    args = parser.parse_args()

    # ── 只讀取模式 ──
    if args.read:
        df = load_kbar(args.read)
        if df is None:
            print(f"❌ {args.read}: 找不到已存檔的 30分K 資料")
            return
        print(f"\n📊 {args.read} 30分K 摘要:")
        print(f"   資料筆數: {len(df)} 根")
        print(f"   日期範圍: {df['datetime'].min()} ~ {df['datetime'].max()}")
        print(f"   最新一筆: {df.iloc[-1].to_dict()}")
        print(f"\n最後 10 根:")
        print(df.tail(10).to_string(index=False))
        return

    # ── 決定股票清單 ──
    if args.sid:
        sids = [s.strip() for s in args.sid.split(",") if s.strip()]
    else:
        sids = parse_watchlist()

    if not sids:
        print("❌ 沒有指定股票代號，也沒找到 watchlist.txt")
        sys.exit(1)

    end = datetime.now()
    start = end - timedelta(days=args.days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    print(f"\n{'='*55}")
    print(f"📥 原生 30分K 下載  ({len(sids)} 支)")
    print(f"   日期: {start_str} ~ {end_str}")
    print(f"   格式: KBarType.Min30 (原生)")
    print(f"   輸出: {DATA_DIR}/")
    print(f"{'='*55}\n")

    api = login_with_apikey()
    ok = fail = 0
    for sid in sids:
        df = download_30k(api, sid, start_str, end_str)
        if df is not None:
            save_kbar(sid, df, fmt=args.format)
            ok += 1
        else:
            fail += 1

    api.logout()
    print(f"\n{'='*55}")
    print(f"🏁 完成: {ok} 支成功, {fail} 支失敗")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
