#!/usr/bin/env python3
"""30分K KD + 價量黃金交叉回測（純 yfinance / 30m）

此腳本不依賴 Shioaji 或 CA 憑證，直接使用 yfinance 抓取臺股 30 分鐘線，
並測試 30 分 KD 黃金交叉與量能 / 價格配合的買賣條件。
"""

import argparse
import math
from datetime import timedelta

import numpy as np
import pandas as pd
import yfinance as yf


DEFAULT_TICKERS = [
    "3711", "4958", "3042", "2337", "2436", "6139",
    "2330", "2454", "2303", "2317", "8150", "2344",
]


def fetch_30min_bars(ticker_id, period="180d"):
    """Fetch the last 30-min bars from yfinance for a Taiwan ticker."""
    for suffix in [".TW", ".TWO"]:
        ticker = f"{ticker_id}{suffix}"
        df = yf.Ticker(ticker).history(period=period, interval="30m")
        if df is not None and not df.empty:
            df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
            df = df[["open", "high", "low", "close", "volume"]].copy()
            df = df.dropna()
            if len(df) >= 50:
                return df
    return None


def compute_kd(df, k_period=9, d_period=3, rsv_period=9):
    """Compute KD values for 30m bars."""
    df = df.copy()
    low_min = df["low"].rolling(window=rsv_period, min_periods=1).min()
    high_max = df["high"].rolling(window=rsv_period, min_periods=1).max()
    denom = high_max - low_min
    rsv = pd.Series(np.where(denom == 0, 50.0, (df["close"] - low_min) / denom * 100), index=df.index)

    k = pd.Series(50.0, index=df.index)
    d = pd.Series(50.0, index=df.index)
    for i in range(1, len(df)):
        k.iloc[i] = (2 / 3) * k.iloc[i - 1] + (1 / 3) * rsv.iloc[i]
        d.iloc[i] = (2 / 3) * d.iloc[i - 1] + (1 / 3) * k.iloc[i]

    df["K"] = k
    df["D"] = d
    return df


def add_volume_price_features(df):
    """Add volume and price strength indicators."""
    df = df.copy()
    df["vol_ma5"] = df["volume"].rolling(window=5, min_periods=1).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma5"].replace({0: np.nan})
    df["prev_close"] = df["close"].shift(1)
    df["price_change_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"].replace({0: np.nan}) * 100
    df["price_up"] = df["price_change_pct"] > 0
    return df


def signal_buy(row, buy_k, min_vol_ratio, min_price_pct):
    """Return True when a price/volume-enhanced KD golden cross buy signal appears."""
    if not row.get("golden_cross", False):
        return False
    if row["K"] >= buy_k:
        return False
    if math.isnan(row["vol_ratio"]) or math.isnan(row["price_change_pct"]):
        return False
    return row["vol_ratio"] >= min_vol_ratio or row["price_change_pct"] >= min_price_pct


def signal_sell(row, sell_k):
    """Return True when a valid sell condition appears."""
    if not row.get("death_cross", False):
        return False
    return row["K_prev"] >= sell_k


def prepare_signals(df):
    """Compute KD cross signals and attach helper columns."""
    df = df.copy()
    df["K_prev"] = df["K"].shift(1)
    df["D_prev"] = df["D"].shift(1)
    df["golden_cross"] = (df["K_prev"] <= df["D_prev"]) & (df["K"] > df["D"])
    df["death_cross"] = (df["K_prev"] >= df["D_prev"]) & (df["K"] < df["D"])
    return df


