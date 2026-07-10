#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Find the corrupted table header line by searching for unique prefix
# bytes: lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % (
# hex: 6c696e65732e617070656e64282220252d367320252d38732025387320253873202535732020252d313073222025202822
prefix = bytes.fromhex('6c696e65732e617070656e64282220252d367320252d38732025387320253873202535732020252d313073222025202822')
idx = data.find(prefix)
if idx >= 0:
    # Find the end of this statement - look for \n with correct indentation
    next_newline = data.find(b'\n', idx)
    # Store this line
    old_line_end = next_newline
    # The corrupted string might continue past one line
    # Let's find the closing ))
    search_start = next_newline + 1
    # Search for the pattern at the start of the next line that matches section 1 format
    section_end = data.find(b'\n    for sid', idx)  # next for loop starts the section
    
    replacement = b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))\n'
    
    # The corrupted line might actually span multiple lines, find the real end
    # Look for \n followed by next statement
    next_stmt = data.find(b'\n    for sid', idx)
    if next_stmt < 0:
        next_stmt = data.find(b'\n    trust_hot', idx)
    
    data = data[:idx] + replacement + data[section_end:]
    print(f"Fixed table header at offset {idx}")
else:
    print("Not found (might already be fixed)")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
