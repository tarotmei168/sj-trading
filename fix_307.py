#!/usr/bin/env python3
import sys
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()
# Fix line 307: corrupted table header with 6 Chinese args
old = data.find(b'lines.append("  %-6s')
if old >= 0:
    # Find the end of this statement (next \n    lines.append or \n#)
    end = data.find(b'\n    lines.append("-", old+1)
    if end < 0:
        end = data.find(b'\n    #', old+1)
    if end < 0:
        end = data.find(b'\n\n', old+1)
    if end < 0:
        end = old + 200

    # Print context for debugging
    context = data[old:old+250]
    print(f"Found at offset {old}")
    print(f"Context hex snippet: {context[:100].hex()}")

    # Replace the whole line with the corrent header  
    # First find the start of this line
    start = data.rfind(b'\n', 0, old) + 1
    # Find end of this logical line (the closing ))
    # Find the closing )) 
    paren_depth = 0
    in_string = False
    quote_char = None
    end_pos = old
    for j in range(old, min(old + 300, len(data))):
        ch = data[j:j+1]
        if in_string:
            if ch == b'\\':
                j += 1  # skip next
                continue
            if ch == quote_char:
                in_string = False
            continue
        if ch in (b'"', b"'"):
            in_string = True
            quote_char = ch
            continue
        if ch == b'(':
            paren_depth += 1
        elif ch == b')':
            paren_depth -= 1
            if paren_depth <= 0:
                end_pos = j + 1
                break

    print(f"Replacing lines {start}-{end_pos}")
    print(f"Old ending bytes: {data[end_pos-10:end_pos+5]!r}")
    
    new_line = b'    lines.append("  %-6s %-8s %8s %8s %5s  %-10s" % ("Code", "Name", "TrustNet", "BuyDays", "Foreign", "Signal"))\n'
    data = data[:start] + new_line + data[end_pos:]

with open(path, 'wb') as f:
    f.write(data)
print("Done")
