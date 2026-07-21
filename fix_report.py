# -*- coding: utf-8 -*-
"""Fix potential stocks block in daily_web_report.py"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('src/sj_trading/daily_web_report.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Find and replace the Jinja2-style block
old_block_start = '    {% if potential_stocks %}'
old_block_end = '            {% endif %}'

idx_start = c.find(old_block_start)
idx_end = c.find(old_block_end)
if idx_start >= 0 and idx_end >= 0:
    idx_end += len(old_block_end)  # include the endif line
    
    new_html = '''    <!-- 潛力股候選（動態從全市場掃描）-->
    <div class="card info">
        <div class="card-title">🎯 潛力股候選（投信連買中，非持股）</div>
        <table>
            <thead>
                <tr>
                    <th>代號</th><th>名稱</th>
                    <th>連買</th>
                    <th>投信買超</th>
                    <th>法人（外資）</th>
                    <th>備註</th>
                </tr>
            </thead>
            <tbody>{potential_rows}</tbody>
        </table>
    </div>'''
    
    c = c[:idx_start] + new_html + c[idx_end:]
    print("Replaced Jinja2 block")
else:
    print("Could not find Jinja2 block")
    # search near news block
    idx = c.find('<!-- 新聞區塊')
    print("Near news block:", repr(c[idx-200:idx+100]))

# Add potential_rows generation before the f-string html template
# Find '    # ═══════════════════════════════════════════'
# The one just before the f-string html
marker = '    # ═══════════════════════════════════════════\n    #  🏗️ 最終 HTML'
if marker in c:
    pot_rows_code = '''
    # ── 潛力股候選 HTML 行 ──
    potential_rows = ''
    for p in potential_stocks:
        fn_color = 'var(--green-go);font-weight:bold;' if p['total_foreign'] < 0 else 'var(--red-alert);font-weight:bold;'
        potential_rows += (
            f'<tr><td>{p[\"sid\"]}</td><td>{p[\"name\"]}</td>'
            f'<td>{p[\"days\"]}天</td>'
            f'<td style=\"color:var(--red-alert);font-weight:bold;\">{p[\"total_trust\"]:,}</td>'
            f'<td style=\"color:{fn_color}\">{p[\"total_foreign\"]:+,}</td>'
            f'<td>✨ 投信連買</td></tr>\\n'
        )
    if not potential_rows:
        potential_rows = '<tr><td colspan=\"6\" style=\"text-align:center;color:#666;\">盤後16:30更新全市場掃描</td></tr>'
'''
    c = c.replace(marker, pot_rows_code + '\n' + marker)
    print("Added potential_rows generation")
else:
    print("Could not find marker for final f-string")
    # find the last marker
    idx = c.rfind('═══════════════════════════════════════════')
    print("Last marker at", idx, ":", c[idx:idx+80])

with open('src/sj_trading/daily_web_report.py', 'w', encoding='utf-8') as f:
    f.write(c)
print("Done")
