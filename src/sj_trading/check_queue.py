import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
base = os.path.dirname(os.path.abspath(__file__))
qpath = os.path.join(base, '..', '..', 'lobster_alert_queue.json')
if os.path.exists(qpath):
    with open(qpath, 'r', encoding='utf-8') as f:
        q = json.load(f)
    wq = [x for x in q if x.get('sid') == '2436']
    if wq:
        for x in wq[-5:]:
            print(x['msg'])
            print()
    else:
        print('伟诠电尚无预警')
else:
    print('queue 尚未产生')
