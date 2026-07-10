# -*- coding: utf-8 -*-
import subprocess, os, re

os.chdir(r'C:\Users\User\.openclaw\workspace\sj-trading')

with open('.env', encoding='utf-8') as f:
    env = f.read()
m = re.search(r'GITHUB_TOKEN=(.+)', env)
token = m.group(1).strip() if m else ''

git = r'D:\StableDiffusion\Git\bin\git.exe'

# 把 remote URL 改成含 token 的格式（git 支援）
# https://username:token@github.com/user/repo.git
remote_url = f'https://tarotmei168:{token}@github.com/tarotmei168/sj-trading.git'
subprocess.run([git, 'remote', 'set-url', 'origin', remote_url], capture_output=True)

# 先 pull 再 push（避免 reject）
subprocess.run([git, 'pull', 'origin', 'main', '--allow-unrelated-histories', '-X', 'theirs'],
    capture_output=True, timeout=30)

# add + commit + push
subprocess.run([git, 'add', '-A'], capture_output=True, timeout=30)
subprocess.run([git, 'commit', '-m', 'update all 2026-07-10'], capture_output=True, timeout=30)

result = subprocess.run([git, 'push', 'origin', 'main'], capture_output=True, text=True, timeout=60)
print(f'RC: {result.returncode}')
print('out:', result.stdout[-400:])
print('err:', result.stderr[-400:])
