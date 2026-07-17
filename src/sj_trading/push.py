#!/usr/bin/env python3
"""Push to GitHub with token from .env"""
import os, subprocess
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))
token = os.environ.get('GITHUB_TOKEN', '') or os.environ.get('GH_TOKEN', '')
repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
git = r'D:\StableDiffusion\Git\bin\git.exe'
url = 'https://tarotmei168:' + token + '@github.com/tarotmei168/sj-trading.git'
subprocess.run([git, '-C', repo_dir, 'remote', 'set-url', 'origin', url], capture_output=True)
r = subprocess.run([git, '-C', repo_dir, 'push', 'origin', 'main'], capture_output=True, text=True, timeout=60)
print('STDOUT:', r.stdout[-300:])
print('STDERR:', r.stderr[-300:])
print('RC:', r.returncode)
