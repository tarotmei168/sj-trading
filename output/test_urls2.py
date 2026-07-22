import requests
from bs4 import BeautifulSoup

urls = [
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_A_0_0.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_1_0.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_2_0.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_4_0.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_3_0.djhtm',
    'https://www.twse.com.tw/fund/T86?response=json',
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for url in urls:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if 'twse' in url:
            d = r.json()
            stat = d.get("stat", "?")
            rows = len(d.get("data", []))
            print(f'{url} -> {stat} ({rows} rows)')
        else:
            r.encoding = 'big5'
            s = BeautifulSoup(r.text, 'html.parser')
            t = s.find('title')
            title = t.get_text(strip=True) if t else "?"
            print(f'{url} -> {title} ({len(r.text)} bytes)')
    except Exception as e:
        print(f'{url} -> Error: {e}')
