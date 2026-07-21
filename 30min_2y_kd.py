#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""30 分 K 本機下載與 KD 黃金交叉分析

這個腳本支援：
- 永豐 Shioaji 下載原生 30 分 K（KBarType.Min30）
- 3 年以上資料分段抓取並合併
- 存成本機 parquet/csv/json
- 讀取本機資料，計算 30 分 KD
- 找出黃金交叉與量價訊號
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import shioaji as sj

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "kbar_30m"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_PATH = ROOT / ".env"


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


ENV = load_env(ENV_PATH)


def getenv(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key) or ENV.get(key) or default


def login() -> sj.Shioaji:
    api_key = getenv("SJ_API_KEY")
    secret_key = getenv("SJ_SEC_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("缺少 SJ_API_KEY / SJ_SEC_KEY，請先設定 .env")

    api = sj.Shioaji(simulation=False)
    api.login(api_key=api_key, secret_key=secret_key, subscribe_trade=False)
    return api


def download_30m_kbars(api: sj.Shioaji, sid: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    contract = api.Contracts.Stocks.get(sid)
    if contract is None:
        raise ValueError(f"找不到股票代號 {sid}")

    try:
        kbars = api.kbars(contract=contract, start=start_date, end=end_date)
    except Exception as exc:
        print(f"    ❌ {sid} 下載錯誤: {exc}")
        return None

    if kbars is None or len(kbars.ts) == 0:
        return None

    df = pd.DataFrame({**kbars})
    df["ts"] = pd.to_datetime(df["ts"])
    df.rename(columns={
        "ts": "datetime",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "Amount": "amount",
    }, inplace=True)
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if "amount" not in df.columns:
        df["amount"] = 0

    df_30m = (
        df.set_index("datetime")
        .resample("30min", label="right", closed="right")
        .agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "amount": "sum",
        })
        .dropna(subset=["open", "close"])
        .reset_index()
    )
    return df_30m[["datetime", "open", "high", "low", "close", "volume", "amount"]]


