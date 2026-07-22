import requests
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

# Try various TWSE endpoints for 投信 data
tests = {
    "T85": f"https://www.twse.com.tw/fund/T85?response=json&date={yesterday}",
    "T86": f"https://www.twse.com.tw/fund/T86?response=json&date={yesterday}",
    "T44": f"https://www.twse.com.tw/fund/T44?response=json&date={yesterday}",
}

for name, url in tests.items():
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        d = r.json()
        print(f"{name}: stat={d.get('stat')} rows={len(d.get('data',[]))} title={d.get('title','')}")
        if d.get("data") and len(d["data"]) > 0:
            print(f"  First: {d['data'][0]}")
    except Exception as e:
        print(f"{name}: Error {e}")
