import requests
for dt in ['20260706','20260707','20260708']:
    r = requests.get('https://www.twse.com.tw/rwd/zh/fund/T38', 
                     params={'date':dt,'selectType':'ALL','response':'json'},
                     headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
    print(f'{dt}: status={r.status_code}, len={len(r.text)}')
    print(r.text[:200])
    print()
