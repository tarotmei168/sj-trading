import requests
urls = [
    'https://www.twse.com.tw/fund/T85?response=json',
    'https://www.twse.com.tw/fund/T86?response=json',
    'https://www.twse.com.tw/fund/BFI82U?response=json',
    'https://www.twse.com.tw/en/fund/BFI82U?response=json&dayDate=20260722',
]
for u in urls:
    try:
        r = requests.get(u, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        d = r.json()
        name = u.split('/')[-1].split('?')[0]
        print(f'{name}: stat={d.get("stat","?")} rows={len(d.get("data",[]))}')
    except Exception as e:
        name = u.split('/')[-1].split('?')[0]
        print(f'{name}: Error {e}')
