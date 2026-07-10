# -*- coding: utf-8 -*-
import json
with open(r'C:\Users\User\.openclaw\workspace\sj-trading\output\trust_scan_latest.json') as f:
    data = json.load(f)
print('更新時間:', data['update_time'])
print()

watch = ['2436','2337','5351','3673','3711','4958','3042','2454','2317',
         '3443','3661','3035','3231','2382','3017','2451','8150','2344','6770','2330']

print('持股投信連買狀況：')
print('代號  名稱      連買  累計買超')
for h in data['trust_top40']:
    if h['sid'] in watch:
        print(f'{h["sid"]} {h["name"]:<8s} {h["days"]}天 {h["total_trust"]:>10,d}')

print()
print('全市場投信買超 TOP 5：')
for h in data['trust_top40'][:5]:
    print(f'{h["sid"]} {h["name"]:<8s} {h["days"]}天 {h["total_trust"]:>10,d}')
