#!/usr/bin/env python3
"""Fix all corrupted string literals in daily_market_update.py using raw bytes"""
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    data = f.read()

# Work line by line, fixing known corrupted string literals
lines = data.split(b'\n')
fixed = 0
new_lines = []

for i, line in enumerate(lines):
    lineno = i + 1
    original = line
    stripped = line.strip()
    
    # Fix each known corrupted line by exact byte matching
    # Line 303: corrupted Chinese section header
    if b'lines.append("?' in line and line.endswith(b'?)\r') or line.endswith(b'?)'):
        new_lines.append(b'    lines.append("[Section 1] Trust Accumulation Scan")')
        fixed += 1
        continue
    
    # Line 305: criteria description  
    if b'lines.append("  蝭拚' in line:
        new_lines.append(b'    lines.append("  Criteria: trust consecutive buying + total > 50W")')
        fixed += 1
        continue
    
    # Line 307: table header format
    if b'lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("' in line and b'\x80' in line:
        new_lines.append(b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))')
        fixed += 1
        continue
    
    # Line 317-319: potential signal text
    if b'        potential = "潃' in line:
        new_lines.append(b'        potential = "Trust+Bull"')
        fixed += 1
        continue
    if b'        potential = "??憭' in line:
        new_lines.append(b'        potential = "ForeignNominal"')
        fixed += 1
        continue
    if b'        potential = "?' in line:
        new_lines.append(b'        potential = "HeavyForeignSell"')
        fixed += 1
        continue
    
    # Line 321: fn_str format
    if b'fn_str = "%+.1f' in line and b'??' in line:
        new_lines.append(b'        fn_str = "%+.1fW" % (fn / 10000)')
        fixed += 1
        continue
    
    # Line 329: watchlist section
    if b'lines.append("?? ?' in line:
        new_lines.append(b'    lines.append("[Watchlist] Stocks with trust accumulation:")')
        fixed += 1
        continue
    
    # Line 341: empty watchlist msg
    if b'lines.append("  閫' in line:
        new_lines.append(b'    lines.append("  (None in watchlist with accumulation)")')
        fixed += 1
        continue
    
    # Line 344: section 2 header
    if b'lines.append("?' in line:
        new_lines.append(b'    lines.append("[Section 2] Trust + External Scan (Top 15)")')
        fixed += 1
        continue
    
    # Line 346-347: section 2 descriptions
    if b'lines.append("  隞乩' in line:
        new_lines.append(b'    lines.append("  Trust buy >=1 day + total > 50W")')
        fixed += 1
        continue
    if b'lines.append("  ?' in line and b'K<40' in line:
        new_lines.append(b'    lines.append("  (KD monitor: run KD_strategy.py separately)")')
        fixed += 1
        continue
    
    # Line 352: format string
    if b'lines.append("  %s %s | ?' in line:
        new_lines.append(b'    lines.append("  %s %s | TrustBuy %s %.1fW | Foreign %.1fW" % (')
        fixed += 1
        continue
    
    # Line 371: emoji
    if b'        emoji = "潃' in line:
        new_lines.append(b'        emoji = "*" if fn > -1000000 else "?"')
        fixed += 1
        continue
    
    # Fix for corrupted comments (lines starting with # have corrupted text too)
    # Let's skip fixing comments, they don't affect execution
    
    # If nothing matched, keep the original line
    new_lines.append(line)

# Check for remaining problems
for i, line in enumerate(new_lines):
    stripped = line.strip()
    if stripped.startswith(b'lines.append(') or stripped.startswith(b'        potential =') or stripped.startswith(b'fn_str =') or stripped.startswith(b'        emoji ='):
        # Check for unbalanced quotes or encoding artifacts
        if b'\x80' in stripped or b'\xee' in stripped or b'\xef' in stripped:
            print(f"  STILL CORRUPTED line {i+1}: {stripped[:80]}")

result = b'\n'.join(new_lines)
with open(path, 'wb') as f:
    f.write(result)

print(f"\nFixed {fixed} lines")
print(f"Output size: {len(result)} bytes")
