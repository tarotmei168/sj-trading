#!/usr/bin/env python3
import sys, os

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    data = f.read()

print(f"Read {len(data)} bytes")

lines = data.split(b'\n')
new_lines = []
changes = 0

for i, line in enumerate(lines):
    clean = line.rstrip(b'\r')

    # Helper: check if line contains bytes from given hex sequence
    def has_bytes(hex_str):
        return bytes.fromhex(hex_str.replace(' ', '')) in clean

    MATCHED = False

    # 1) Section 1 header - starts with corrupted chars
    #   'lines.append("\xee\x8f\xb2 ...'
    if MATCHED:
        pass
    elif has_bytes('6c696e65732e617070656e642822ee8fb2') or \
         has_bytes('6c696e65732e617070656e6428223fee8fb2'):
        new_lines.append(b'    lines.append("[Section 1] Trust Accumulation Scan")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Section 1 header")

    # 2) Criteria description
    elif has_bytes('e89dade68b9a') and b'lines.append' in clean:
        new_lines.append(b'    lines.append("  Criteria: trust consecutive buying + total > 50W")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Criteria desc")

    # 3) Table header with corrupted Chinese args
    elif has_bytes('6c696e65732e617070656e64282220252d367320252d38732025387320253873202535732020252d313073222025202822') and \
         (has_bytes('80') or has_bytes('ee') or has_bytes('ef')):
        new_lines.append(b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Table header")

    # 4) potential assignments
    elif b'potential = "' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('e8') or has_bytes('e6')):
        if has_bytes('9c83') or has_bytes('ee'):
            new_line = b'        potential = "Trust+Bull"'
        elif has_bytes('86adeea1bf'):
            new_line = b'        potential = "ForeignNominal"'
        else:
            new_line = b'        potential = "HeavyForeignSell"'
        new_lines.append(new_line)
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: potential assignment")

    # 5) fn_str format
    elif b'fn_str =' in clean and has_bytes('ee'):
        new_lines.append(b'        fn_str = "%+.1fW" % (fn / 10000)')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: fn_str")

    # 6) net_str format
    elif b'net_str =' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('e9')):
        new_lines.append(b'        net_str = "%+.1fW" % (v["total_net"] / 10000)')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: net_str")

    # 7) Watchlist section header
    elif has_bytes('6c696e65732e617070656e642822ee8984') or \
         has_bytes('6c696e65732e617070656e6428223fee8984') or \
         has_bytes('6c696e65732e617070656e642822ef'):
        new_lines.append(b'    lines.append("[Watchlist] Stocks with trust accumulation:")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Watchlist header")

    # 8) Empty watchlist msg
    elif has_bytes('6c696e65732e617070656e64282220e996ab'):
        new_lines.append(b'    lines.append("  (None in watchlist with accumulation)")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Empty watchlist")

    # 9) Section 2 header  
    elif has_bytes('6c696e65732e617070656e642822ee8d9e'):
        new_lines.append(b'    lines.append("[Section 2] Trust + External Scan (Top 15)")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Section 2 header")

    # 10) Section 2 desc "  \xe9\x9a\x9e"
    elif has_bytes('6c696e65732e617070656e64282220e99a9ee4b9a9'):
        new_lines.append(b'    lines.append("  Trust buy >=1 day + total > 50W")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Section 2 desc 1")

    # 11) Section 2 desc with K<40
    elif has_bytes('6c696e65732e617070656e64282220') and b'K<40' in clean:
        new_lines.append(b'    lines.append("  (KD monitor: run KD_strategy.py separately)")')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Section 2 desc KD")

    # 12) Format string with corrupted chars
    elif b'lines.append("  %s %s |' in clean and (has_bytes('ee') or has_bytes('ef')):
        new_lines.append(b'    lines.append("  %s %s | TrustBuy %s %.1fW | Foreign %.1fW" % (')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Format string")

    # 13) emoji = "..." assignments
    elif b'emoji = "' in clean and (has_bytes('ee') or has_bytes('ef') or has_bytes('9c83')):
        new_lines.append(b'            emoji = "*" if fn > -1000000 else "?"')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Emoji")

    # 14) Watchlist found line
    elif has_bytes('6c696e65732e617070656e642822202573202573202573202573207c20') and \
         (has_bytes('ee') or has_bytes('ef')):
        new_lines.append(b'            lines.append("  %s %s %s %s | TrustBuy%s %+.1fW Foreign%+.1fW" % (emoji, sid, nm[:6], " "*(8-len(nm[:6])), days, tn/10000, fn/10000))')
        MATCHED = True
        changes += 1
        print(f"Line {i+1}: Watchlist found")

    # If nothing matched, keep original
    if not MATCHED:
        new_lines.append(line)

result = b'\n'.join(new_lines)
with open(path, 'wb') as f:
    f.write(result)

print(f"\nTotal changes: {changes}")

# Verify syntax
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax check: PASSED!")
except py_compile.PyCompileError as e:
    print(f"Syntax check FAILED: {e}")
