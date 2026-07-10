#!/usr/bin/env python3
import sys, os, py_compile

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    data = f.read()

lines = data.split(b'\n')
new_lines = []
changes = 0

# Track the original fix_enc4.py fixes and add the net_str fix
# net_str = "%+.1f?? % (v["total_net"] / 10000)
# This has corrupted `W"` -> `??` (0x3f 0x3f) causing unterminated string
for i, line in enumerate(lines):
    clean = line.rstrip(b'\r')

    # Helper
    def has_bytes(s):
        return bytes.fromhex(s.replace(' ', '')) in clean

    MATCHED = False

    # 1) Section 1 header
    if has_bytes('6c696e65732e617070656e642822ee8fb2') or \
       has_bytes('6c696e65732e617070656e6428223fee8fb2'):
        new_lines.append(b'    lines.append("[Section 1] Trust Accumulation Scan")')
        MATCHED = True
        changes += 1

    # 2) Criteria description
    elif has_bytes('e89dade68b9a') and b'lines.append' in clean:
        new_lines.append(b'    lines.append("  Criteria: trust consecutive buying + total > 50W")')
        MATCHED = True
        changes += 1

    # 3) Table header
    elif has_bytes('6c696e65732e617070656e64282220252d367320252d38732025387320253873202535732020252d313073222025202822') and \
         (has_bytes('80') or has_bytes('ee') or has_bytes('ef')):
        new_lines.append(b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))')
        MATCHED = True
        changes += 1

    # 4) potential assignments (3 places)
    elif b'potential = "' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('e8') or has_bytes('e6') or has_bytes('9c83')):
        if has_bytes('9c83') or has_bytes('ee'):
            new_line = b'        potential = "Trust+Bull"'
        elif has_bytes('86adeea1bf'):
            new_line = b'        potential = "ForeignNominal"'
        else:
            new_line = b'        potential = "HeavyForeignSell"'
        new_lines.append(new_line)
        MATCHED = True
        changes += 1

    # 5) fn_str format
    elif b'fn_str =' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('3f3f') or has_bytes('e9')):
        new_lines.append(b'        fn_str = "%+.1fW" % (fn / 10000)')
        MATCHED = True
        changes += 1

    # 6) net_str format - KEY FIX: corrupted W" -> ??
    elif b'net_str =' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('e9') or has_bytes('3f3f')):
        # Check if it has non-standard format indicating corruption
        # The correct line should be: net_str = "%+.1fW" % (v["total_net"] / 10000)
        new_lines.append(b'        net_str = "%+.1fW" % (v["total_net"] / 10000)')
        MATCHED = True
        changes += 1

    # 7) Watchlist section header (corrupted Chinese line after dash line)
    elif has_bytes('6c696e65732e617070656e642822ee8984') or \
         has_bytes('6c696e65732e617070656e6428223fee8984') or \
         has_bytes('6c696e65732e617070656e642822ef'):
        # But only if it contains non-ASCII and is NOT an already-fixed line
        if has_bytes('ee') or has_bytes('ef') or has_bytes('80'):
            new_lines.append(b'    lines.append("[Watchlist] Stocks with trust accumulation:")')
            MATCHED = True
            changes += 1

    # 8) Empty watchlist msg
    elif has_bytes('6c696e65732e617070656e64282220e996ab'):
        new_lines.append(b'    lines.append("  (None in watchlist with accumulation)")')
        MATCHED = True
        changes += 1

    # 9) Section 2 header
    elif has_bytes('6c696e65732e617070656e642822ee8d9e') or \
         has_bytes('6c696e65732e617070656e6428223fee8d9e'):
        new_lines.append(b'    lines.append("[Section 2] Trust + External Scan (Top 15)")')
        MATCHED = True
        changes += 1

    # 10) Section 2 desc "  \xe9\x9a\x9e" (trust buy condition)
    elif has_bytes('6c696e65732e617070656e64282220e99a9ee4b9a9') or \
         has_bytes('6c696e65732e617070656e64282220e99a9e') and b'lines.append' in clean:
        new_lines.append(b'    lines.append("  Trust buy >=1 day + total > 50W")')
        MATCHED = True
        changes += 1

    # 11) Section 2 desc with K<40
    elif has_bytes('6c696e65732e617070656e64282220') and b'K<40' in clean:
        new_lines.append(b'    lines.append("  (KD monitor: run KD_strategy.py separately)")')
        MATCHED = True
        changes += 1

    # 12) Format string with corrupted chars
    elif b'lines.append("  %s %s |' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('80')):
        new_lines.append(b'    lines.append("  %s %s | TrustBuy %s %.1fW | Foreign %.1fW" % (')
        MATCHED = True
        changes += 1

    # 13) emoji = "..." assignments
    elif b'emoji = "' in clean and (has_bytes('9c83') or has_bytes('ee') or has_bytes('ef') or has_bytes('3f3f')):
        new_lines.append(b'            emoji = "*" if fn > -1000000 else "?"')
        MATCHED = True
        changes += 1

    # 14) Watchlist found line with format
    elif has_bytes('6c696e65732e617070656e642822202573202573202573202573207c20ee') or \
         has_bytes('6c696e65732e617070656e642822202573202573202573202573207c203f'):
        new_lines.append(b'            lines.append("  %s %s %s %s | TrustBuy%s %+.1fW Foreign%+.1fW" % (emoji, sid, nm[:6], " "*(8-len(nm[:6])), days, tn/10000, fn/10000))')
        MATCHED = True
        changes += 1

    # If nothing matched, keep original
    if not MATCHED:
        new_lines.append(line)

result = b'\n'.join(new_lines)
with open(path, 'wb') as f:
    f.write(result)

print(f"Total changes: {changes}")

# Verify syntax
try:
    py_compile.compile(path, doraise=True)
    print("Syntax check: PASSED!")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
