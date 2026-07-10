#!/usr/bin/env python3
import sys, os, py_compile

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    raw = f.read()

# Define replacement pairs as (old_bytes, new_bytes)
# Use raw byte sequences to avoid any encoding issues
reps = [
    # Line 307: table header format with corrupted Chinese args
    (
        b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("\xe9\x9a\x9e??", "?\xef\x9a\x99\xe8\xbf\x82", "\xe7\x98\x9b\xe5\x88\xbb\xe7\x9c\xba\xe9\xa0\x9e?, "??\xe7\x9c\xba\xe6\x86\xad?, "??\xe7\x9c\xba\xe6\x86\xad?, "??\xe7\x9c\xba\xe6\x86\xad?, "??\xe7\x9c\xba\xe6\x86\xad?,")',
        b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))',
    ),
    # Line 313: day_str with corrupted chars
    (
        b'        day_str = "%d\xe6\x86\xad? % v["buy_days"]',
        b'        day_str = "%dD" % v["buy_days"]',
    ),
    # Line 328: watchlist section header after dash line
    (
        b'    lines.append("?? ?\xee\x93\x91?\xe6\x92\x96\xee\xb8\x82??\xe6\xa0\xbc?\xe9\x9d\xbd\xe2\x88\xa9?\xe6\x92\x85\xc2\x80?\xc2\x80\xe7\x98\x9c\xee\xbc\xb9\xc2\x80?)',
        b'    lines.append("[Watchlist] Stocks with trust accumulation:")',
    ),
    # Line 341: watchlist found format string
    (
        b'            lines.append("  %s %s %s %s | ?\xee\x9f\x9e\xe7\xb8\x91??\xe7\x9c\xba%d\xe6\x86\xad?\xe7\x98\x9b?+.1f??\xe6\x86\xad\xee\xa1\xbf?%+.1f?? % (',
        b'            lines.append("  %s %s %s %s | TrustBuy%s %+.1fW Foreign%+.1fW" % (',
    ),
    # Line 344: empty watchlist msg
    (
        b'        lines.append("  \xe9\x96\xab\xc2\x80\xe6\x92\x96\xee\xb8\x82??\xe6\xa1\x90\xe8\x91\x89?\xe2\x8a\xa5?\xe9\x9d\xbd\xe2\x88\x9f??\xee\xb8\x80?\xe6\x92\x85\xc2\x80\xe7\x92\x85\xee\xa9\x95?")',
        b'        lines.append("  (None in watchlist with accumulation)")',
    ),
    # Line 352: section 2 desc
    (
        b'    lines.append("  \xe9\x9a\x9e\xe4\xb9\xa9??\xe7\xae\xb8?\xe9\x9d\xbd\xe2\x8a\xbf\xc2\x80?\xe7\x9c\xba>=1\xe6\x86\xad\xe6\x8b\x90?\xe9\x9e\x8e\xe7\x91\x81?>50?\xe7\xa5\x88\xee\xbe\x94?\xef\x84\x95\xee\xbe\x94\xe8\x9f\xa1?)',
        b'    lines.append("  Trust buy >=1 day + total > 50W")',
    ),
    # Line 353: KD desc  
    (
        b'    lines.append("  \xef\x81\x80?',
        b'    lines.append("  (KD monitor: run KD_strategy.py separately)")',
    ),
]

changes = 0
for old, new in reps:
    if old in raw:
        raw = raw.replace(old, new)
        changes += 1
        print(f"  Fixed: {old[:50]!r}")
    else:
        # Try partial match
        if old[:30] in raw:
            print(f"  PARTIAL match for: {old[:40]!r}")
        else:
            print(f"  NOT FOUND (already fixed?): {old[:50]!r}")

with open(path, 'wb') as f:
    f.write(raw)

print(f"\nTotal changes: {changes}")

# Verify syntax
try:
    py_compile.compile(path, doraise=True)
    print("Syntax check: PASSED!")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
    # Show what's still wrong
    import subprocess, tempfile
    # Let's find remaining issues
    print("\nStill corrupted lines:")
    lines = raw.split(b'\n')
    for i, line in enumerate(lines):
        for kw in [b'potential =', b'fn_str =', b'net_str =', b'day_str =', b'emoji =', b'lines.append']:
            if kw in line:
                has_non_ascii = any(b > 127 for b in line)
                if has_non_ascii:
                    print(f"  Line {i+1}: {line[:100]!r}")