def run_backtest(df, params, initial_capital=100000):
    """Run a single backtest, returning metrics and detailed trades."""
    df = compute_kd(df, params["k_period"], params["d_period"], params["rsv_period"])
    df = add_volume_price_features(df)
    df = prepare_signals(df)

    capital = float(initial_capital)
    position = 0
    entry_price = 0.0
    entry_index = None
    equity_curve = [capital]
    trades = []

    for idx in range(1, len(df)):
        row = df.iloc[idx]
        if position == 0:
            if signal_buy(row, params["buy_k"], params["min_vol_ratio"], params["min_price_pct"]):
                shares = int(capital / row["close"])
                if shares <= 0:
                    continue
                position = shares
                entry_price = row["close"]
                entry_index = idx
                capital -= shares * entry_price
                trades.append({"entry_time": row.name, "entry_price": entry_price})
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
                    "exit_time": row.name,
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "hold_bars": idx - entry_index,
                    "reason": "death_cross" if row.get("death_cross", False) else (
                        "take_profit" if pnl_pct >= params["take_profit"] else "stop_loss"
                    ),
                })
                position = 0
                entry_price = 0.0
                entry_index = None
                equity_curve.append(capital)

    if position > 0:
        exit_price = df.iloc[-1]["close"]
        pnl_pct = (exit_price / entry_price - 1) * 100
        capital += position * exit_price
        trades[-1].update({
            "exit_time": df.iloc[-1].name,
            "exit_price": exit_price,
            "pnl_pct": round(pnl_pct, 2),
            "hold_bars": len(df) - entry_index - 1,
            "reason": "end_of_data",
        })
        equity_curve.append(capital)

    if not trades:
        return None

    total_return = (capital / float(initial_capital) - 1) * 100
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    losses = sum(1 for t in trades if t["pnl_pct"] <= 0)
    avg_trade = sum(t["pnl_pct"] for t in trades) / len(trades)
    win_rate = wins / len(trades) * 100
    max_dd = compute_max_drawdown(equity_curve)

    return {
        "params": params,
        "total_return": round(total_return, 2),
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "avg_trade": round(avg_trade, 2),
        "max_drawdown": round(max_dd, 2),
        "trades_detail": trades,
    }


def compute_max_drawdown(equity_curve):
    max_peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        max_peak = max(max_peak, value)
        drawdown = (max_peak - value) / max_peak * 100
        max_dd = max(max_dd, drawdown)
    return max_dd


def optimize_parameters(df, grid):
    """Search the best parameter combination based on total return."""
    best = None
    for params in grid:
        result = run_backtest(df, params)
        if result is None:
            continue
        if best is None or result["total_return"] > best["total_return"]:
            best = result
    return best


def build_grid():
    grid = []
    for k_period in [3, 5, 7, 9]:
        for buy_k in [30, 35, 40, 45, 50]:
            for min_vol_ratio in [1.0, 1.3, 1.7, 2.2]:
                for min_price_pct in [0.0, 0.2, 0.5]:
                    for sell_k in [55, 60, 65, 70]:
                        for stop_loss in [3, 4, 5]:
                            for take_profit in [4, 6, 8]:
                                grid.append({
                                    "k_period": k_period,
                                    "d_period": 3,
                                    "rsv_period": 9,
                                    "buy_k": buy_k,
                                    "min_vol_ratio": min_vol_ratio,
                                    "min_price_pct": min_price_pct,
                                    "sell_k": sell_k,
                                    "stop_loss": stop_loss,
                                    "take_profit": take_profit,
                                })
    return grid


def summarize_results(results):
    lines = ["30分KD價量黃金交叉回測結果"]
    for r in sorted(results, key=lambda x: x["metrics"]["total_return"], reverse=True):
        lines.append(
            f"{r['ticker']}  {r['name']}  收益={r['metrics']['total_return']:+.2f}%  "
            f"交易={r['metrics']['trades']}  勝率={r['metrics']['win_rate']}%  "
            f"最大回撤={r['metrics']['max_drawdown']}%  "
            f"最佳K={r['metrics']['params']['k_period']} 買K<{r['metrics']['params']['buy_k']} "
            f"量比>={r['metrics']['params']['min_vol_ratio']}  價量增<={r['metrics']['params']['min_price_pct']}%"
        )
    return "\n".join(lines)


def main(tickers, period="180d"):
    grid = build_grid()
    results = []
    for ticker_id in tickers:
        name = ticker_id
        df = fetch_30min_bars(ticker_id, period)
        if df is None:
            print(f"{ticker_id}: 30m 資料讀取失敗或不夠長，跳過")
            continue

        best = optimize_parameters(df, grid)
        if best is None:
            print(f"{ticker_id}: 無有效交易")
            continue

        print(
            f"{ticker_id}: best={best['total_return']:+.2f}% trades={best['trades']} "
            f"win={best['win_rate']}% max_dd={best['max_drawdown']}% params={best['params']}"
        )

        results.append({"ticker": ticker_id, "name": name, "metrics": best})

    print("\n" + summarize_results(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="30m KD backtest with volume/price golden cross")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS, help="股票代碼清單")
    parser.add_argument("--period", default="180d", help="yfinance 資料期間，例如 180d、1y")
    args = parser.parse_args()
    main(args.tickers, period=args.period)
