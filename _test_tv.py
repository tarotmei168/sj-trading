"""測試 TradingView API - 試不同端點"""
import json, urllib.request, ssl

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 1. UDF (統一數據格式) - TradingView 給第三方使用的公開 API
# https://github.com/tradingview/charting_library/wiki/UDF
urls = [
    # Symbol info
    ('台指期 info', 'https://scanner.tradingview.com/tw/scan?symbol=TAIFEX:TX%21'),
    ('台指期 search', 'https://symbol-search.tradingview.com/symbol_search/?text=TX&exchange=TAIFEX'),
    ('TV quote', 'https://quotes.tradingview.com/v1/symbol?symbol=TAIFEX%3ATX%21'),
]

for name, url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        raw = resp.read().decode('utf-8')
        try:
            d = json.loads(raw)
            print('OK [%s]: %s' % (name, json.dumps(d, ensure_ascii=False)[:500]))
        except:
            print('RAW [%s]: %s...' % (name, raw[:200]))
    except Exception as e:
        print('ERR [%s]: %s' % (name, str(e)[:50]))
