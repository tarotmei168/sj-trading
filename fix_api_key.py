files = ['src/sj_trading/alert_system.py']
for f in files:
    content = open(f, 'r', encoding='utf-8').read()
    content = content.replace('api_key=***', 'api_key=os.environ[')
    content = content.replace(']SJ_API_KEY"]', '["SJ_API_KEY"]')
    open(f, 'w', encoding='utf-8').write(content)
    print(f'fixed {f}')
