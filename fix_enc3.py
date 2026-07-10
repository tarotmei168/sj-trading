#!/usr/bin/env python3
import os, sys

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    data = f.read()

print(f"Read {len(data)} bytes")

# Define replacements as (old_bytes_hex_list, new_ascii)
# old_bytes: list of byte strings encoded as hex
# new_ascii: replacement text
replacements = []

# Helper to find and replace all occurrences
def apply_replacements(data, reps):
    count = 0
    for old_list, new_text in reps:
        for old_hex in old_list:
            old_bytes = bytes.fromhex(old_hex.replace(' ', ''))
            new_bytes = new_text.encode('ascii')
            if old_bytes in data:
                data = data.replace(old_bytes, new_bytes)
                count += 1
                print(f"  Replaced: {old_bytes[:20]!r} -> {new_text[:40]}")
            # else: already handled or not found
    return data, count

# Line 303: corrupted section 1 header
# "?\xee\x8f\xb2 ?\xee\x93\x8f?\xe9\x9d\xbd\xe2\x88\xa0?\xe6\x92\x96\xef\x89\x8c\xe9\x81\xa3?\xef\x90\xa3\xee\xbc\x8b\xe7\x9a\x9c\xe7\xa0\x94\xc2\x80?)"
reps = [
    # Line 303 - section header 1
    ([
        '22 3f ee 8f b2 20 3f ee 93 8f 3f e9 9d bd e2 88 a0 3f e6 92 96 ef 89 8c e9 81 a3 3f ef 90 a3 ee bc 8b e7 9a 9c e7 a0 94 c2 80 3f 29 22',
    ], '[Section 1] Trust Accumulation Scan'),
    
    # Line 305 - criteria description
    ([
        '22 20 20 e8 9d ad e6 8b 9a ee bc 8e e5 9a 97 ee ab b1 3f e9 9d bd e2 8a bf c2 80 3f e7 9c ba 20 2b 20 3f e6 a0 bc ee a3 99 e9 9e 8e e7 91 81 3e 35 30 3f e7 a5 88 ee be 94 22',
    ], '  Criteria: trust consecutive buying + total > 50W'),
    
    # Line 307 - table header with corrupted Chinese strings
    ([
        '22 e9 9a 9e 3f 3f 22',
    ], '"Code"'),
    
    # The issue is that there are multiple Chinese strings in that format...
]

# Let me try a simpler approach - just find the exact byte sequences
# for each corrupted line and replace the entire line

