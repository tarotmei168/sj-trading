#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Find `elif fn > -5000000:` which is at offset 13165
elif_offset = data.find(b'elif fn > -5000000:')
if elif_offset >= 0:
    # Find start of line (previous \n)
    sol = data.rfind(b'\n', 0, elif_offset)
    # We need to replace from line before the 'elif' (the double potential lines) through 
    # the `else: potential = "..."` lines
    
    # Let me find the beginning of the block (the 1st potential = "Trust+Bull" after day_str)
    # Look back from elif_offset
    first_potential = data.rfind(b'potential = "Trust+Bull"', 0, elif_offset)
    if first_potential >= 0:
        block_start = data.rfind(b'\n', 0, first_potential)
        
        # Find end of block (after the last potential line after else)
        else_offset = data.find(b'else:', elif_offset)
        after_else = data.find(b'\n', data.find(b'\n', else_offset) + 1)
        
        # Now replace everything from block_start+1 through after_else
        old_block = data[block_start+1:after_else]
        new_block = b'        if fn > -1000000:\n            potential = "Trust+Bull"\n        elif fn > -5000000:\n            potential = "ForeignNominal"\n        else:\n            potential = "HeavyForeignSell"'
        
        data = data[:block_start+1] + new_block + data[after_else:]
        print(f"Fixed if/elif/else block. Replaced {len(old_block)} bytes with {len(new_block)} bytes")
        print(f"Old block: {old_block[:100]!r}")
else:
    print("elif not found")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
