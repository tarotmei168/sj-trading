#!/usr/bin/env python3
"""
🦞 intraday_git_pusher.py — 盤中自動 Git Push 引擎
====================================================
功能: 被其他模組呼叫，將 web/ 底下的最新 HTML
      透過 Git 自動 add → commit → push

使用方式:
    from intraday_git_pusher import quick_push
    quick_push("💡 黃K金叉觸發 聯發科")

也支援獨立執行:
    python intraday_git_pusher.py "📊 盤中更新"
"""

import os, sys, subprocess
from datetime import datetime

# ─── 路徑 ─────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
WEB_DIR = os.path.join(BASE_DIR, 'web')


def quick_push(message: str = None) -> bool:
    """
    快速推送 web/ 目錄變更到 GitHub
    回傳 True=成功, False=失敗
    """
    if not message:
        message = f"🦞 盤中即時更新 {datetime.now().strftime('%H:%M')}"

    try:
        # 定位 .git 所在的 web 目錄
        git_dir = WEB_DIR
        if not os.path.exists(os.path.join(git_dir, '.git')):
            git_dir = BASE_DIR  # 回退到上一層

        # 只 add web/ 目錄下的變更（避免塞入 cache/ 等）
        subprocess.run(
            ['git', 'add', '.'],
            cwd=git_dir, capture_output=True, timeout=15
        )

        # 檢查是否有東西要 commit（避免空 commit 錯誤）
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=git_dir, capture_output=True, timeout=10, text=True
        )
        if not result.stdout.strip():
            # 沒變更，不需推
            return True

        # commit + push
        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=git_dir, capture_output=True, timeout=15
        )
        subprocess.run(
            ['git', 'push'],
            cwd=git_dir, capture_output=True, timeout=60
        )

        now = datetime.now().strftime('%H:%M:%S')
        print(f'✅ [{now}] Git Push 成功 | {message}')
        return True

    except subprocess.TimeoutExpired:
        print(f'⚠️ Git Push 超時 | {message}')
        return False
    except Exception as e:
        print(f'⚠️ Git Push 失敗 | {message} | {str(e)[:80]}')
        return False


def push_with_alert(tag: str, detail: str = ""):
    """
    方便的包裝函式：帶標籤的推送
    tag: 事件標籤 (GC/DC/PRE_GC/PRE_DC/TRUST_CHANGE)
    detail: 詳細描述
    """
    ts = datetime.now().strftime('%H:%M')
    msg = f"🦞 [{tag}] {detail} @{ts}"
    return quick_push(msg)


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "🦞 手動觸發 Git Push"
    ok = quick_push(msg)
    sys.exit(0 if ok else 1)
