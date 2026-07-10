import sys, ast
sys.stdout.reconfigure(encoding='utf-8')
with open('src/sj_trading/taiwan_lobster_realtime.py', 'r', encoding='utf-8') as f:
    code = f.read()
try:
    ast.parse(code)
    checks = ['_compute_rsi', '_update_rsi_status', 'rsi_oversold', 'rsi_overbought',
              'RSI', '_rsi_tag', '_analyze_tick_whale', 'whale_buy_pct', 'whale_net_amt']
    for c in checks:
        ok = c in code
        print(f'  [{"OK" if ok else "XX"}] {c}')
    print(f'\nCode {len(code)} chars - syntax OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
