"""分析各資料源HTML結構"""
import re, urllib.request, ssl

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
HEADERS = {'User-Agent': UA}

# SSL bypass for ctee
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch(name, url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)
        text = resp.read().decode('utf-8', errors='ignore')
        return text
    except Exception as e:
        print('ERR %s: %s' % (name, str(e)[:60]))
        return None

# 1. MoneyDJ - 修 pattern
html = fetch('MoneyDJ', 'https://www.moneydj.com/KMDJ/News/NewsRealList.aspx?a=CHAT')
if html:
    # Find <td> with date followed by <a> with href
    pattern = r'<td[^>]*>(\\d{2}/\\d{2}\\s+\\d{2}:\\d{2})</td><td>\\s*<a[^>]*href=\"([^\"]+)\"[^>]*title=\"([^\"]*)\"'
    matches = re.findall(pattern, html, re.DOTALL)
    print('\nMoneyDJ: %d matches' % len(matches))
    for d, h, t in matches[:3]:
        print('  [%s] %s -> %s' % (d.strip(), t.strip()[:40], h[:30]))

# 2. 工商時報
html = fetch('工商時報', 'https://ctee.com.tw/')
if html:
    print('\n工商時報: %d bytes' % len(html))
    # find news titles
    titles = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
    print('  h3 tags: %d' % len(titles))
    for t in titles[:5]:
        clean = re.sub(r'<[^>]+>', '', t).strip()
        if clean:
            print('  %s' % clean[:50])

# 3. 經濟日報
html = fetch('經濟日報', 'https://money.udn.com/money/index')
if html:
    print('\n經濟日報: %d bytes' % len(html))
    # find news titles
    titles = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
    print('  h2 tags: %d' % len(titles))
    for t in titles[:5]:
        clean = re.sub(r'<[^>]+>', '', t).strip()
        if clean:
            print('  %s' % clean[:50])

# 4. 財訊
html = fetch('財訊', 'https://www.wealth.com.tw/')
if html:
    print('\n財訊: %d bytes' % len(html))
    titles = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html, re.DOTALL)
    print('  h2/h3 tags: %d' % len(titles))
    for t in titles[:5]:
        clean = re.sub(r'<[^>]+>', '', t).strip()
        if clean:
            print('  %s' % clean[:50])

# 5. MOPS - try different URL
html = fetch('MOPS', 'https://mops.twse.com.tw/mops/web/ajax_t05st01?encodeURIComponent=1&step=1&firstin=1&off=1&keyword4=&code1=&TYPEK2=&checkbtn=&queryYear=2026&queryMonth=&co_id=2330&TYPEK=&isnew=false')
if html:
    print('\nMOPS: %d bytes' % len(html))
    print(html[:500])
