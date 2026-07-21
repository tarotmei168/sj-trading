from datetime import datetime, timedelta
import calendar

def nth_weekday_date(year, month, weekday, nth=1):
    """找出某月第n個星期幾的日期。weekday: 0=Mon"""
    d = datetime(year, month, 1)
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first = d + timedelta(days=days_ahead)
    return first + timedelta(weeks=nth-1)

today = datetime.now().replace(hour=0,minute=0,second=0)
cutoff = today + timedelta(days=14)

events = []
for i in range(3):
    m = today.month + i
    y = today.year
    if m > 12:
        m -= 12
        y += 1

    # 非農: 第1個星期五
    nfp = nth_weekday_date(y, m, 4, 1)
    if today <= nfp <= cutoff:
        events.append((nfp.strftime('%Y-%m-%d'), 'US Nonfarm Payrolls (NFP)'))

    # CPI: 第2個星期三
    cpi = nth_weekday_date(y, m, 2, 2)
    if today <= cpi <= cutoff:
        events.append((cpi.strftime('%Y-%m-%d'), 'US CPI'))

    # PPI: 第2個星期四
    ppi = nth_weekday_date(y, m, 3, 2)
    if today <= ppi <= cutoff:
        events.append((ppi.strftime('%Y-%m-%d'), 'US PPI'))

    # ISM製造業PMI: 第1個工作日
    first_day = datetime(y, m, 1)
    ism_m = first_day
    while ism_m.weekday() >= 5:
        ism_m += timedelta(days=1)
    if today <= ism_m <= cutoff:
        events.append((ism_m.strftime('%Y-%m-%d'), 'US ISM Manufacturing PMI'))

    # ISM服務業PMI: 通常第3個工作日
    ism_s = ism_m + timedelta(days=2)
    while ism_s.weekday() >= 5:
        ism_s += timedelta(days=1)
    if today <= ism_s <= cutoff:
        events.append((ism_s.strftime('%Y-%m-%d'), 'US ISM Services PMI'))

print(f'Today: {today.strftime("%Y-%m-%d")} -> {cutoff.strftime("%Y-%m-%d")}')
print('Events:')
for d,n in sorted(events, key=lambda x: x[0]):
    print(f'  {d}: {n}')
