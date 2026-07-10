#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新 WeChat ID 到 web/wechat_info.html"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, 'web')

HTML = """<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WeChat Info</title>
<style>
body{font-family:sans-serif;background:#1a1a2e;color:#eee;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;}
.card{background:#16213e;padding:24px;border-radius:12px;max-width:400px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.4);}
h2{color:#f0c27a;margin:0 0 8px;}
p{color:#8899aa;font-size:13px;margin:4px 0;}
.code{font-size:18px;color:#4ade80;font-weight:bold;background:#0f3460;padding:8px 16px;border-radius:8px;display:inline-block;margin:12px 0;}
.footer{font-size:11px;color:#556;margin-top:16px;}
</style></head><body>
<div class="card">
<h2>🐉 小龍蝦 WeChat</h2>
<p>對話 ID</p>
<div class="code">o9cq804gqpOKaKXjPv4i7LTMeOGo</div>
<p>訊息 ID</p>
<div class="code">openclaw-weixin:1783563175498-ef7f6697</div>
<p>時間戳</p>
<div class="code">2026-07-09 10:12 GMT+8</div>
<div class="footer">🦞 小龍蝦台股系統 · 自動記錄</div>
</div></body></html>
"""

os.makedirs(WEB, exist_ok=True)
with open(os.path.join(WEB, 'wechat_info.html'), 'w', encoding='utf-8') as f:
    f.write(HTML)
print('[OK] wechat_info.html updated')

# git push
import subprocess
git_dir = WEB if os.path.exists(os.path.join(WEB, '.git')) else BASE
subprocess.run(['git', 'add', '.'], cwd=git_dir, capture_output=True, timeout=15)
subprocess.run(['git', 'commit', '-m', '📝 更新 WeChat info 記錄'], cwd=git_dir, capture_output=True, timeout=15)
subprocess.run(['git', 'push'], cwd=git_dir, capture_output=True, timeout=60)
print('[OK] Git Push 完成')
print('🔗 https://tarotmei168.github.io/sj-trading/wechat_info.html')
