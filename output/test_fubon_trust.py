import requests
from bs4 import BeautifulSoup

# Try to find the 投信 ranking URL
url = 'https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F.djhtm'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

r = requests.get(url, headers=headers, timeout=10)
r.encoding = 'big5'
soup = BeautifulSoup(r.text, 'html.parser')

# Find all links that might point to 投信 pages
for a in soup.find_all('a'):
    href = a.get('href', '')
    text = a.get_text(strip=True)
    if '投信' in text or '投信' in href:
        print(f'Found 投信 link: href={href} text={text}')
    elif 'zg_F' in href and '0_' in href:
        print(f'Found zg_F_0 link: href={href} text={text}')
