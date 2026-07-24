# -*- coding: utf-8 -*-
"""Replace linkage wall in daily_web_report.py"""
import pathlib

def main():
    p = pathlib.Path(r'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\daily_web_report.py')
    text = p.read_text(encoding='utf-8')
    
    Q = chr(39)
    DQ = Q + Q
    NL = chr(10)
    EM = chr(8212)
    
    # Find old block using Chinese chars via chr()
    # 台美聯動牆（即時從
    s = text.find(chr(21488)+chr(32654)+chr(32879)+chr(21205)+chr(29254))
    # 聯動模組未啟用
    e = text.find(chr(32879)+chr(21205)+chr(27169)+chr(32068)+chr(26410)+chr(29992)+chr(29987), s)
    e = text.find(chr(10), e) + 1
    
    print(f'Old block: {s} to {e}')
    if s < 0 or e < 0:
        print('ERROR: Cannot find old block')
        return False
    
    # Build new linkage wall code
    nc = ''
    nc += '    # ' + EM*2 + ' 台美聯動牆（用 LINKAGE_40 完整對照，篩選 >=2.5% 或 <=-5% 才顯示）' + EM*2 + NL
    nc += '    linkage_rows = ' + DQ + NL
    nc += '    if HAVE_WEATHER:' + NL
    nc += '        try:' + NL
    nc += '            from global_weather import get_us_stock_change as _gusc' + NL
    nc += '            _sector_rows = {}' + NL
    nc += '            _all_us_symbols = {}' + NL
    nc += '            for _k, _v in LINKAGE_40.items():' + NL
    nc += '                _sector = _v.get(' + Q + 'sector' + Q + ', ' + Q + '其他' + Q + ')' + NL
    nc += '                for _us_sym, _us_name in _v.get(' + Q + 'us' + Q + ', []):' + NL
    nc += '                    _tw_codes = _v.get(' + Q + 'tw' + Q + ', [])' + NL
    nc += '                    _tw_str = ' + Q + ', ' + Q + '.join([f' + Q + '{c}({n})' + Q + ' for c, n in _tw_codes]) if _tw_codes else ' + DQ + NL
    nc += '                    if _us_sym not in _all_us_symbols:' + NL
    nc += '                        _all_us_symbols[_us_sym] = []' + NL
    nc += '                    _all_us_symbols[_us_sym].append((_sector, _us_name, _tw_str, _v.get(' + Q + 'desc' + Q + ', ' + DQ + ')))' + NL
    nc += '            for _sym, _entries in _all_us_symbols.items():' + NL
    nc += '                try:' + NL
    nc += '                    _chg, _close = _gusc(_sym)' + NL
    nc += '                except:' + NL
    nc += '                    continue' + NL
    nc += '                if _chg is None:' + NL
    nc += '                    continue' + NL
    nc += '                if not (_chg >= 2.5 or _chg <= -5):' + NL
    nc += '                    continue' + NL
    nc += '                _abs = abs(_chg)' + NL
    nc += '                if _abs >= 5:' + NL
    nc += '                    _badge = ' + Q + chr(128308)*2 + Q + ' if _chg < 0 else ' + Q + chr(128994)*2 + Q + NL
    nc += '                    _bc = ' + Q + 'badge-red' + Q + ' if _chg < 0 else ' + Q + 'badge-blue' + Q + NL
    nc += '                elif _abs >= 2.5:' + NL
    nc += '                    _badge = ' + Q + chr(128308) + Q + ' if _chg < 0 else ' + Q + chr(128994) + Q + NL
    nc += '                    _bc = ' + Q + 'badge-red' + Q + ' if _chg < 0 else ' + Q + 'badge-blue' + Q + NL
    nc += '                else:' + NL
    nc += '                    _badge = ' + Q + chr(128315) + Q + ' if _chg < 0 else ' + Q + chr(128994) + Q + NL
    nc += '                    _bc = ' + Q + 'badge-orange' + Q + ' if _chg < 0 else ' + Q + 'badge-blue' + Q + NL
    nc += '                _chg_str = f' + Q + '{_chg:+.2f}%' + Q + NL
    nc += '                _sector = _entries[0][0]' + NL
    nc += '                _us_name = _entries[0][1]' + NL
    nc += '                _tw_str = _entries[0][2]' + NL
    nc += '                _desc = _entries[0][3]' + NL
    nc += '                _line = (' + NL
    nc += '                    ' + Q + '<div class=link-row>' + Q + ',' + NL
    nc += '                    ' + Q + '<span class=badge {_bc}>{_badge}</span> ' + Q + ',' + NL
    nc += '                    ' + Q + '<b>{_sym} {_us_name}</b> {_chg_str}' + Q + ',' + NL
    nc += '                    (' + Q + ' -> <span style=color:#4a9eff>{_tw_str}</span>' + Q + ' if _tw_str else ' + DQ + '),' + NL
    nc += '                    ' + Q + ' <span style=color:#888;font-size:20px>({_desc})</span>' + Q + ',' + NL
    nc += '                    ' + Q + '</div>\\n' + Q + ',' + NL
    nc += '                )' + NL
    nc += '                if _sector not in _sector_rows:' + NL
    nc += '                    _sector_rows[_sector] = ' + DQ + NL
    nc += '                _sector_rows[_sector] += _line' + NL
    nc += '            for _sector, _lines in _sector_rows.items():' + NL
    nc += '                if _lines:' + NL
    nc += '                    linkage_rows += (' + NL
    nc += '                        ' + Q + '<div style=margin-bottom:12px>' + Q + ',' + NL
    # Use var(--primary-gold) via chr to avoid any issues
    nc += '                        ' + Q + '<div style=color:var(' + chr(45)*2 + 'primary-gold);font-size:20px;font-weight:bold;margin-bottom:6px>' + chr(128204) + ' {_sector}</div>' + Q + ',' + NL
    nc += '                        f' + Q + '{_lines}' + Q + ',' + NL
    nc += '                        ' + Q + '</div>' + Q + ',' + NL
    nc += '                    )' + NL
    nc += '            if not linkage_rows:' + NL
    nc += '                linkage_rows = ' + Q + '<div class=link-row>' + chr(9989) + ' 本日無劇烈波動（無美股漲>=2.5%或跌<=-5%）</div>' + Q + NL
    nc += '        except Exception as _le:' + NL
    nc += '            linkage_rows = f' + Q + '<div class=link-row>' + chr(9888) + chr(65039) + ' 聯動牆讀取失敗: {_le}</div>' + Q + NL
    nc += '    else:' + NL
    nc += '        linkage_rows = ' + Q + '<div class=link-row>' + chr(9888) + chr(65039) + ' 聯動模組未啟用</div>' + Q + NL
    
    new_text = text[:s] + nc + text[e:]
    
    # Verify old block is gone
    check_str = chr(21488)+chr(32654)+chr(32879)+chr(21205)+chr(29254)+chr(65288)+chr(21363)+chr(26178)+chr(24478)
    if check_str in new_text:
        print('ERROR: Old block still present!')
        return False
    
    p.write_text(new_text, encoding='utf-8')
    print(f'SUCCESS! File size: {len(new_text)} chars')
    return True

if __name__ == '__main__':
    main()