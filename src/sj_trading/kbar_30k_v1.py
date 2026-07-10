#!/usr/bin/env python3
"""
Shioaji 1.5.4 版 30分K 下載器 🦞
====================================
1.5.4 沒有原生 KBarType.Min30，拉 1分K 合成 30分K。
shioaji_helper.py 也有用到這個 API 寫法。
"""
import sys, os, time
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 for Windows console
sys.stdout.reconfigure(encoding='utf-8')

import shioaji as sj

# ── .env ──
env_path = Path(__file__).resolve().parents[3] / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get('SHIOAJI_API_KEY') or os.environ.get('SJ_API_KEY')
SEC_KEY = os.environ.get('SHIOAJI_SECRET_KEY') or os.environ.get('SJ_SEC_KEY')

# ── watchlist ──
WATCHLIST = Path(__file__).resolve().parents[2] / 'watchlist.txt'

def parse_watchlist() -> list[str]:
    sids = []
    if not WATCHLIST.exists():
        print(f'⚠️ 找不到 watchlist: {WATCHLIST}')
        return sids
    with open(WATCHLIST, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if parts and parts[0].strip().isdigit():
                sids.append(parts[0].strip())
    return sids

# ── 合成 30分K ──
def aggregate_30k(bars) -> list[dict]:
    """從 1分K bars 合成 30分K"""
    if bars is None or len(bars.ts) == 0:
        return []

    ts_list = bars['ts']
    o = bars['Open']
    h = bars['High']
    l = bars['Low']
    c = bars['Close']
    v = bars['Volume']

    n = len(ts_list)
    result = []
    for i in range(0, n, 30):
        end = min(i + 30, n)
        result.append({
            'ts': ts_list[i],
            'open': o[i],
            'high': max(h[i:end]),
            'low': min(l[i:end]),
            'close': c[end - 1],
            'volume': sum(v[i:end]),
        })
    return result

# ── 存 CSV ──
OUT_DIR = Path(__file__).resolve().parents[2] / 'data_kbar_30m'
OUT_DIR.mkdir(parents=True, exist_ok=True)

def save_csv(sid: str, bars_30k: list[dict]):
    path = OUT_DIR / f'{sid}_30k.csv'
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write('ts,open,high,low,close,volume\n')
        for b in bars_30k:
            f.write(f'{b["ts"]},{b["open"]},{b["high"]},{b["low"]},{b["close"]},{b["volume"]}\n')
    print(f'  ✅ {sid}: {len(bars_30k)} 根 30分K → {path.name}')

# ── main ──
def main():
    sids = parse_watchlist()
    if not sids:
        print('❌ watchlist 沒股票')
        sys.exit(1)

    end = datetime.now()
    start = end - timedelta(days=45)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    print(f'📥 1分K → 30分K 下載 ({len(sids)} 支)')
    print(f'   日期: {start_str} ~ {end_str}')
    print(f'   輸出: {OUT_DIR}/\n')

    api = sj.Shioaji(simulation=True)
    api.login(api_key=API_KEY, secret_key=SEC_KEY, contracts_timeout=10000)

    ok = fail = 0
    for sid in sids:
        try:
            contract = api.Contracts.Stocks[sid]
            bars = api.kbars(contract=contract, start=start_str, end=end_str)
            if bars is None or len(bars.ts) == 0:
                print(f'  ⚠️  {sid}: 無資料')
                fail += 1
                continue

            bars_30k = aggregate_30k(bars)
            if bars_30k:
                save_csv(sid, bars_30k)
                ok += 1
            else:
                print(f'  ⚠️  {sid}: 合成後為空')
                fail += 1
        except Exception as e:
            print(f'  ❌ {sid}: {e}')
            fail += 1

        time.sleep(0.25)  # 避免打太急

    api.logout()
    print(f'\n🏁 完成: {ok} 支成功, {fail} 支失敗')

if __name__ == '__main__':
    main()
