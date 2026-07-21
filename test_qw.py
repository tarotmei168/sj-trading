from datetime import datetime, timedelta

today = datetime.now()
print('Today:', today.strftime('%Y-%m-%d %a'))

# 計算 3,6,9,12 月的第 3 個星期五
for m in [3, 6, 9, 12]:
    d = datetime(today.year, m, 1)
    days_ahead = 4 - d.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_fri = d + timedelta(days=days_ahead)
    third_fri = first_fri + timedelta(weeks=2)
    print(f'  {m}月第3個星期五: {third_fri.strftime("%Y-%m-%d %a")}')

cutoff = today + timedelta(days=14)
print(f'Cutoff: {cutoff.strftime("%Y-%m-%d %a")}')
for m in [3, 6, 9, 12]:
    d = datetime(today.year, m, 1)
    days_ahead = 4 - d.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_fri = d + timedelta(days=days_ahead)
    third_fri = first_fri + timedelta(weeks=2)
    if today <= third_fri <= cutoff:
        print(f'  ⚠️ 四物日在範圍內: {third_fri.strftime("%Y-%m-%d %a")}')
