# -*- coding: utf-8 -*-
"""
🦞 KD 30分K 黃金交叉回測引擎
==============================================
用 Shioaji 永豐 API 下載 45 天 30分K 資料
每檔股票獨立回測，找出最適 KD 參數

輸出: database/kd_params_30min.json
"""
import os, json, sys, csv, time
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE, 'database')
PARAMS_FILE = os.path.join(DB_DIR, 'kd_params_30min.json')

# 20 檔持股
STOCKS = [
    ('2436','偉詮電'),('2337','旺宏'),('5351','鈺創'),
    ('3673','TPK-KY'),('3711','日月光'),('4958','臻鼎-KY'),('3042','晶技'),
    ('2454','聯發科'),('2317','鴻海'),
    ('3443','創意'),('3661','世芯-KY'),('3035','智原'),
    ('3231','緯創'),('2382','廣達'),('3017','奇鋐'),('2451','創見'),
    ('8150','南茂'),('2344','華邦電'),('6770','力積電'),
    ('2330','台積電'),
]

# ══════════════════════════════════════════════
#  下載 30分K（Shioaji 永豐 API）
# ══════════════════════════════════════════════

def download_30min_kbars(stock_id, days=45):
    """用 ShioajiClient 下載 30分K 資料"""
    import pandas as pd
    
    try:
        sys.path.insert(0, os.path.join(BASE, 'src', 'sj_trading'))
        from shioaji_helper import ShioajiClient
        
        sjc = ShioajiClient()
        if not sjc.login():
            print('登入失敗', end='')
            return None
        
        api = sjc.api
        
        # 找合約
        contract = None
        for c in api.Contracts.Stocks:
            if c.code == stock_id:
                contract = c
                break
        
        if not contract:
            sjc.logout()
            print('合約不存在', end='')
            return None
        
        # 下載 K 線
        end = datetime.now()
        start = end - timedelta(days=days)
        
        kbars = api.kbars(
            contract=contract,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
        )
        
        sjc.logout()
        
        if len(kbars.ts) == 0:
            return None
        
        result = []
        for i in range(len(kbars.ts)):
            result.append({
                'datetime': pd.to_datetime(kbars.ts[i]).strftime('%Y-%m-%d %H:%M'),
                'open': float(kbars.Open[i]),
                'high': float(kbars.High[i]),
                'low': float(kbars.Low[i]),
                'close': float(kbars.Close[i]),
                'volume': int(kbars.Volume[i]),
            })
        
        # 存到本機
        local_file = os.path.join(DB_DIR, f'{stock_id}_30min.json')
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
        
        return result
    except Exception as e:
        print(f' 錯誤:{str(e)[:30]}', end='')
        return None


def load_local_30min(stock_id):
    """讀取本機已存的 30分K 資料"""
    local_file = os.path.join(DB_DIR, f'{stock_id}_30min.json')
    if os.path.exists(local_file):
        with open(local_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


# ══════════════════════════════════════════════
#  30分K KD 計算
# ══════════════════════════════════════════════

def compute_kd_30min(kbars, rsv_days=9, k_period=3, d_period=3):
    """對 30分K 資料計算完整 KD 線"""
    n = len(kbars)
    if n < rsv_days + 5:
        return [], []
    
    closes = np.array([k['close'] for k in kbars])
    highs = np.array([k['high'] for k in kbars])
    lows = np.array([k['low'] for k in kbars])
    
    k_vals = [50.0]
    d_vals = [50.0]
    
    for i in range(n):
        start = max(0, i - rsv_days + 1)
        h9 = max(highs[start:i+1])
        l9 = min(lows[start:i+1])
        if h9 == l9:
            rsv = 50.0
        else:
            rsv = (closes[i] - l9) / (h9 - l9) * 100
        
        k_i = (k_vals[-1] * (k_period - 1) + rsv) / k_period
        d_i = (d_vals[-1] * (d_period - 1) + k_i) / d_period
        
        k_vals.append(k_i)
        d_vals.append(d_i)
    
    return k_vals[1:], d_vals[1:]


# ══════════════════════════════════════════════
#  回測核心（30分K）
# ══════════════════════════════════════════════

def backtest_30min(kbars, k_period=3, d_period=3, rsv_days=9,
                   buy_k=40, stop_loss=3, take_profit=5):
    """用30分K資料回測 KD 參數"""
    if len(kbars) < 50:
        return None
    
    closes = np.array([k['close'] for k in kbars])
    highs = np.array([k['high'] for k in kbars])
    lows = np.array([k['low'] for k in kbars])
    
    k_vals, d_vals = compute_kd_30min(kbars, rsv_days, k_period, d_period)
    if len(k_vals) == 0:
        return None
    
    trades = []
    position = 0
    entry_price = 0
    entry_idx = 0
    
    for i in range(rsv_days + 5, len(closes)):
        k = k_vals[i]
        d = d_vals[i]
        k_prev = k_vals[i-1]
        d_prev = d_vals[i-1]
        price = closes[i]
        dt = kbars[i]['datetime']
        
        # 金叉：K 從下往上穿 D
        golden = k_prev < d_prev and k > d
        
        if not position and golden and k < buy_k:
            position = 1
            entry_price = price
            entry_idx = i
            continue
        
        if position:
            profit = (price / entry_price - 1) * 100
            
            if profit <= -stop_loss:
                trades.append({'entry': entry_idx, 'exit': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit, 2), 'reason': 'stop_loss',
                    'entry_time': kbars[entry_idx]['datetime'], 'exit_time': dt})
                position = 0
                continue
            
            if profit >= take_profit:
                trades.append({'entry': entry_idx, 'exit': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit, 2), 'reason': 'take_profit',
                    'entry_time': kbars[entry_idx]['datetime'], 'exit_time': dt})
                position = 0
                continue
            
            # 死叉
            dead = k_prev > d_prev and k < d
            if dead:
                trades.append({'entry': entry_idx, 'exit': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit, 2), 'reason': 'dead_cross',
                    'entry_time': kbars[entry_idx]['datetime'], 'exit_time': dt})
                position = 0
                continue
    
    if position:
        price = closes[-1]
        profit = (price / entry_price - 1) * 100
        trades.append({'entry': entry_idx, 'exit': len(closes)-1,
            'entry_price': entry_price, 'exit_price': price,
            'profit_pct': round(profit, 2), 'reason': 'forced',
            'entry_time': kbars[entry_idx]['datetime'], 'exit_time': kbars[-1]['datetime']})
    
    if not trades:
        return None
    
    wins = sum(1 for t in trades if t['profit_pct'] > 0)
    losses = sum(1 for t in trades if t['profit_pct'] <= 0)
    total = wins + losses
    win_rate = wins / total * 100 if total > 0 else 0
    total_profit = sum(t['profit_pct'] for t in trades)
    avg_profit = total_profit / total if total > 0 else 0
    
    score = win_rate * 0.6 + avg_profit * 10 * 0.4
    
    return {
        'total_trades': total, 'wins': wins, 'losses': losses,
        'win_rate': round(win_rate, 1),
        'total_profit': round(total_profit, 2),
        'avg_profit': round(avg_profit, 2),
        'score': round(score, 1),
    }


