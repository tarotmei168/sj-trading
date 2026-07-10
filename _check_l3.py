import sys; sys.path.insert(0, 'src')
from sj_trading.lobster_pipeline import Layer3_BlackHorse
l3 = Layer3_BlackHorse()
data = l3.scan()
print('Total: %d' % len(data))
for item in data:
    print('  %s %s - %s' % (item['sid'], item['name'].ljust(6), item['theme'].ljust(10)))
