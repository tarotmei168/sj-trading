"""Replace login_shioaji, download_60d_1min, merge_30min, analyze_stocks in ta_strategy_engine.py"""
fpath = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\ta_strategy_engine.py'

with open(fpath, encoding='utf-8') as f:
    c = f.read()

# Find positions
idx_login = c.find('def login_shioaji()')
idx_talib = c.find('def calc_talib(sid, df30)')

# New functions (proven approach from download_3y_intraday_kd_v2.py)
new_funcs = '''def login_shioaji():
    api_key = os.environ.get("SJ_API_KEY", "")
    sec_key = os.environ.get("SJ_SEC_KEY", "")
    if not api_key or not sec_key:
        print("?? 無 API Key")
        return None
    api = sj.Shioaji(simulation=False)
    try:
        api.login(api_key=api_key, secret_key=sec_key, fetch_contract=True)
        print("?? Shioaji 登入成功")
        return api
    except Exception as e:
        print(f"?? Shioaji 登入失敗: {e}")
        return None


def download_60d_1min(api, sid):
    """Shioaji 60天1分K，大段30天/段 (proven approach)"""
    from datetime import date, time
    end = datetime.now()
    start = end - timedelta(days=60)
    segs = []
    s = start
    while s < end:
        e = min(s + timedelta(days=30), end)
        segs.append((s, e))
        s = e
    try:
        contract = getattr(api.Contracts.Stocks, sid, None)
        if contract is None:
            contract = api.Contracts.Stocks[sid]
    except:
        print(f"  ?? {sid}: 無合約")
        return None
    all_chunks = []
    total = len(segs)
    for idx, (ss, se) in enumerate(segs, 1):
        print(f"    [{idx}/{total}] {ss.date()} ~ {se.date()}", end=" ", flush=True)
        for retry in range(3):
            try:
                kb = api.kbars(contract=contract, start=ss.strftime("%Y-%m-%d"),
                               end=se.strftime("%Y-%m-%d"), timeout=15000)
                if kb is None or len(kb.ts) == 0:
                    print("?? 無資料", end="")
                    break
                df = pd.DataFrame({
                    "datetime": pd.to_datetime(kb.ts),
                    "open": [float(x) for x in kb.Open],
                    "high": [float(x) for x in kb.High],
                    "low": [float(x) for x in kb.Low],
                    "close": [float(x) for x in kb.Close],
                    "volume": [float(x) for x in kb.Volume],
                })
                all_chunks.append(df)
                print(f"? {len(df)}筆", end="")
                break
            except:
                if retry < 2:
                    import time as ttime
                    ttime.sleep(2 * (retry + 1))
                else:
                    print("?? 失敗", end="")
                    break
        print()
    if not all_chunks:
        return None
    result = pd.concat(all_chunks, ignore_index=True)
    result.drop_duplicates(subset=["datetime"], inplace=True)
    result.sort_values("datetime", inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def merge_30min(df):
    """1分K -> 30分K，過濾台股交易時段 09:00~13:30"""
    if df is None or df.empty:
        return None
    d = df.set_index("datetime")
    o = pd.DataFrame({"open": d["open"].resample("30min").first()})
    o["high"] = d["high"].resample("30min").max()
    o["low"] = d["low"].resample("30min").min()
    o["close"] = d["close"].resample("30min").last()
    o["volume"] = d["volume"].resample("30min").sum()
    o = o.dropna().reset_index()
    o["h"] = o["datetime"].dt.hour
    o["m"] = o["datetime"].dt.minute
    o = o[((o["h"] == 9) & (o["m"] >= 0)) |
          ((o["h"] >= 10) & (o["h"] <= 12)) |
          ((o["h"] == 13) & (o["m"] <= 30))]
    o = o.drop(columns=["h", "m"]).reset_index(drop=True)
    if len(o) < 25:
        return None
    return o'''

# Extract the old analyze_stocks function
idx_analyze = c.find('def analyze_stocks(api, stock_ids, strict_mode)')
idx_save_json = c.find('def save_signal_json')

# Build new analyze_stocks
new_analyze = '''def analyze_stocks(api, stock_ids, strict_mode):
    """Shioaji 60天1分K -> 30分K -> TA-Lib (proven approach, 0 cache)"""
    kth = 30 if strict_mode else 35
    results = {}
    print(f"\\n?? 60天30分K + TA-Lib {len(stock_ids)} 檔 (K<{kth} 低檔金叉)")

    for sid in stock_ids:
        name = CORE_NAMES.get(sid, sid)
        print(f"\\n  {sid} {name} 下載 60天1分K...")
        df1 = download_60d_1min(api, sid)
        if df1 is None:
            print("  ?? 無資料")
            continue
        df30 = merge_30min(df1)
        if df30 is None:
            print("  ?? 30分K合併失敗")
            continue
        print(f"  -> {len(df30)}根30分K | last={str(df30.iloc[-1][\"datetime\"])[:19]} close={df30.iloc[-1][\"close\"]}")
        
        t = calc_talib(sid, df30)
        if t:
            t["name"] = name
            results[sid] = t
            print(f"     K:{t['k']:.1f}/D:{t['d']:.1f} RSI:{t['rsi']} MACD_hist:{t.get('macd_hist',0):.1f} | {t['strategy']}")
    return results'''

# Perform replacement
c = c[:idx_login] + new_funcs + "\n\n" + c[idx_talib:]

# Now find and replace analyze_stocks
idx_analyze2 = c.find('def analyze_stocks(api, stock_ids, strict_mode)')
idx_save2 = c.find('def save_signal_json')
# Remove old analyze_stocks
old_analyze = c[idx_analyze2:idx_save2]
c = c.replace(old_analyze, new_analyze + "\n\n", 1)

# Also update the header text about data source
c = c.replace(
    '資料: Shioaji 60天1分K -> 30分K',
    '資料: Shioaji 60天1分K -> 30分K (proven)'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)

import ast
ast.parse(c)
print('OK')
