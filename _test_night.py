"""測試各夜盤資料源"""
import json, urllib.request, ssl

UA = 'Mozilla/5.0'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def try_url(name, url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        raw = resp.read().decode('utf-8')
        d = json.loads(raw)
        print('OK [%s] %s' % (name, url))
        print(json.dumps(d, ensure_ascii=False, indent=2)[:600])
        print()
        return d
    except Exception as e:
        print('ERR [%s] %s - %s' % (name, url, str(e)[:60]))
        return None

# 台指期 (大台)
try_url('台指期', 'https://news.cnyes.com/api/v3/quote/stock/quote?symbol=TWF:TX00')

# 台指期夜盤 (可能不同代碼)
try_url('台指期夜盤-1', 'https://news.cnyes.com/api/v3/quote/stock/quote?symbol=TWF:TXN')
try_url('台指期夜盤-2', 'https://news.cnyes.com/api/v3/quote/futures/quote?symbol=TWF:TX00')
try_url('台指期夜盤-3', 'https://news.cnyes.com/api/v3/quote/futures/quote?symbol=TWF:TXN')

# 費半SOX夜盤 (美股正在進行)
try_url('費半SOX', 'https://news.cnyes.com/api/v3/quote/stock/quote?symbol=US:SOX')

# NVDA夜盤
try_url('NVDA', 'https://news.cnyes.com/api/v3/quote/stock/quote?symbol=US:NVDA')

# 標普500夜盤
try_url('SPY', 'https://news.cnyes.com/api/v3/quote/stock/quote?symbol=US:SPY')
