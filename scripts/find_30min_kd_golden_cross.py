"""
30分K 價量黃金交叉掃描 — 核心持股專用
篩選標準 (因為台股在季線，要精準抓買點來平倉):
1. K值 > D值 (KD黃金交叉)
2. K值 < 40 (低檔黃金交叉，反彈訊號)
3. 成交量 > 前5根均量 * 1.5 (價量配合)
4. 目前股價 > 20MA (短線偏多)
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta, timezone

# Windows CP950 相容
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

# 核心持股
CORE_STOCKS = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科",
    "3711": "日月光投控", "4958": "臻鼎-KY", "3042": "晶技",
    "2436": "偉詮電", "2337": "旺宏", "5351": "鈺創",
    "3673": "TPK-KY", "8150": "南茂"
}

DB_DIR = r"C:\Users\User\.openclaw\workspace\sj-trading\database"
TZ = timezone(timedelta(hours=8))

def calc_kd(high, low, close, n=9):
    """計算 KD 值"""
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = ((close - low_n) / (high_n - low_n)) * 100
    rsv = rsv.fillna(50)
    k = pd.Series(np.zeros(len(rsv)), index=rsv.index)
    d = pd.Series(np.zeros(len(rsv)), index=rsv.index)
    k.iloc[0] = 50
    d.iloc[0] = 50
    for i in range(1, len(rsv)):
        k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
        d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
    return k, d

def calc_ma(close, period):
    return close.rolling(period).mean()

def calc_volume_ma(volume, period):
    return volume.rolling(period).mean()

def load_stock_data(stock_id):
    """從 3y CSV 載入資料並重採樣為 30分K"""
    filepath = os.path.join(DB_DIR, f"{stock_id}_3y.csv")
    if not os.path.exists(filepath):
        print(f"  ⚠️  {stock_id} 無資料")
        return None
    
    df = pd.read_csv(filepath)
    if 'date' not in df.columns:
        print(f"  ⚠️  {stock_id} 格式不符")
        return None
    
    # 確保有時間欄位
    df['datetime'] = pd.to_datetime(df['date'])
    
    # 排序
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # 過濾最近 14 天
    cutoff = pd.Timestamp.now(tz=TZ) - timedelta(days=14)
    df = df[df['datetime'].dt.tz_localize(TZ, ambiguous='infer') >= cutoff].copy()
    
    if len(df) < 50:
        print(f"  ⚠️  {stock_id} 資料不足 ({len(df)} 筆)")
        return None
    
    # 重採樣為 30分K
    df = df.set_index('datetime')
    
    ohlc = df.resample('30min', closed='right', label='right').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    
    return ohlc

def check_golden_cross(df, stock_id, stock_name):
    """檢查最後一根 30分K 是否出現 KD 價量黃金交叉"""
    if df is None or len(df) < 20:
        return None
    
    k, d = calc_kd(df['High'], df['Low'], df['Close'])
    ma20 = calc_ma(df['Close'], 20)
    vol_ma5 = calc_volume_ma(df['Volume'], 5)
    
    # 只看最後一根
    last = df.iloc[-1]
    last_k = k.iloc[-1]
    last_d = d.iloc[-1]
    last_ma20 = ma20.iloc[-1]
    last_vol_ma5 = vol_ma5.iloc[-1]
    
    # 前一根的 K/D 值 (確認交叉)
    prev_k = k.iloc[-2] if len(k) >= 2 else None
    prev_d = d.iloc[-2] if len(d) >= 2 else None
    
    # 檢查條件
    conditions = {
        "KD黃金交叉": False,
        "低檔(<40)": False,
        "價量配合": False,
        "站上20MA": False,
        "趨勢偏多": False
    }
    
    reasons = []
    
    # 條件1: KD 黃金交叉 (K 上穿 D，或 K>D 且前一根 K<=D)
    if prev_k is not None and prev_d is not None:
        if prev_k <= prev_d and last_k > last_d:
            conditions["KD黃金交叉"] = True
            reasons.append(f"K({last_k:.1f})剛上穿D({last_d:.1f})")
        elif last_k > last_d:
            conditions["KD黃金交叉"] = True
            reasons.append(f"K({last_k:.1f})>D({last_d:.1f})維持黃金交叉")
    
    # 條件2: 低檔 (< 40)
    if last_k < 40:
        conditions["低檔(<40)"] = True
        reasons.append(f"低檔K={last_k:.1f}")
    elif last_k < 50:
        reasons.append(f"中檔K={last_k:.1f}")
    
    # 條件3: 價量配合
    if last['Volume'] > last_vol_ma5 * 1.5:
        conditions["價量配合"] = True
        reasons.append(f"量{int(last['Volume'])}>均量{int(last_vol_ma5)}x1.5")
    
    # 條件4: 站上20MA
    if last['Close'] > last_ma20:
        conditions["站上20MA"] = True
        reasons.append(f"價{last['Close']:.1f}>20MA{last_ma20:.1f}")
    else:
        reasons.append(f"價{last['Close']:.1f}<20MA{last_ma20:.1f}")
    
    # 條件5: 趨勢偏多 (最後3根收盤 > 前一根)
    if len(df) >= 4:
        if df['Close'].iloc[-1] > df['Close'].iloc[-2] and \
           df['Close'].iloc[-2] > df['Close'].iloc[-3]:
            conditions["趨勢偏多"] = True
            reasons.append("連3根上漲")
    
    score = sum(1 for v in conditions.values() if v)
    
    timestamp = df.index[-1]
    
    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "time": timestamp.strftime("%Y-%m-%d %H:%M"),
        "price": round(last['Close'], 2),
        "k": round(last_k, 1),
        "d": round(last_d, 1),
        "volume": int(last['Volume']),
        "vol_ma5": int(last_vol_ma5),
        "ma20": round(last_ma20, 1),
        "conditions": conditions,
        "score": score,
        "reason": ", ".join(reasons)
    }

def main():
    print("=" * 65)
    print(f"  🦞 核心持股 30分K KD價量黃金交叉掃描")
    print(f"  時間: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')} (台股時間)")
    print("=" * 65)
    print(f"\n📋 掃描標準:")
    print(f"  1. KD 黃金交叉 (K上穿D)")
    print(f"  2. 低檔 (< 40 更佳)")
    print(f"  3. 成交量 > 5均量 x 1.5")
    print(f"  4. 站上 20MA")
    print(f"  5. 趨勢偏多 (連3根漲)")
    print(f"  ⚡ 滿足4-5條件為強烈訊號，適合平倉\n")
    
    results = []
    
    for sid, sname in CORE_STOCKS.items():
        print(f"  🔍 {sid} {sname} ... ", end="", flush=True)
        df = load_stock_data(sid)
        result = check_golden_cross(df, sid, sname)
        if result:
            results.append(result)
            print(f"✅ Score={result['score']}/5")
        else:
            print(f"⏹️  無訊號")
    
    # 排序: 分數高的在前面
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "=" * 65)
    print(f"  📊 篩選結果 (Score 3+):")
    print("=" * 65)
    
    strong_signals = [r for r in results if r['score'] >= 3]
    weak_signals = [r for r in results if 1 <= r['score'] <= 2]
    
    if strong_signals:
        print(f"\n🔥 強烈訊號 (Score 3-5):")
        print(f"{'代號':<8} {'名稱':<10} {'時間':<16} {'價':<8} {'K':<6} {'D':<6} {'量':<10} {'分數':<6} 條件")
        print("-" * 120)
        for r in strong_signals:
            print(f"{r['stock_id']:<8} {r['stock_name']:<10} {r['time']:<16} {r['price']:<8} {r['k']:<6} {r['d']:<6} {r['volume']:<10} {r['score']}/5  {r['reason']}")
    
    if weak_signals:
        print(f"\n📌 一般訊號 (Score 1-2):")
        for r in weak_signals:
            print(f"  {r['stock_id']} {r['stock_name']:8s} | 價={r['price']} K={r['k']} D={r['d']} | {r['reason']}")
    
    if not strong_signals and not weak_signals:
        print(f"\n  ❌ 目前核心持股均無 30分K 價量黃金交叉訊號")
    
    # 換句話說平倉建議
    print("\n" + "=" * 65)
    print(f"  💡 操作建議 (平倉參考):")
    print("=" * 65)
    if strong_signals:
        print(f"  🎯 以下出現價量黃金交叉，反彈力道充足，可考慮平倉:")
        for r in strong_signals[:5]:
            direction = "🟢 強烈平倉" if r['score'] >= 4 else "🟡 可考慮平倉"
            print(f"    {direction}: {r['stock_id']} {r['stock_name']} @ {r['price']}")
    else:
        check_k_up = [r for r in results if r['k'] > r['d']]
        if check_k_up:
            print(f"  ⏳ 以下KD已轉多但價量不足，等放量再平倉:")
            for r in check_k_up[:3]:
                print(f"    {r['stock_id']} {r['stock_name']} K={r['k']}>D={r['d']} 量需≥{r['vol_ma5']*1.5:.0f}")
        else:
            print(f"  ⏳ 目前無明確反彈訊號，建議等待 KD 黃金交叉確認")
    
    print()

if __name__ == "__main__":
    main()
