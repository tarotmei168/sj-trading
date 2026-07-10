#!/usr/bin/env python3
path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'
with open(path, 'rb') as f:
    data = f.read()

# Fix the broken if/elif/else block in trust_hot loop
# Current broken:
#         potential = "Trust+Bull"
#         potential = "Trust+Bull"
#         elif fn > -5000000:
#         potential = "Trust+Bull"
#         else:
#         potential = "Trust+Bull"
#
# Should be:
#         if fn > -1000000:
#             potential = "Trust+Bull"
#         elif fn > -5000000:
#             potential = "ForeignNominal"
#         else:
#             potential = "HeavyForeignSell"

# Find the unique sequence to replace
# The two consecutive `potential = "Trust+Bull"` lines after day_str
target = b'        potential = "Trust+Bull"\n        potential = "Trust+Bull"\n        elif fn > -5000000:\n        potential = "Trust+Bull"\n        else:\n        potential = "Trust+Bull"'
replacement = b'        if fn > -1000000:\n            potential = "Trust+Bull"\n        elif fn > -5000000:\n            potential = "ForeignNominal"\n        else:\n            potential = "HeavyForeignSell"'

if target in data:
    data = data.replace(target, replacement)
    print("Fixed if/elif/else block for potential")
else:
    print("Target not found, looking...")
    # Find the partial sequence
    idx = data.find(b'elif fn > -5000000:')
    if idx >= 0:
        print(f"Found elif at offset {idx}")
    else:
        print("elif not found either")

with open(path, 'wb') as f:
    f.write(data)
print("Done")
