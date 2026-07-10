import re, urllib.request

UA = 'Mozilla/5.0'
url = 'https://www.moneydj.com/KMDJ/News/NewsRealList.aspx?a=CHAT'
req = urllib.request.Request(url, headers={'User-Agent': UA})
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')

# show the raw text around tr/td tags
idx = html.find('<tr')
while idx >= 0:
    chunk = html[idx:idx+400]
    if 'href' in chunk and '/kmdj/news/newsviewer' in chunk:
        print(chunk[:400])
        print('---')
    idx = html.find('<tr', idx+1)
    if idx > 50000:
        break
