import sys; sys.path.insert(0, 'src/sj_trading')
from us_tw_mapping_matrix import LINKAGE_40
for gid, info in LINKAGE_40.items():
    us_list = [(s,n) for s,n in info['us']]
    tw_list = [(s,n) for s,n in info['tw']]
    print(f"[{gid}] {info['sector']}: {info['desc']}")
    print(f"  US: {us_list}")
    print(f"  TW: {tw_list}")
    print()