# ══════════════════════════════════════════════
#  搜尋最佳參數
# ══════════════════════════════════════════════

def find_best_params_30min(kbars):
    """搜尋 30分K 最佳 KD 參數"""
    if not kbars or len(kbars) < 50:
        return None
    
    best = None
    best_score = -999
    
    # 參數組合（取樣測試，最多 300 組）
    params_list = []
    for kp in [2, 3, 4, 5]:
        for dp in [2, 3, 4, 5]:
            for rsv in [5, 7, 9, 12, 14]:
                for bk in [30, 35, 40, 45, 50]:
                    for sl in [2, 3, 4]:
                        for tp in [3, 4, 5]:
                            if kp == dp == 2:
                                continue
                            params_list.append((kp, dp, rsv, bk, sl, tp))
    
    # 抽樣，最多測 200 組
    step = max(1, len(params_list) // 200)
    test_list = params_list[::step]
    
    for p in test_list:
        kp, dp, rsv, bk, sl, tp = p
        result = backtest_30min(kbars, kp, dp, rsv, bk, sl, tp)
        if result and result['total_trades'] >= 5:
            if result['score'] > best_score:
                best_score = result['score']
                best = {
                    'k_period': kp, 'd_period': dp, 'rsv_days': rsv,
                    'buy_k': bk, 'stop_loss': sl, 'take_profit': tp,
                    **result
                }
    
    return best


# ══════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════

def run_all():
    print('=' * 70)
    print('  🦞 KD 30分K 黃金交叉回測')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('  資料源: Shioaji 永豐 API (45天 30分K)')
    print('=' * 70)
    
    results = {}
    
    for sid, sname in STOCKS:
        print(f'\n  {sid} {sname}...', end=' ', flush=True)
        
        # 先看本機有沒有
        kbars = load_local_30min(sid)
        
        if kbars:
            print(f'本機 {len(kbars)} 根', end=' ', flush=True)
        else:
            print('下載中...', end=' ', flush=True)
            kbars = download_30min_kbars(sid, days=45)
            if kbars:
                print(f'下載 {len(kbars)} 根', end=' ', flush=True)
            else:
                print('❌ 下載失敗')
                continue
        
        # 回測
        best = find_best_params_30min(kbars)
        if best:
            results[sid] = best
            print(f'✅ K{best["k_period"]}/D{best["d_period"]}/RSV{best["rsv_days"]}  '
                  f'K<{best["buy_k"]} 停損{best["stop_loss"]}% 停利{best["take_profit"]}%  '
                  f'勝率{best["win_rate"]}% 交易{best["total_trades"]}次')
        else:
            print('❌ 回測不足')
    
    if not results:
        print('\n  ❌ 無回測結果')
        return
    
    # 儲存
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'data_source': 'Shioaji 永豐 API (45天 30分K)',
        'stocks': results,
    }
    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print('=' * 70)
    print(f'  ✅ {len(results)} 檔完成！參數已存: {PARAMS_FILE}')
    print('=' * 70)


def get_kd_params(stock_id):
    """晨報讀取 30分K 的 KD 參數"""
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('stocks', {}).get(stock_id, {
                'k_period': 3, 'd_period': 3, 'rsv_days': 9,
                'buy_k': 40, 'stop_loss': 3, 'take_profit': 5
            })
        except:
            pass
    return {'k_period': 3, 'd_period': 3, 'rsv_days': 9,
            'buy_k': 40, 'stop_loss': 3, 'take_profit': 5}


if __name__ == '__main__':
    run_all()
