"""檢查即時引擎語法"""
import sys, ast
sys.stdout.reconfigure(encoding='utf-8')
with open('src/sj_trading/taiwan_lobster_realtime.py', 'r', encoding='utf-8') as f:
    code = f.read()
try:
    ast.parse(code)
    checks = ['_analyze_tick_whale', '_update_whale_metrics', 'reset_whale_stats',
              'update_snapshot_oi', 'whale_net', 'trade_avg_size', '_poll_snapshots']
    for c in checks:
        found = c in code
        print(f'  [{"✅" if found else "❌"}] {c}')
    print(f'\n  程式碼 {len(code)} chars — 語法正確 ✅')
except SyntaxError as e:
    print(f'❌ 語法錯誤: {e}')
