with open('src/sj_trading/ta_strategy_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '.badge-blue{background:#1a2a4a;color:#4a9eff;}',
    '.badge-blue{background:#5a1a1a;color:#ffd700;}'
)

with open('src/sj_trading/ta_strategy_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('OK')
with open('src/sj_trading/ta_strategy_engine.py', 'r', encoding='utf-8') as f:
    c2 = f.read()
print(f'badge-red gold: {"#ffd700" in c2}')
print(f'badge-blue gold: {"#ffd700" in c2}')
