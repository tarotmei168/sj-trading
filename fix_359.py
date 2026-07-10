#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Fix line 359: "%d\xe6\x86\xad? % v["buy_days"] -> "%dD" % v["buy_days"]
# The corrupted bytes are \xe6\x86\xad (Chinese char) followed by ?
target = b'        sid, v["name"][:6], "%d\xe6\x86\xad? % v["buy_days"], v["total_net"]/10000, fn/10000))'
replacement = b'            sid, v["name"][:6], "%dD" % v["buy_days"], v["total_net"]/10000, fn/10000))'

if target in data:
    data = data.replace(target, replacement)
    print("Fixed line 359")
else:
    # Try with different indentation
    for indent in [b'        ', b'            ', b'    ', b'          ']:
        try_target = indent + b'sid, v["name"][:6], "%d\xe6\x86\xad? % v["buy_days"]'
        if try_target in data:
            repl = indent + b'sid, v["name"][:6], "%dD" % v["buy_days"]'
            data = data.replace(try_target, repl)
            print(f"Fixed line 359 (indent={len(indent)})")
            break
    else:
        # Search more broadly
        idx = data.find(b'v["name"][:6], "%d')
        if idx >= 0:
            # Found the line, find end
            print(f"Found at offset {idx}")
            # Show context
            ctx = data[max(0,idx-40):idx+80]
            print(f"Context: {ctx!r}")
            # Try replacing from name through buy_days
            old = b'v["name"][:6], "%d\xe6\x86\xad? % v["buy_days"]'
            new = b'v["name"][:6], "%dD" % v["buy_days"]'
            data = data.replace(old, new)
            print("Fixed (broad search)")
        else:
            print("Not found")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
