# -*- coding: utf-8 -*-
"""
上傳 index.html & architecture.html 到 GitHub
用法: python _upload_to_github.py
"""

import os, sys, json, base64, requests

REPO = "tarotmei168/sj-trading"
BRANCH = "main"

# 讀取本地檔案
BASE = os.path.dirname(os.path.abspath(__file__))
files_to_upload = {
    "index.html": os.path.join(BASE, "web", "index.html"),
    "architecture.html": os.path.join(BASE, "web", "architecture.html"),
}

# 請輸入你的 GitHub Token
# 到 https://github.com/settings/tokens 建立一個 classic token
# 權限勾 repo 即可
print("=" * 60)
print("🦞 GitHub 上傳工具")
print("=" * 60)
print()
print("你需要一個 GitHub Personal Access Token (classic)")
print("建立位置: https://github.com/settings/tokens")
print("權限: 勾 repo 即可")
print()

TOKEN = input("請貼上你的 GitHub Token: ").strip()
if not TOKEN:
    print("❌ 需要 Token")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

for filename, local_path in files_to_upload.items():
    if not os.path.exists(local_path):
        print(f"⚠️ 找不到 {local_path}，跳過")
        continue
    
    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 檢查檔案是否存在，取得 sha
    check_url = f"https://api.github.com/repos/{REPO}/contents/{filename}?ref={BRANCH}"
    r = requests.get(check_url, headers=headers)
    
    sha = None
    if r.status_code == 200:
        sha = r.json().get("sha")
        print(f"📄 {filename}: 找到舊檔，將取代 (SHA: {sha[:8]}...)")
    elif r.status_code == 404:
        print(f"📄 {filename}: 新檔案，將建立")
    else:
        print(f"⚠️ 檢查 {filename} 失敗: {r.status_code} {r.text[:100]}")
        continue
    
    # 上傳
    upload_url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    payload = {
        "message": f"🦞 更新 {filename} - 完整40組台美連動+台灣50除權息+美國總經+Fed日曆",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    
    r2 = requests.put(upload_url, json=payload, headers=headers)
    if r2.status_code in (200, 201):
        print(f"✅ {filename} 上傳成功!")
    else:
        print(f"❌ {filename} 上傳失敗: {r2.status_code} {r2.text[:200]}")

print()
print("完成! 等待 1-2 分鐘後開啟:")
print("https://tarotmei168.github.io/sj-trading/")
input("\n按 Enter 結束...")
