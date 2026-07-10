import urllib.request
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
url = 'https://www.moneydj.com/KMDJ/News/NewsRealList.aspx?a=CHAT'
req = urllib.request.Request(url, headers={'User-Agent': UA})
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode('utf-8', errors='ignore')

# Find news list area
idx = html.lower().find('class="title"')
if idx < 0:
    idx = html.find('newslist')
if idx < 0:
    idx = html.find('NewsList')
if idx < 0:
    # just show the body
    b = html.find('<body')
    if b >= 0:
        print(html[b:b+3000])
    else:
        print(html[:3000])
else:
    print(html[max(0,idx-500):idx+2000])
