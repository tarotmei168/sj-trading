"""直接 str.find 逐一抓"""
import urllib.request

UA = 'Mozilla/5.0'
url = 'https://www.moneydj.com/KMDJ/News/NewsRealList.aspx?a=CHAT'
req = urllib.request.Request(url, headers={'User-Agent': UA})
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')

items = []
pos = 0
while True:
    # Find "color:Gray;width:100px;"
    idx = html.find('color:Gray;width:100px;', pos)
    if idx < 0:
        break
    # Move past the closing >
    end_style = html.find('>', idx)
    if end_style < 0:
        break
    rest = html[end_style+1:]
    
    # Extract date (trim whitespace)
    date = rest.strip().split('<')[0].strip()
    if not date or not date[0].isdigit():
        pos = end_style + 1
        continue
    
    # Find the <a href
    a_start = rest.find('<a href=')
    if a_start < 0:
        break
    a_rest = rest[a_start:]
    # href
    h_start = a_rest.find('"')
    h_end = a_rest.find('"', h_start+1)
    href = a_rest[h_start+1:h_end] if h_start >= 0 and h_end > h_start else ''
    # title
    t_start = a_rest.find('title="')
    if t_start >= 0:
        t_end = a_rest.find('"', t_start+7)
        title = a_rest[t_start+7:t_end] if t_end > t_start else ''
    else:
        title = ''
    
    items.append((date.strip(), title.strip(), href.strip()))
    pos = idx + 1

print('Items: %d' % len(items))
for d, t, h in items[:5]:
    print('  [%s] %s' % (d, t[:50]))
