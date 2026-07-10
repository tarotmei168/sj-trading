#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# The corrupted comment line has trade_dates = [] as part of the comment
# Find the line and split it so trade_dates = [] is on its own line
# Current: # ???...    trade_dates = []
# Should be: # ???...\n    trade_dates = []

# Find "trade_dates = []" that's inside a comment
# Search for the specific pattern: corrupted Chinese ending followed by trade_dates
idx = data.find(b'trade_dates = []')
if idx >= 0:
    # Check if there's a '#' before this
    line_start = data.rfind(b'\n', 0, idx) + 1
    if data[line_start:line_start+5] == b'    # ':
        # This is inside a comment! Fix it
        # Move trade_dates to its own line
        # Find the exact position
        td_pos = data.find(b'trade_dates = []', idx - 10)
        # Insert newline before trade_dates if preceded by comment content
        # The line is: spaces, #, corrupted_comment_padding, spaces, trade_dates = []
        # We need to change the space before trade_dates to \n
        before_td = td_pos - 1
        while data[before_td:before_td+1] == b' ':
            before_td -= 1
        before_td += 1
        # Now before_td points to the first space before trade_dates
        # Change 4 spaces to \n
        data = data[:before_td] + b'\n' + data[before_td+4:]
        print(f"Fixed trade_dates at offset {td_pos}")
    else:
        print(f"trade_dates found but not in comment context: {repr(data[line_start:line_start+10])}")
else:
    print("trade_dates not found")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
