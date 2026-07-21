"""
30分K 價量黃金交叉掃描 - 用 Shioaji 即時分鐘資料
因為現在14:01剛收盤，盤中分鐘K還熱的
"""
import sys, os
sys.path.insert(0, r"C:\Users\User\.openclaw\workspace\sj-trading")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv(r"C:\Users\User\.openclaw\workspace\sj-trading\.env")

from src.sj_trading.shioaji_helper import get_kbars_45d, is_simulation_mode, load_config

TZ = timezone(timedelta(hours=8))

CORE_STOCKS = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科",
    "3711": "日月光投控", "4958": "臻鼎-KY", "3042": "晶技",
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "8150": "南茂"
}

def calc_kd(high, low, close, n=9):
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = ((close - low_n) / (high_n - low_n)) * 100
    rsv = rsv.fillna(50).clip(0, 100)
    k = pd.Series(np.zeros(len(rsv)), index=rsv.index, dtype=float)
    d = pd.Series(np.zeros(len(rsv)), index=rsv.index, dtype=float)
    k.iloc[0] = 50
    d.iloc[0] = 50
    for i in range(1, len(rsv)):
        k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
        d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
    return k, d

def main():
    print("=" * 65)
    print("  核心持股 30分K KD價量黃金交叉掃描")
    print(f"  時間: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65)

    print(f"\n API Key 狀態: {'✅ 有 Key' if not is_simulation_mode() else '⚠️  模擬模式 (無 Key)'}")
    cfg = load_config()
    print(f"  帳號: {cfg['api_key'][:4]}...{cfg['api_key'][-4:]}")

    # 抓最近 7 天的分鐘K (盤後也能抓到)
    print(f"\n 下載分鐘K線中...")
    stock_ids = list(CORE_STOCKS.keys())
    kbars = get_kbars_45d(stock_ids, use_cache=False, force_download=True)

    results = []

    for sid, sname in CORE_STOCKS.items():
        if sid not in kbars or kbars[sid] is None or len(kbars[sid]) < 30:
            print(f"  {sid} {sname}: 資料不足, 跳過")
            continue

        df = kbars[sid].copy()
        if 'ts' not in df.columns:
            continue

        df['datetime'] = pd.to_datetime(df['ts'])
        df = df.set_index('datetime')
        df = df.sort_index()

        # 只取最近 7 天
        cutoff = pd.Timestamp.now(tz=TZ) - timedelta(days=7)
        df = df[df.index.tz_localize(TZ, ambiguous='infer') >= cutoff] if df.index.tz is None else df

        # 重採樣為 30分K
        ohlc = df.resample('30min', closed='right', label='right').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()

        if len(ohlc) < 20:
            print(f"  {sid} {sname}: 30分K不足20根 ({len(ohlc)})")
            continue

        k, d = calc_kd(ohlc['High'], ohlc['Low'], ohlc['Close'])
        ma20 = ohlc['Close'].rolling(20).mean()
        vol_ma5 = ohlc['Volume'].rolling(5).mean()

        last = ohlc.iloc[-1]
        last_k = k.iloc[-1]
        last_d = d.iloc[-1]
        last_ma20 = ma20.iloc[-1]
        last_vol_ma5 = vol_ma5.iloc[-1]

        prev_k = k.iloc[-2] if len(k) >= 2 else None
        prev_d = d.iloc[-2] if len(d) >= 2 else None

        reasons = []
        score = 0

        # 條件1: KD黃金交叉
        kd_golden = False
        if prev_k is not None and prev_d is not None:
            if prev_k <= prev_d and last_k > last_d:
                kd_golden = True
                reasons.append(f"K上穿D({last_k:.1f}>{last_d:.1f})")
            elif last_k > last_d:
                kd_golden = True
                reasons.append(f"K>D({last_k:.1f}>{last_d:.1f})")
        if kd_golden:
            score += 1

        # 條件2: 低檔
        if last_k < 40:
            score += 1
            reasons.append(f"低檔K={last_k:.1f}")
        elif last_k < 50:
            reasons.append(f"中檔K={last_k:.1f}")
        else:
            reasons.append(f"高檔K={last_k:.1f}")

        # 條件3: 價量配合
        vol_ratio = last['Volume'] / last_vol_ma5 if last_vol_ma5 > 0 else 0
        if vol_ratio >= 1.5:
            score += 1
            reasons.append(f"量{int(last['Volume'])}>{int(last_vol_ma5)}x1.5")
        elif vol_ratio >= 1.2:
            reasons.append(f"量微增{vol_ratio:.1f}x")
        else:
            reasons.append(f"量不足{vol_ratio:.1f}x")

        # 條件4: 站上20MA
        if not pd.isna(last_ma20) and last['Close'] > last_ma20:
            score += 1
            reasons.append(f"價{last['Close']:.1f}>20MA{last_ma20:.1f}")
        else:
            ma20v = f"{last_ma20:.1f}" if not pd.isna(last_ma20) else "N/A"
            reasons.append(f"價{last['Close']:.1f}<20MA{ma20v}")

        # 條件5: 趨勢偏多
        if len(ohlc) >= 4:
            if (ohlc['Close'].iloc[-1] > ohlc['Close'].iloc[-2] and
                ohlc['Close'].iloc[-2] > ohlc['Close'].iloc[-3]):
                score += 1
                reasons.append("連3根漲")

        results.append({
            "stock_id": sid,
            "stock_name": sname,
            "time": ohlc.index[-1].strftime("%m/%d %H:%M"),
            "price": round(last['Close'], 2),
            "k": round(last_k, 1),
            "d": round(last_d, 1),
            "volume": int(last['Volume']),
            "vol_ma5": int(last_vol_ma5),
            "vol_ratio": round(vol_ratio, 1),
            "ma20": round(last_ma20, 1) if not pd.isna(last_ma20) else "N/A",
            "score": score,
            "reason": ", ".join(reasons)
        })

    # 排序: 高分在前
    results.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n{'='*65}")
    print(f"  RESULT")
    print(f"{'='*65}")

    strong = [r for r in results if r['score'] >= 3]
    normal = [r for r in results if 1 <= r['score'] <= 2]
    none_signal = [r for r in results if r['score'] == 0]

    if strong:
        print(f"\n[強烈訊號 Score 3-5] 可考慮平倉:")
        print(f"{'代號':<8} {'名稱':<10} {'時間':<12} {'價':<8} {'K/D':<10} {'量比':<8} {'分數':<6} 條件")
        print("-" * 100)
        for r in strong:
            print(f"{r['stock_id']:<8} {r['stock_name']:<10} {r['time']:<12} {r['price']:<8} {r['k']}/{r['d']:<8} {r['vol_ratio']:<8} {r['score']}/5  {r['reason']}")
    else:
        print(f"\n 目前無強烈訊號 (Score >= 3)")

    if normal:
        print(f"\n[一般訊號 Score 1-2]:")
        for r in normal:
            print(f"  {r['stock_id']} {r['stock_name']:8s} | Score={r['score']}/5 | K={r['k']} D={r['d']} 量比={r['vol_ratio']} | 價={r['price']} | {r['reason']}")

    if none_signal:
        print(f"\n[無訊號 Score 0]:")
        for r in none_signal:
            print(f"  {r['stock_id']} {r['stock_name']:8s} | K={r['k']} D={r['d']} 量比={r['vol_ratio']} | {r['reason']}")

    print(f"\n{'='*65}")
    print(f"  操作建議:")
    print(f"{'='*65}")
    if strong:
        print(f"  平倉優先順序:")
        for i, r in enumerate(strong[:5], 1):
            if r['score'] >= 4:
                print(f"  [{i}] {r['stock_id']} {r['stock_name']} @ {r['price']} - 強烈反彈，可平倉")
            else:
                print(f"  [{i}] {r['stock_id']} {r['stock_name']} @ {r['price']} - 訊號浮現，觀察一下")
    else:
        print(f"  目前 KD 普遍偏弱，建議等放量 KD 黃金交叉再平倉")
    print()

if __name__ == "__main__":
    main()
