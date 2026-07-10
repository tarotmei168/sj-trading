import sys, ast
sys.stdout.reconfigure(encoding='utf-8')
with open('src/sj_trading/lobster_pipeline.py', 'r', encoding='utf-8') as f:
    code = f.read()
try:
    ast.parse(code)
    checks = ['rsi_data', 'RSI位階天氣預報', 'full_report(rsi_data']
    for c in checks:
        ok = c in code
        print(f'  [{"OK" if ok else "-"}] {c}')
    print(f'Code {len(code)} chars - syntax OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
