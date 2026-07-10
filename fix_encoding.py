#!/usr/bin/env python
"""Fix encoding corruption in daily_market_update.py"""
import re

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Find and fix all corrupted string literals by replacing with safe ASCII equivalents
# The issue is that Chinese text was double-encoded or corrupted

# Strategy: Replace the corrupted string literal lines with ASCII-safe versions
text = data.decode('utf-8', errors='replace')

# Fix specific known corrupted strings
fixes = {
    # Line 303 - section 1 header
    'lines.append("?\\uf3f2 ?\\ue4cf?靽∠?撖\\uf24c遣?\\uf423\\uef0b皜研\\x80?)':
        'lines.append("[Section 1] Trust Accumulation Scan")',
    
    # Line 305 - criteria description
    'lines.append("  蝭拚嚗?靽⊿\\x80?眺 + ?格鞎瑁?>50?祈")':
        'lines.append("  Criteria: trust consecutive buying + total > 50W")',
    
    # Line 307 - table header
    'lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("隞??", "?迂", "瘛刻眺頞?, "??眺憭?, "憭?", "瞏?"))':
        'lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))',
    
    # Line 317-319 - potential signals
    '        potential = "潃?靽∟?擗?"':
        '        potential = "Trust+Bull"',
    '        potential = "??憭?撠?"':
        '        potential = "ForeignNominal"',
    '        potential = "??憭?憭扯都"':
        '        potential = "HeavyForeignSell"',
    
    # Line 321-322 - format string
    'fn_str = "%+.1f?? % (fn / 10000)':
        'fn_str = "%+.1fW" % (fn / 10000)',
    
    # Line 329 - watchlist section
    'lines.append("?? ??撖??格?靽∩?撅\\x80?\\x80瘜\\x80?)":
        'lines.append("[Watchlist] Stocks with trust accumulation:")',
    
    # Line 341 - empty watchlist message
    'lines.append("  閫\\x80撖??桐葉?⊥?靽∟???撅\\x80璅?")':
        'lines.append("  (None in watchlist with accumulation)")',
    
    # Line 344 - section 2 header
    'lines.append("? ??靽⊿\\x80?眺+?\\x80銵蝭拚???\\x80銝脫KD鞈?蝣箄?雿?)":
        'lines.append("[Section 2] Trust + External Scan (Top 15)")',
    
    # Line 346-347 - section 2 description
    'lines.append("  隞乩??箸?靽⊿\\x80?眺>=1憭拐?鞎瑁?>50?祈?蟡?)':
        'lines.append("  Trust buy >=1 day + total > 50W")',
    'lines.append("  ?\\x80?Ⅱ隤D?臬?其?瑼?(K<40)?\\x80脣")':
        'lines.append("  (KD monitor: run KD_strategy.py separately)")',
    
    # Line 352 - format string
    'lines.append("  %s %s | ?縑??眺%s %.1f?祈 | 憭?%.1f?祈" % (':
        'lines.append("  %s %s | TrustBuy %s %.1fW | Foreign %.1fW" % (',
    
    # Line 371 - emoji
    '        emoji = "潃? if fn > -1000000 else "??"':
        '        emoji = "*" if fn > -1000000 else "?"',
    
    # Line 375 - hot tag
    '"?\\u2742"':
        '" HOT"',
}

for old, new in fixes.items():
    if old in text:
        text = text.replace(old, new)
        print(f'Fixed: {old[:40]}...')
    else:
        print(f'NOT FOUND: {old[:40]}...')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('\nDone')
