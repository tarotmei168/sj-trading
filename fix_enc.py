#!/usr/bin/env python
"""Fix encoding corruption in daily_market_update.py - using bytes to avoid encoding issues"""
import re

path = r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_market_update.py'

with open(path, 'rb') as f:
    data = f.read()

# Replace corrupted lines using exact byte sequences
# Strategy: find line endings we know are correct, and replace everything in between

replacements = []

# Helper: find content between known anchors
def replace_between(start_marker, end_marker, new_content):
    """Replace content between start_marker and end_marker with new ASCII bytes"""
    start_idx = data.find(start_marker)
    if start_idx < 0:
        print(f"WARN: start marker not found: {start_marker[:30]}")
        return None
    end_idx = data.find(end_marker, start_idx + len(start_marker))
    if end_idx < 0:
        print(f"WARN: end marker not found: {end_marker[:30]}")
        return None
    
    old_bytes = data[start_idx:end_idx + len(end_marker)]
    new_bytes = new_content.encode('ascii')
    
    global data
    data = data[:start_idx] + new_bytes + data[end_idx + len(end_marker):]
    return True

# Let me work with the raw text using latin-1 to preserve all byte values
text_latin = data.decode('latin-1')

# Define fixes using latin-1 decoded strings (preserves all bytes as-is)
fixes_latin = {}

# Line 303: section 1 header - the original line has corrupted chars at end
# Looking at hex: \xee\x8f\xb2 \xee\x93\x8f\xe9\x9d\xbd...\xc2\x80?)
# The corruption is at the end where \xc2\x80 appears inside the string before )
old_l303 = text_latin.find('lines.append("')
# Find this specific occurrence - find the second one (the corrupted one)
offset = 0
count = 0
line303_start = None
while True:
    idx = text_latin.find('lines.append("', offset)
    if idx < 0:
        break
    count += 1
    if count == 2:
        line303_start = idx
        break
    offset = idx + 1

# This is getting complex. Let me just write the whole current file content,
# find and fix specific problematic patterns

print("File size:", len(data), "bytes")

# Let me identify all the problematic lines by looking for lines with
# corrupted Chinese text patterns
lines = text_latin.split('\n')
print(f"Total lines: {len(lines)}")

# Find problematic lines (lines with SyntaxError-causing issues)
import re
problem_found = False
for i, line in enumerate(lines):
    if line.strip().startswith('lines.append('):
        # Check if it has a corrupted closing quote
        # A properly quoted string ends with ")
        stripped = line.strip()
        if stripped.endswith(')') and stripped.count('"') % 2 != 0:
            print(f"  PROBLEM line {i+1}: {stripped[:60]}...")
            problem_found = True

if not problem_found:
    print("No obvious problems found")
