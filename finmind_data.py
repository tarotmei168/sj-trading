#!/usr/bin/env python3
"""FinMind 資料抓取與快取工具。"""

import os
import json
from datetime import datetime

import pandas as pd
import requests

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
COLUMN_MAP = {
    'Trading_Volume': 'volume',
    'Trading_money': 'money',
    'open': 'open',
    'max': 'high',
    'min': 'low',
    'close': 'close',
}


def fetch_daily_price(ticker, start_date, end_date, dataset='TaiwanStockPrice'):
    params = {
        'dataset': dataset,
        'data_id': ticker,
        'start_date': start_date,
        'end_date': end_date,
    }
    r = requests.get(FINMIND_URL, params=params, timeout=30)
    data = r.json()
    if data.get('status') != 200:
        raise RuntimeError(f"FinMind error: {data.get('msg')}")
    rows = data.get('data', [])
    if not rows:
        return None

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    df = df.rename(columns=COLUMN_MAP)
    for c in ['open', 'high', 'low', 'close', 'volume']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df[['open', 'high', 'low', 'close', 'volume']].dropna()
    return df


def get_cache_path(ticker, start_date, end_date, cache_dir=None):
    if cache_dir is None:
        cache_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(cache_dir, exist_ok=True)
    filename = f"{ticker}_{start_date}_{end_date}.csv"
    return os.path.join(cache_dir, filename)


def load_cached_price(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['date'], index_col='date')
    return df


def save_cached_price(df, path):
    df.to_csv(path, index=True)


def load_or_fetch_daily_price(ticker, start_date, end_date, cache_dir=None):
    cache_path = get_cache_path(ticker, start_date, end_date, cache_dir)
    df = load_cached_price(cache_path)
    if df is not None and len(df) > 0:
        return df
    df = fetch_daily_price(ticker, start_date, end_date)
    if df is not None:
        save_cached_price(df, cache_path)
    return df
