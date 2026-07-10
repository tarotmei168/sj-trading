import requests, base64, os

# 從 .env 讀 token
import re
with open(os.path.join(os.path.dirname(__file__), '..', '.env'), 'r', encoding='utf-8') as f:
    env = f.read()
m = re.search(r'GITHUB_TOKEN=(\S+)', env)
TOKEN = m.group(1) if m else input("貼上你的 GitHub Token: ")

REPO = 'tarotmei168/sj-trading'
BRANCH = 'main'
headers = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/vnd.github+json'}

fp = os.path.join(os.path.dirname(__file__), 'index.html')
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# GET sha
url = f'https://api.github.com/repos/{REPO}/contents/index.html?ref={BRANCH}'
r = requests.get(url, headers=headers)
if r.status_code == 200:
    sha = r.json()['sha']
    print(f'SHA: {sha[:12]}...')
else:
    print(f'GET failed: {r.status_code}')
    sha = None

# PUT
b64 = base64.b64encode(content.encode()).decode('ascii')
payload = {'message': 'remove 6 stocks from core holdings', 'content': b64, 'branch': BRANCH}
if sha:
    payload['sha'] = sha

r2 = requests.put(url, json=payload, headers=headers)
print(f'Status: {r2.status_code}')
if r2.status_code in (200, 201):
    print('OK! https://tarotmei168.github.io/sj-trading/')
else:
    print(r2.text[:300])
