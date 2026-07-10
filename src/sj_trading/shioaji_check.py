"""Shioaji API 深度調查"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import shioaji as sj

# Snapshot
print('=== Shioaji Snapshot API ===')
snap_attrs = [m for m in dir(sj.Snapshot) if not m.startswith('_')]
print(f'Snapshot 属性: {snap_attrs}')

# Ticks
print(f'\n=== Ticks ===')
tick_attrs = [m for m in dir(sj.Ticks) if not m.startswith('_')]
print(f'Ticks 属性: {tick_attrs}')

# KBars
print(f'\n=== KBars ===')
kbar_attrs = [m for m in dir(sj.KBars) if not m.startswith('_')]
print(f'KBars 属性: {kbar_attrs}')

# TicksQueryType
print(f'\n=== TicksQueryType ===')
try:
    print(f'TicksQueryType: {list(sj.TicksQueryType)}')
except:
    print('no TicksQueryType')

# Snapshot fields
print(f'\n=== Snapshot 字段 ===')
try:
    # Try importing SnapshotFields
    print(sj.Snapshot.__doc__[:500] if sj.Snapshot.__doc__ else '(no doc)')
except:
    pass

# 检查从 login 回来的 client 能做什么
print('\n=== 模拟连线后可用 API ===')
# 用 login 的返回看
print(f'每日报价: DailyQuotes -> {[m for m in dir(sj.DailyQuotes) if not m.startswith("_")]}')
print(f'BidAskSTKv1: {[m for m in dir(sj.BidAskSTKv1) if not m.startswith("_")]}')
print(f'TickSTKv1: {[m for m in dir(sj.TickSTKv1) if not m.startswith("_")]}')
