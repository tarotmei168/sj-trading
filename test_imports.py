#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""匯入測試"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'sj_trading'))

print("[OK] 正在測試模組載入...")

from intraday_git_pusher import quick_push, push_with_alert
print("[OK] intraday_git_pusher 載入成功")

from scheduler_cockpit import log, run_morning_report, check_trust_change
print("[OK] scheduler_cockpit 載入成功")

print("\n[PASS] 全部模組載入成功，排程系統就緒！")
