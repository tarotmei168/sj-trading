#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Fix indentation: 8 spaces -> 4 spaces for the table header line
target = b'        lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))'
replacement = b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))'

if target in data:
    data = data.replace(target, replacement)
    with open(path, 'wb') as f:
        f.write(data)
    print("Fixed indentation")
else:
    print("Target not found, checking...")
    # Find partial match
    p = b'lines.append("%-6s'
    idx = data.find(p)
    if idx >= 0:
        line_start = data.rfind(b'\n', 0, idx) + 1
        line_end = data.find(b'\n', idx)
        print(f"Found at offset {line_start}-{line_end}")
        print(f"Content: {data[line_start:line_end]!r}")
