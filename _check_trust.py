# 檢查 trust_rates 在 HTML 模板裡的位置
with open('src/sj_trading/daily_web_report.py','r',encoding='utf-8') as f:
    c=f.read()

idx = c.find("html = f'''")
tmpl = c[idx:idx+20000]
lines = tmpl.split('\n')
found = False
for i,l in enumerate(lines):
    if '滲透' in l or 'trust_rate' in l:
        print(f'L{i}: {l.strip()[:120]}')
        found = True
if not found:
    print('✅ 主HTML模板中完全沒有滲透率/trust_rates')
    # 確認參數trust_rates是否有被用到
    print()
    print('=== 檢查 gen_html 參數 ===')
    print('trust_rates 參數確實存在但未在HTML模板中被渲染')
