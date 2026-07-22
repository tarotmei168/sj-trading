# Test Fubon URLs
import requests
from bs4 import BeautifulSoup

urls = [
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_1.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_0.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_3.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_4.djhtm',
    'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_5.djhtm',
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for url in urls:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'big5'
        s = BeautifulSoup(r.text, 'html.parser')
        t = s.find('title')
        title = t.get_text(strip=True) if t else "No title"
        print(f'{url} -> {title} ({len(r.text)} bytes)')
    except Exception as e:
        print(f'{url} -> Error: {e}')
