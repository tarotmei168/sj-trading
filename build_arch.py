#!/usr/bin/env python3
import markdown, os

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, 'architecture_master.md'), 'r', encoding='utf-8') as f:
    md = f.read()

html_body = markdown.markdown(md, extensions=['tables', 'fenced_code'])

style = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>系统架構 — 小龍蝦早報</title>
<style>
body{background:#121212;color:#e0e0e0;font-family:-apple-system,"Microsoft JhengHei",Arial,sans-serif;font-size:18px;padding:16px;line-height:1.6}
h1{color:#ffbe76;border-bottom:2px solid #ffbe76;padding-bottom:8px}
h2{color:#ff6b6b;margin-top:24px;border-bottom:1px solid #333;padding-bottom:4px}
h3{color:#ffbe76;margin-top:20px}
code{background:#2a2a2a;padding:2px 6px;border-radius:4px;color:#7ec8e3}
table{width:100%;border-collapse:collapse;margin:10px 0}
th{background:#2d2d2d;color:#ffbe76;padding:8px 6px;text-align:left;border-bottom:2px solid #333}
td{padding:8px 6px;border-bottom:1px solid #333}
a{color:#1e90ff}
</style>
</head>
<body>
'''

full_html = style + html_body + '</body></html>'

out = os.path.join(BASE, 'web', 'architecture.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(full_html)
print('OK:', out)
