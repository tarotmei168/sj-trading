#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Find "trade_dates = []" and look at what's before it
idx = data.find(b'trade_dates = []')
if idx >= 0:
    # Show 30 bytes before it
    ctx = data[max(0,idx-30):idx+20]
    print(f"Context: {ctx!r}")
    print(f"Hex: {ctx.hex()}")
    
    # Check if there's a newline before it
    nl_before = data.rfind(b'\n', 0, idx)
    print(f"Last newline before: {nl_before}")
    line = data[nl_before:idx+20]
    print(f"Full line: {line!r}")
    
    # Find the hash comment marker
    hash_pos = data.rfind(b'#', nl_before, idx)
    print(f"Hash at: {hash_pos}")
    
    if hash_pos > nl_before:
        # The # makes everything to end of line a comment
        # trade_dates is on same line as #, so it's in the comment!
        # Fix: insert newline before trade_dates
        td_idx = data.find(b'trade_dates', idx - 5)
        # Insert newline
        data = data[:td_idx] + b'\n    ' + data[td_idx:]
        with open(path, 'wb') as f:
            f.write(data)
        print(f"Fixed: inserted newline before trade_dates")
    else:
        print("No hash before trade_dates, check other issue")
else:
    print("Not found")