lines = data.split(b'\n')
new_lines = []
changes = 0
for i, line in enumerate(lines):
    orig = line
    # Remove trailing \r
    clean = line.rstrip(b'\r')
    
    # Pattern 1: Section 1 header - corrupted Chinese
    if clean.startswith(b'    lines.append("\xee') or clean.startswith(b'    lines.append("?\xee') or clean.startswith(b'    lines.append("\xef'):
        # Check if it ends with ?) or similar corruption
        stripped = clean.strip()
        if stripped.endswith(b'?)') or stripped.endswith(b'\xc2\x80?)'):
            new_lines.append(b'    lines.append("[Section 1] Trust Accumulation Scan")')
            changes += 1
            print(f"  Line {i+1}: Fixed section header 1")
            continue
    
    # Pattern 2: Criteria description
    if b'\xe8\x9d\xad\xe6\x8b\x9a' in clean and b'lines.append' in clean:
        new_lines.append(b'    lines.append("  Criteria: trust consecutive buying + total > 50W")')
        changes += 1
        print(f"  Line {i+1}: Fixed criteria desc")
        continue
    
    # Pattern 3: Table header row with corrupted Chinese args
    if b'lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("' in clean:
        if b'\x80' in clean or b'\xee' in clean or b'\xef' in clean:
            new_lines.append(b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))')
            changes += 1
            print(f"  Line {i+1}: Fixed table header")
            continue
    
    # Pattern 4: potential = "..." assignments
    if b'potential = "' in clean:
        if b'\xee' in clean or b'\xef' in clean or b'\xe8' in clean or b'\xe6' in clean:
            # Replace with signal-based text
            if b'potential = "潃' in clean or b'potential = "\xee' in clean:
                new_line = b'        potential = "Trust+Bull"'
                new_lines.append(new_line)
                changes += 1
                print(f"  Line {i+1}: Fixed potential Trust+Bull")
                continue
            elif b'potential = "??' in clean:
                new_line = b'        potential = "ForeignNominal"'
                new_lines.append(new_line)
                changes += 1
                print(f"  Line {i+1}: Fixed potential ForeignNominal")
                continue
            elif b'potential = "?\\xe8' in clean or b'potential = "?\xee\xba' in clean:
                new_line = b'        potential = "HeavyForeignSell"'
                new_lines.append(new_line)
                changes += 1
                print(f"  Line {i+1}: Fixed potential HeavyForeignSell")
                continue
    
    # Pattern 5: fn_str format with Chinese chars
    if b'fn_str = "%+.1f' in clean:
        if b'\xee' in clean or b'\xef' in clean:
            new_line = b'        fn_str = "%+.1fW" % (fn / 10000)'
            new_lines.append(new_line)
            changes += 1
            print(f"  Line {i+1}: Fixed fn_str")
            continue
    
    # Pattern 6: net_str format with Chinese chars  
    if b'net_str = "%+.1f' in clean:
        if b'\xee' in clean or b'\xef' in clean or b'\xe9' in clean:
            new_line = b'        net_str = "%+.1fW" % (v["total_net"] / 10000)'
            new_lines.append(new_line)
            changes += 1
            print(f"  Line {i+1}: Fixed net_str")
            continue
    
    # Pattern 7: Watchlist section header
    if clean.startswith(b'    lines.append("\xee') or clean.startswith(b'    lines.append("?\xee') or clean.startswith(b'    lines.append("\xef'):
        stripped = clean.strip()
        if b'watch' in stripped.lower() or b'sid' in stripped.lower():
            # Already fixed
            pass
        else:
            new_lines.append(b'    lines.append("[Watchlist] Stocks with trust accumulation:")')
            changes += 1
            print(f"  Line {i+1}: Fixed watchlist header")
            continue
    
    # Pattern 8: Empty watchlist - Chinese msg
    if b'lines.append("  \xe9\x96\xab' in clean:
        new_lines.append(b'    lines.append("  (None in watchlist with accumulation)")')
        changes += 1
        print(f"  Line {i+1}: Fixed empty watchlist")
        continue
    
    # Pattern 9: Section 2 header
    if b'lines.append("\xee\x8d\x9e' in clean or b'lines.append("?\xee\x8d\x9e' in clean:
        new_lines.append(b'    lines.append("[Section 2] Trust + External Scan (Top 15)")')
        changes += 1
        print(f"  Line {i+1}: Fixed section 2 header")
        continue
    
    # Pattern 10: Section 2 desc "  隞乩"
    if b'lines.append("  \xe9\x9a\x9e\xe4\xb9\xa9' in clean:
        new_lines.append(b'    lines.append("  Trust buy >=1 day + total > 50W")')
        changes += 1
        print(f"  Line {i+1}: Fixed section 2 desc")
        continue
    
    # Pattern 11: Section 2 desc "  ?\x80?\x9a\x99..."
    if b'lines.append("  \xef\x81\x80' in clean and b'K<40' in clean:
        new_lines.append(b'    lines.append("  (KD monitor: run KD_strategy.py separately)")')
        changes += 1
        print(f"  Line {i+1}: Fixed KD desc")
        continue
    
    # Pattern 12: Format string "  %s %s | \xee..."
    if b'lines.append("  %s %s | \xee' in clean or b'lines.append("  %s %s | ?' in clean:
        new_lines.append(b'    lines.append("  %s %s | TrustBuy %s %.1fW | Foreign %.1fW" % (')
        changes += 1
        print(f"  Line {i+1}: Fixed format string")
        continue
    
    # Pattern 13: Emoji assignment
    if b'emoji = "' in clean:
        if b'\xee' in clean or b'\xef' in clean:
            new_line = b'            emoji = "*" if fn > -1000000 else "?"'
            new_lines.append(new_line)
            changes += 1
            print(f"  Line {i+1}: Fixed emoji")
            continue
    
    # Pattern 14: Watchlist found line with format
    if b'lines.append("  %s %s %s %s | ' in clean and (b'\xee' in clean or b'\xef' in clean):
        new_lines.append(b'            lines.append("  %s %s %s %s | TrustBuy%s %+.1fW Foreign%+.1fW" % (emoji, sid, nm[:6], " "*(8-len(nm[:6])), days, tn/10000, fn/10000))')
        changes += 1
        print(f"  Line {i+1}: Fixed watchlist found line")
        continue
    
    # Pattern 15: Line with "?\\xe2\x80\x9c" - corrupted character
    if b'"?\\u2742"' in clean:
        new_line = clean.replace(b'"\\xe2\x80\x9c"', b'"HOT"')
        # Actually let me just look for it
        new_lines.append(new_line)
        changes += 1
        print(f"  Line {i+1}: Fixed hot tag")
        continue
    
    # Keep line as-is
    new_lines.append(orig)

result = b'\n'.join(new_lines)
with open(path, 'wb') as f:
    f.write(result)

print(f"\nTotal changes: {changes}")

# Verify - try to compile
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax check: PASSED!")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
