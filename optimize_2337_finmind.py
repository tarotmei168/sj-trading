#!/usr/bin/env python3
"""Optimize buy/exit rules for 2337 using FinMind historical data.
Fetches daily price from FinMind and runs a grid search over buy triggers
(for oversold zone + deviation + days-since-min) and exit rules (profit target
or KD threshold). Reports top parameter sets by win rate and recovery.
"""
import json
import math
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from finmind_data import load_or_fetch_daily_price

USER_COST = 190.0
TICKER = '2337'


def compute_indicators(df):
    df = df.copy()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA60'] = df['close'].rolling(60).mean()
    # KD (K=9,D=3 RSV 9)
    rsv = (df['close'] - df['low'].rolling(9).min()) / (df['high'].rolling(9).max() - df['low'].rolling(9).min()) * 100
    rsv = rsv.fillna(50)
    k = pd.Series(50.0, index=df.index)
    d = pd.Series(50.0, index=df.index)
    for i in range(1, len(df)):
        k.iloc[i] = (2/3)*k.iloc[i-1] + (1/3)*rsv.iloc[i]
        d.iloc[i] = (2/3)*d.iloc[i-1] + (1/3)*k.iloc[i]
    df['K'] = k; df['D'] = d
    # RSI 14
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100/(1+rs))
    return df


def simulate(df, params, user_cost=USER_COST):
    # single-share fixed-size trades
    trades = []
    holding = False
    entry_price = None
    entry_idx = None
    equity = 0
    for idx in range(len(df)):
        row = df.iloc[idx]
        date = row.name
        price = row['close']
        # compute days since N-day rolling min index
        window = params['min_window']
        start_i = max(0, idx - window + 1)
        window_lows = df['low'].iloc[start_i:idx+1]
        local_min_idx = window_lows.idxmin()
        days_since_min = (date - local_min_idx).days if not pd.isna(local_min_idx) else 999

        if not holding:
            # require price in oversold range
            if price > params['oversold_max'] or price < params['oversold_min']:
                continue
            # require deviation vs MA20
            ma20 = row['MA20'] if not math.isnan(row['MA20']) else None
            if ma20 is None: continue
            dev = (price - ma20) / ma20 * 100
            if dev > -params['dev_pct']:
                continue
            # require days since local min >= threshold
            if days_since_min < params['days_since_min']:
                continue
            # buy
            holding = True
            entry_price = price
            entry_idx = idx
            trades.append({'entry_date': date, 'entry_price': entry_price})
        else:
            # exit conditions
            # profit target relative to user cost
            if price >= user_cost * (1 + params['profit_target']/100):
                # close
                trades[-1].update({'exit_date': date, 'exit_price': price, 'reason': f'profit_{params["profit_target"]}%'})
                holding = False
                entry_price = None
                entry_idx = None
                continue
            # KD threshold
            if row['K'] >= params['exit_k']:
                trades[-1].update({'exit_date': date, 'exit_price': price, 'reason': f'KD_{params["exit_k"]}'})
                holding = False
                entry_price = None
                entry_idx = None
                continue
            # stop loss
            if (price / trades[-1]['entry_price'] - 1) * 100 <= -params['stop_loss']:
                trades[-1].update({'exit_date': date, 'exit_price': price, 'reason': 'stop_loss'})
                holding = False
                entry_price = None
                entry_idx = None
                continue
    # if still holding, close at last price
    if holding and trades:
        last_price = df['close'].iloc[-1]
        trades[-1].update({'exit_date': df.index[-1], 'exit_price': last_price, 'reason': 'end'})
    # calculate metrics
    if not trades:
        return None
    wins = sum(1 for t in trades if t.get('exit_price',0) > t['entry_price'])
    total = len(trades)
    win_rate = wins / total * 100
    avg_ret = sum(((t['exit_price']/t['entry_price']-1)*100) for t in trades)/total
    # recovery: percent of trades that exit at or above user_cost
    recovered = sum(1 for t in trades if t.get('exit_price',0) >= user_cost)
    recovery_rate = recovered / total * 100
    total_return = sum((t['exit_price']/t['entry_price']-1)*100 for t in trades)
    return {'params': params, 'trades': total, 'wins': wins, 'win_rate': round(win_rate,1), 'avg_ret': round(avg_ret,2), 'recovery_rate': round(recovery_rate,1), 'total_return': round(total_return,2), 'trades_detail': trades}


def grid_search(df, user_cost=USER_COST):
    grid = []
    # oversold ranges focusing on 120s
    oversold_options = [(110,130),(115,130),(120,130),(120,125)]
    dev_options = [10,15,20]  # percent below MA20
    days_since_min_opts = [0,1,2,3,5]
    profit_targets = [0,3,5,8,12]
    exit_k_opts = [50,60,70]
    stop_loss_opts = [15,20,25]
    min_window_opts = [7,14,30]

    results = []
    total = len(oversold_options)*len(dev_options)*len(days_since_min_opts)*len(profit_targets)*len(exit_k_opts)*len(stop_loss_opts)*len(min_window_opts)
    count = 0
    for overs in oversold_options:
        for dev in dev_options:
            for days in days_since_min_opts:
                for pt in profit_targets:
                    for ek in exit_k_opts:
                        for sl in stop_loss_opts:
                            for mw in min_window_opts:
                                params = {'oversold_min': overs[0], 'oversold_max': overs[1], 'dev_pct': dev, 'days_since_min': days, 'profit_target': pt, 'exit_k': ek, 'stop_loss': sl, 'min_window': mw}
                                res = simulate(df, params, user_cost)
                                count += 1
                                if res:
                                    results.append(res)
    return results


def summarize(results, topn=10):
    if not results:
        print('No results')
        return
    # sort by win_rate desc then recovery_rate desc
    sorted_res = sorted(results, key=lambda r: (r['win_rate'], r['recovery_rate'], r['avg_ret']), reverse=True)
    print('Top parameter sets (by win_rate, recovery_rate):')
    for r in sorted_res[:topn]:
        p = r['params']
        print(f"win={r['win_rate']}% recov={r['recovery_rate']}% trades={r['trades']} avg_ret={r['avg_ret']}% total_ret={r['total_return']}% -> overs={p['oversold_min']}-{p['oversold_max']} dev={p['dev_pct']}% days_since_min={p['days_since_min']} profit_target={p['profit_target']}% exit_k={p['exit_k']} stop_loss={p['stop_loss']}% window={p['min_window']}")


def load_2337_data(start_date, end_date, cache_dir=None):
    df = load_or_fetch_daily_price(TICKER, start_date, end_date, cache_dir=cache_dir)
    if df is None or len(df) < 200:
        raise RuntimeError('No data')
    return df


def run_optimization(start_date, end_date, cache_dir=None, output_json='optimize_2337_results.json'):
    print(f'Fetching {TICKER} from FinMind {start_date} to {end_date} ...')
    df = load_2337_data(start_date, end_date, cache_dir)
    print('Compute indicators...')
    df = compute_indicators(df)
    print('Running grid search (may take a while)...')
    results = grid_search(df)
    print(f'Completed grid search, found {len(results)} parameter results')
    summarize(results, topn=20)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, default=str, ensure_ascii=False, indent=2)
    print(f'Saved {output_json}')
    return results


if __name__ == '__main__':
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=365*2)).strftime('%Y-%m-%d')
    run_optimization(start, end)
