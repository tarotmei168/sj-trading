"""资料源深度调查 — 找即时买卖超/法人/大户"""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
H = {'User-Agent': 'Mozilla/5.0'}

# ===== 1. 证交所即时行情 =====
url1 = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw&json=1&delay=0'
try:
    req = urllib.request.Request(url1, headers=H)
    raw = urllib.request.urlopen(req, timeout=10).read()
    d = json.loads(raw)
    msg = d['msgArray'][0]
    print('=== 1. 证交所即时行情 (盘中可用) ===')
    print(f'  股价: {msg["z"]}  昨收: {msg["y"]}')
    print(f'  开:{msg["o"]} 高:{msg["h"]} 低:{msg["l"]} 量:{msg["v"]}')
    print(f'  买1~5价位: {msg["b"]}')
    print(f'  卖1~5价位: {msg["a"]}')
    print(f'  买量1~5: {msg["g"]}')
    print(f'  卖量1~5: {msg["f"]}')
    print(f'  时间: {msg["t"]}')
except Exception as e:
    print(f'[❌] 证交所: {e}')

# ===== 2. 钜亨看有没有新的 ticks API =====
print('\n=== 2. 钜亨 API 探索 ===')
for ver in ['v2', 'v3']:
    for path in ['/ticks/api/' + ver + '/tickers/2330', '/api/' + ver + '/ticks/2330']:
        url = 'https://ws.api.cnyes.com' + path
        try:
            req = urllib.request.Request(url, headers=H)
            raw = urllib.request.urlopen(req, timeout=8).read()
            d = json.loads(raw)
            print(f'  [✅] {path}: {str(d)[:200]}')
        except:
            pass

# 试试不同的 query param
for q in ['type=tick', 'type=day', 'type=quote', 'range=1d', 'period=1m']:
    url = f'https://ws.api.cnyes.com/ticks/api/v1/tickers/2330/ticks?{q}'
    try:
        req = urllib.request.Request(url, headers=H)
        raw = urllib.request.urlopen(req, timeout=8).read()
        d = json.loads(raw)
        print(f'  [✅] ticks?{q}: {str(d)[:200]}')
    except urllib.error.HTTPError:
        pass
    except Exception as e:
        print(f'  [❌] ticks?{q}: {type(e).__name__}')

# ===== 3. 群益API / 其他证券商 =====
print('\n=== 3. 其他 API ===')
# 元大 API
for url in [
    'https://yestock.yuanta.com.tw/api/stock/2330/quote',
    'https://www.wantgoo.com/api/stock/2330',
    'https://www.cmoney.tw/api/stock/2330',
]:
    try:
        req = urllib.request.Request(url, headers=H)
        raw = urllib.request.urlopen(req, timeout=8).read()
        d = json.loads(raw)
        print(f'  [✅] {url[:50]}... : {str(d)[:200]}')
    except urllib.error.HTTPError:
        print(f'  [404] {url[:50]}...')
    except Exception as e:
        pass

# ===== 4. Goodinfo 免SSL =====
print('\n=== 4. Goodinfo (不驗證SSL) ===')
import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
url_gi = 'https://goodinfo.tw/StockInfo/StockDetail.asp?STOCK_ID=2330'
try:
    req = urllib.request.Request(url_gi, headers=H)
    raw = urllib.request.urlopen(req, context=ctx, timeout=10).read()
    html = raw.decode('utf-8', errors='replace')
    print(f'  抓到 {len(html)} chars')
    # 找法人買賣超表格
    for keyword in ['外資', '投信', '自營', '法人', '買賣超', '買超', '賣超']:
        idx = html.find(keyword)
        if idx >= 0:
            print(f'  找到關鍵字「{keyword}」在位置 {idx}')
            print(f'  附近: {html[max(0,idx-50):idx+100]}')
            print()
except Exception as e:
    print(f'  [❌] Goodinfo: {type(e).__name__}: {str(e)[:100]}')

print('\n=== 調查完成 ===')
