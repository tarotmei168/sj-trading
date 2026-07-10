#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Find the corrupted line - search for unique ASCII prefix
target = b'lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ('
idx = data.find(target)
if idx >= 0:
    # Find end of line
    eol = data.find(b'\n', idx)
    replacement = b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))'
    data = data[:idx] + replacement + data[eol:]
    print("Fixed table header line")
else:
    # Try shorter search
    target2 = b'%-6s %-8s %8s %8s %5s  %-10s'
    idx2 = data.find(target2)
    if idx2 >= 0:
        # Find start of line
        sol = data.rfind(b'\n', 0, idx2) + 1
        eol = data.find(b'\n', idx2)
        print(f"Found at offset {sol}-{eol}")
        replacement = b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))'
        data = data[:sol] + replacement + data[eol:]
        print("Fixed")
    else:
        print("Not found")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