def chunked_download(api: sj.Shioaji, sid: str, start_date: str, end_date: str, chunk_days: int = 180) -> pd.DataFrame | None:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    segments = []
    current_start = start_dt
    while current_start < end_dt:
        current_end = min(current_start + timedelta(days=chunk_days), end_dt)
        seg_start = current_start.strftime("%Y-%m-%d")
        seg_end = current_end.strftime("%Y-%m-%d")
        print(f"  下載分段: {sid} {seg_start} ~ {seg_end}")
        segment = download_30m_kbars(api, sid, seg_start, seg_end)
        if segment is None or segment.empty:
            print(f"    ⚠️ {sid} {seg_start}~{seg_end} 無資料")
        else:
            segments.append(segment)
            print(f"    ✅ {sid} 取得 {len(segment)} 筆 30 分 K")
        current_start = current_end
    if not segments:
        return None
    df = pd.concat(segments, ignore_index=True)
    df.drop_duplicates(subset=["datetime"], keep="last", inplace=True)
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def save_kbars(df: pd.DataFrame, sid: str, fmt: str = "parquet") -> Path:
    path = DATA_DIR / f"{sid}.{fmt}"
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    elif fmt == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif fmt == "json":
        records = df.copy()
        records["datetime"] = records["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
        records.to_json(path, orient="records", force_ascii=False, indent=2)
    else:
        raise ValueError(f"不支援格式: {fmt}")
    return path


def load_kbars(sid: str, fmt: str | None = None) -> pd.DataFrame | None:
    base = DATA_DIR / sid
    if fmt is None:
        for ext in ["parquet", "csv", "json"]:
            p = base.with_suffix(f".{ext}")
            if p.exists():
                fmt = ext
                break
    if fmt is None:
        return None
    path = base.with_suffix(f".{fmt}")
    if not path.exists():
        return None
    if fmt == "parquet":
        return pd.read_parquet(path)
    elif fmt == "csv":
        return pd.read_csv(path, parse_dates=["datetime"])
    elif fmt == "json":
        df = pd.read_json(path, orient="records")
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df
    return None


def compute_kd(df: pd.DataFrame, rsv_days: int = 9, k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
    df = df.copy()
    df["low_min"] = df["low"].rolling(rsv_days).min()
    df["high_max"] = df["high"].rolling(rsv_days).max()
    df["rsv"] = ((df["close"] - df["low_min"]) / (df["high_max"] - df["low_min"])) * 100
    df["rsv"] = df["rsv"].fillna(50)

    k = [50.0] * len(df)
    d = [50.0] * len(df)
    for i in range(1, len(df)):
        k[i] = (k[i - 1] * (k_period - 1) + df.loc[df.index[i], "rsv"]) / k_period
        d[i] = (d[i - 1] * (d_period - 1) + k[i]) / d_period
    df[f"K_{rsv_days}"] = k
    df[f"D_{rsv_days}"] = d
    df["K"] = df[f"K_{rsv_days}"]
    df["D"] = df[f"D_{rsv_days}"]
    return df


def find_golden_cross(df: pd.DataFrame, k_col: str, d_col: str) -> pd.DataFrame:
    df = df.copy()
    df["prev_k"] = df[k_col].shift(1)
    df["prev_d"] = df[d_col].shift(1)
    df["golden_cross"] = (df["prev_k"] <= df["prev_d"]) & (df[k_col] > df[d_col])
    return df[df["golden_cross"]]


def build_volume_signal(df: pd.DataFrame, lookback: int = 5, volume_mult: float = 1.2) -> pd.DataFrame:
    df = df.copy()
    df["volume_avg"] = df["volume"].rolling(lookback).mean()
    df["vol_ratio"] = df["volume"] / df["volume_avg"].replace({0: float("nan")})
    df["volume_signal"] = df["vol_ratio"] >= volume_mult
    return df


def prepare_signals(df: pd.DataFrame, k_col: str, d_col: str) -> pd.DataFrame:
    df = df.copy()
    df["K_prev"] = df[k_col].shift(1)
    df["D_prev"] = df[d_col].shift(1)
    df["golden_cross"] = (df["K_prev"] <= df["D_prev"]) & (df[k_col] > df[d_col])
    df["death_cross"] = (df["K_prev"] >= df["D_prev"]) & (df[k_col] < df[d_col])
    return df


def signal_buy(row, buy_k: float, min_vol_ratio: float, min_price_pct: float) -> bool:
    if not row.get("golden_cross", False):
        return False
    if row["K"] >= buy_k:
        return False
    if row.get("vol_ratio", 0) >= min_vol_ratio or row.get("price_change_pct", 0) >= min_price_pct:
        return True
    return False


def signal_sell(row, sell_k: float) -> bool:
    return row.get("death_cross", False) and row.get("K_prev", 0) >= sell_k


def run_backtest(df: pd.DataFrame, params: dict, initial_capital: float = 100000) -> dict | None:
    df = compute_kd(df, rsv_days=params["rsv_days"], k_period=params["k_period"], d_period=params["d_period"])
    df = build_volume_signal(df, lookback=5, volume_mult=params["min_vol_ratio"])
    df["prev_close"] = df["close"].shift(1)
    df["price_change_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"].replace({0: float("nan")}) * 100
    df = prepare_signals(df, "K", "D")

    capital = float(initial_capital)
    position = 0
    entry_price = 0.0
    entry_idx = None
    trades = []
    equity_curve = []

    for idx in range(1, len(df)):
        row = df.iloc[idx]
        if position == 0:
            if signal_buy(row, params["buy_k"], params["min_vol_ratio"], params["min_price_pct"]):
                shares = int(capital / row["close"])
                if shares <= 0:
                    equity_curve.append(capital)
                    continue
                position = shares
                entry_price = row["close"]
                entry_idx = idx
                capital -= shares * entry_price
                trades.append({
                    "entry_time": row["datetime"],
                    "entry_price": entry_price,
                    "shares": shares,
                })
        else:
            if signal_sell(row, params["sell_k"]) or (
                (row["close"] / entry_price - 1) * 100 <= -params["stop_loss"]
            ) or (
                (row["close"] / entry_price - 1) * 100 >= params["take_profit"]
            ):
                exit_price = row["close"]
                pnl_pct = (exit_price / entry_price - 1) * 100
                capital += position * exit_price
                trades[-1].update({
                    "exit_time": row["datetime"],
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "hold_bars": idx - entry_idx,
                    "reason": "death_cross" if row.get("death_cross", False) else (
                        "take_profit" if pnl_pct >= params["take_profit"] else "stop_loss"
                    ),
                })
                position = 0
                entry_price = 0.0
                entry_idx = None
        equity_curve.append(capital + position * row["close"])

    if position > 0:
        exit_price = df.iloc[-1]["close"]
        pnl_pct = (exit_price / entry_price - 1) * 100
        capital += position * exit_price
        trades[-1].update({
            "exit_time": df.iloc[-1]["datetime"],
            "exit_price": exit_price,
            "pnl_pct": round(pnl_pct, 2),
            "hold_bars": len(df) - entry_idx - 1,
            "reason": "end_of_data",
        })
        equity_curve.append(capital)

    if not trades:
        return None

    total_return = (capital / initial_capital - 1) * 100
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    avg_trade = sum(t["pnl_pct"] for t in trades) / len(trades)
    win_rate = wins / len(trades) * 100
    peak = initial_capital
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = (peak - value) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, drawdown)

    return {
        "params": params,
        "total_return": round(total_return, 2),
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round(win_rate, 1),
        "avg_trade": round(avg_trade, 2),
        "max_drawdown": round(max_dd, 2),
        "trades_detail": trades,
    }


def build_grid() -> list[dict]:
    grid = []
    for rsv_days in [7, 9, 12]:
        for k_period in [3, 5]:
            for d_period in [3, 5]:
                for buy_k in [20, 30, 40]:
                    for sell_k in [70, 80, 90]:
                        for min_vol_ratio in [1.0, 1.2, 1.5]:
                            for min_price_pct in [0.0, 0.5, 1.0]:
                                for stop_loss in [2.0, 3.0, 5.0]:
                                    for take_profit in [2.0, 3.0, 5.0]:
                                        grid.append({
                                            "rsv_days": rsv_days,
                                            "k_period": k_period,
                                            "d_period": d_period,
                                            "buy_k": buy_k,
                                            "sell_k": sell_k,
                                            "min_vol_ratio": min_vol_ratio,
                                            "min_price_pct": min_price_pct,
                                            "stop_loss": stop_loss,
                                            "take_profit": take_profit,
                                        })
    return grid


def optimize_parameters(df: pd.DataFrame, max_trials: int = 100) -> dict | None:
    best_result = None
    grid = build_grid()
    for i, params in enumerate(grid, start=1):
        result = run_backtest(df, params)
        if result is None:
            continue
        if best_result is None or result["total_return"] > best_result["total_return"]:
            best_result = result
    return best_result


def print_best_strategy(df: pd.DataFrame, sid: str) -> None:
    best = optimize_parameters(df)
    if best is None:
        print(f"❌ {sid} 無有效回測結果")
        return
    params = best["params"]
    print(f"\n=== {sid} 最佳歷史策略 ===")
    print(f"  總報酬: {best['total_return']}%")
    print(f"  交易次數: {best['trades']}  勝率: {best['win_rate']}%  平均每筆: {best['avg_trade']}%")
    print(f"  最大回撤: {best['max_drawdown']}%")
    print(f"  參數: RSV={params['rsv_days']}  K週期={params['k_period']}  D週期={params['d_period']}")
    print(f"        買K<{params['buy_k']}  賣K={params['sell_k']}")
    print(f"        量比>={params['min_vol_ratio']}  價量增>={params['min_price_pct']}%")
    print(f"        止損={params['stop_loss']}%  止盈={params['take_profit']}%")


def print_analysis(df: pd.DataFrame, sid: str, rsv_days: int = 9, volume_mult: float = 1.2) -> None:
    df = compute_kd(df, rsv_days=rsv_days)
    df = build_volume_signal(df, lookback=5, volume_mult=volume_mult)
    df["prev_close"] = df["close"].shift(1)
    df["price_change_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"].replace({0: float("nan")}) * 100
    df = prepare_signals(df, "K", "D")

    golden = df[df["golden_cross"]].tail(5)
    print(f"\n=== {sid} KD 分析結果 ===")
    print(f"  資料筆數: {len(df)}  最後時間: {df.iloc[-1]['datetime'] if len(df) else 'N/A'}")
    print(f"  最後 K/D: {df.iloc[-1]['K']:.2f}/{df.iloc[-1]['D']:.2f}")
    print(f"  最近 5 次金叉: {len(golden)}")
    if golden.empty:
        print("    無金叉訊號")
    else:
        for _, row in golden.iterrows():
            print(f"    {row['datetime']} K={row['K']:.1f} D={row['D']:.1f} vol_ratio={row.get('vol_ratio', 0):.2f} price_pct={row.get('price_change_pct', 0):.2f}")
    avg_vol_ratio = df['vol_ratio'].dropna().tail(5).mean()
    print(f"  量增門檻: {volume_mult}  最近 5 根平均量比: {avg_vol_ratio:.2f}")


def parse_watchlist(path: Path | None = None) -> list[str]:
    if path is None:
        path = ROOT / "watchlist.txt"
    if not path.exists():
        return []
    sids = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sid = line.split(",")[0].strip()
            if sid.isdigit():
                sids.append(sid)
    return sids


def main() -> None:
    parser = argparse.ArgumentParser(description="永豐 30 分 K 本機下載 + KD 黃金交叉分析")
    parser.add_argument("--sid", type=str, default=None, help="股票代號，逗號分隔。預設從 watchlist.txt 讀取")
    parser.add_argument("--start", type=str, default=None, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="結束日期 YYYY-MM-DD")
    parser.add_argument("--download", action="store_true", help="下載 30 分 K 並存本機")
    parser.add_argument("--analyze", action="store_true", help="從本機資料計算 KD 黃金交叉")
    parser.add_argument("--optimize", action="store_true", help="回測並搜尋最高報酬策略")
    parser.add_argument("--format", type=str, default="parquet", choices=["parquet", "csv", "json"], help="本機存檔格式")
    parser.add_argument("--chunk-days", type=int, default=180, help="下載分段天數，預設 180")
    parser.add_argument("--rsv-days", type=int, default=9, help="KD RSV 天數，預設 9")
    parser.add_argument("--volume-mult", type=float, default=1.2, help="成交量多於平均的倍數才視為量增")
    args = parser.parse_args()

    if args.sid:
        sids = [s.strip() for s in args.sid.split(",") if s.strip()]
    else:
        sids = parse_watchlist()
    if not sids:
        raise SystemExit("請指定 --sid 或 watchlist.txt 裡要抓的股票")

    if args.end:
        end_date = args.end
    else:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if args.start:
        start_date = args.start
    else:
        start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

    if args.download:
        api = login()
        try:
            for sid in sids:
                print(f"\n=== 下載 {sid} 30 分 K ({start_date} ~ {end_date}) ===")
                df = chunked_download(api, sid, start_date, end_date, chunk_days=args.chunk_days)
                if df is None or df.empty:
                    print(f"⚠️ {sid} 無資料，跳過存檔")
                    continue
                path = save_kbars(df, sid, fmt=args.format)
                print(f"✅ {sid} 存檔完成: {path}")
        finally:
            api.logout()
    if args.analyze or args.optimize:
        for sid in sids:
            df = load_kbars(sid)
            if df is None:
                print(f"❌ {sid} 無本機資料，請先 --download")
                continue
            if args.optimize:
                print_best_strategy(df, sid)
            else:
                print_analysis(df, sid, rsv_days=args.rsv_days, volume_mult=args.volume_mult)


if __name__ == "__main__":
    main()
