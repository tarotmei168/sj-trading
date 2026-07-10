#!/usr/bin/env python3
import py_compile

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    raw = f.read()

reps = [
    # Line 307: table header with 6 corrupted Chinese args
    (
        b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("\xe9\x9a\x9e??", "?\xef\x9a\x99\xe8\xbf\x82", "\xe7\x98\x9b\xe5\x88\xbb\xe7\x9c\xba\xe9\xa0\x9e?, "??\xe7\x9c\xba\xe6\x86\xad?, "\xe6\x86\xad\xee\xa1\xbf?", "\xe7\x9e\x8f\xee\xae\x8d?"))',
        b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))',
    ),
    # Line 359: another day_str corruption inside lines.append
    (
        b'            sid, v["name"][:6], "%d\xe6\x86\xad? % v["buy_days"], v["total_net"]/10000, fn/10000))',
        b'            sid, v["name"][:6], "%dD" % v["buy_days"], v["total_net"]/10000, fn/10000))',
    ),
]

changes = 0
for old, new in reps:
    if old in raw:
        raw = raw.replace(old, new)
        changes += 1
        print(f"  Fixed: {old[:50]!r}")
    else:
        print(f"  NOT FOUND: {old[:50]!r}")

with open(path, 'wb') as f:
    f.write(raw)

print(f"Changes: {changes}")

try:
    py_compile.compile(path, doraise=True)
    print("Syntax check: PASSED!")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
    # Show remaining corrupted
    lines = raw.split(b'\n')
    for i, line in enumerate(lines):
        for kw in [b'potential =', b'fn_str =', b'net_str =', b'day_str =', b'emoji =', b'lines.append']:
            if kw in line:
                if any(b > 127 for b in line):
                    print(f"  Line {i+1}: {line[:120]!r}")
