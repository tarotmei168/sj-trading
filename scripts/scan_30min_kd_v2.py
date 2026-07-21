"""
30分K KD價量黃金交叉 - 用 Shioaji 抓30天分鐘K
"""
import sys, os, pandas as pd, numpy as np
sys.path.insert(0, r"C:\Users\User\.openclaw\workspace\sj-trading")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv(r"C:\Users\User\.openclaw\workspace\sj-trading\.env")

import shioaji as sj
from shioaji.constant import TSE

TZ = timezone(timedelta(hours=8))
CORE = {
    "2330":"台積電","2317":"鴻海","2454":"聯發科","3711":"日月光投控",
    "4958":"臻鼎-KY","3042":"晶技","2436":"偉詮電","2337":"旺宏",
    "5351":"鈺創","3673":"TPK-KY","8150":"南茂"
}

# 登入 Shioaji
api_key = os.environ.get("SJ_API_KEY")
sec_key = os.environ.get("SJ_SEC_KEY")
api = sj.Shioaji(simulation=False)
try:
    accounts = api.login(api_key, sec_key)
    print(f"登入成功: {api_key[:4]}...{api_key[-4:]}")
except Exception as e:
    print(f"登入失敗: {e}")
    sys.exit(1)

def calc_kd(df, n=9):
    low_n = df['Low'].rolling(n).min()
    high_n = df['High'].rolling(n).max()
    rsv = ((df['Close'] - low_n) / (high_n - low_n)) * 100
    rsv = rsv.fillna(50).clip(0,100)
    k, d = 50.0, 50.0
    ks, ds = [], []
    for r in rsv:
        k = (2/3)*k + (1/3)*r
        d = (2/3)*d + (1/3)*k
        ks.append(k); ds.append(d)
    return pd.Series(ks, index=df.index), pd.Series(ds, index=df.index)

end = datetime.now()
start = end - timedelta(days=30)
results = []

for sid, sname in CORE.items():
    print(f"\n  {sid} {sname} ... ", end="", flush=True)
    try:
        contract = api.Contracts.Stocks[sid]
        if not contract:
            print("找不到合約", end="", flush=True); continue
        kbars = api.kbars(contract, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if len(kbars) < 30:
            print(f"資料不足({len(kbars)})", end="", flush=True); continue
        
        df = pd.DataFrame({k: kbars[k] for k in ['ts','Open','High','Low','Close','Volume']})
        df['ts'] = pd.to_datetime(df['ts'])
        df = df.set_index('ts').sort_index()
        
        # 30分重採樣
        ohlc = df.resample('30min', closed='right', label='right').agg({
            'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'
        }).dropna()
        
        if len(ohlc) < 20:
            print(f"30分K不足({len(ohlc)})", end="", flush=True); continue
        
        k, d = calc_kd(ohlc)
        ma20 = ohlc['Close'].rolling(20).mean()
        vol_ma5 = ohlc['Volume'].rolling(5).mean()
        
        last = ohlc.iloc[-1]
        lk, ld = k.iloc[-1], d.iloc[-1]
        pk, pd_ = k.iloc[-2], d.iloc[-2]
        lma = ma20.iloc[-1]
        lvm = vol_ma5.iloc[-1]
        
        score = 0; reasons = []
        
        # KD黃金交叉
        if pk <= pd_ and lk > ld:
            score += 1; reasons.append(f"K上穿D({lk:.1f}>{ld:.1f})")
        elif lk > ld:
            score += 1; reasons.append(f"K>D({lk:.1f}>{ld:.1f})")
        else:
            reasons.append(f"K<D({lk:.1f}<{ld:.1f})")
        
        # 低檔
        if lk < 40:
            score += 1; reasons.append(f"低檔K={lk:.1f}")
        
        # 價量
        vr = last['Volume'] / lvm if lvm > 0 else 0
        if vr >= 1.5:
            score += 1; reasons.append(f"量{int(last['Volume'])}>均量x{vr:.1f}")
        elif vr >= 1.2:
            reasons.append(f"量微增{vr:.1f}x")
        else:
            reasons.append(f"量縮{vr:.1f}x")
        
        # 站上20MA
        if not pd.isna(lma) and last['Close'] > lma:
            score += 1; reasons.append(f">20MA({lma:.1f})")
        else:
            ma = f"{lma:.1f}" if not pd.isna(lma) else "N/A"
            reasons.append(f"<20MA({ma})")
        
        # 連3漲
        if len(ohlc) >= 4:
            if all(ohlc['Close'].iloc[-i] > ohlc['Close'].iloc[-i-1] for i in [1,2]):
                score += 1; reasons.append("連3漲")
        
        results.append({
            "id": sid, "name": sname, "time": ohlc.index[-1].strftime("%m/%d %H:%M"),
            "price": round(last['Close'], 2), "k": round(lk, 1), "d": round(ld, 1),
            "vol": int(last['Volume']), "vol_ratio": round(vr, 1),
            "ma20": round(lma, 1) if not pd.isna(lma) else 0,
            "score": score, "reason": ", ".join(reasons)
        })
        print(f"Score={score}/5", end="", flush=True)
    except Exception as e:
        print(f"錯誤:{e}", end="", flush=True)

api.logout()
print("\n\n" + "=" * 60)
print("  【核心持股 30分K KD價量黃金交叉】")
print(f"  掃描時間: {datetime.now(TZ).strftime('%H:%M')}")
print("=" * 60)

results.sort(key=lambda x: x['score'], reverse=True)
strong = [r for r in results if r['score'] >= 3]
normal = [r for r in results if 1 <= r['score'] <= 2]
weak = [r for r in results if r['score'] == 0]

if strong:
    print(f"\n  🔥 強烈訊號 (Score 3-5) — 可考慮平倉:")
    print(f"  {'代號':<6} {'名稱':<10} {'價':<8} {'K/D':<10} {'量比':<6} {'分數':<6} 條件")
    print("  " + "-" * 80)
    for r in strong:
        print(f"  {r['id']:<6} {r['name']:<10} {r['price']:<8} {r['k']}/{r['d']:<8} {r['vol_ratio']:<6} {r['score']}/5  {r['reason']}")
else:
    print(f"\n  ❌ 目前無 Score >= 3 的強烈訊號")

if normal:
    print(f"\n  📌 一般訊號 (Score 1-2):")
    for r in normal:
        print(f"    {r['id']} {r['name']:8s} | K={r['k']} D={r['d']} 量比={r['vol_ratio']} | {r['reason']}")

if weak:
    print(f"\n  ⚪ 無訊號 (Score 0):")
    for r in weak:
        print(f"    {r['id']} {r['name']:8s} | K={r['k']} D={r['d']} 量比={r['vol_ratio']} | {r['reason']}")

# 更新記憶
note = f"\n# 30分K KD掃描 ({datetime.now(TZ).strftime('%m/%d %H:%M')})"
note += f"\n# 核心持股30分KD價量黃金交叉掃描結果"
for r in results:
    note += f"\n#   {r['id']} {r['name']}: Score={r['score']}/5 K={r['k']} D={r['d']} 價={r['price']} 量比={r['vol_ratio']} {r['reason']}"
with open(os.path.join(os.path.dirname(__file__), "..", "scan_30m_kd_result.md"), "w", encoding="utf-8") as f:
    f.write(note)

print(f"\n  📝 結果已寫入 scan_30m_kd_result.md")
print()
