# -*- coding: utf-8 -*-
"""
🦞 KD 黃金交叉回測引擎（本機 726 天日K資料）
==============================================
用 database/*_3y.csv 的 3年日K線回測
每檔股票獨立找最適 KD 參數

輸出: database/kd_params.json
"""
import os, json, sys, csv
from datetime import datetime
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE, 'database')
PARAMS_FILE = os.path.join(DB_DIR, 'kd_params.json')

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
#  KD 計算
# ══════════════════════════════════════════════

def read_csv_data(stock_id):
    """讀取 3年日K CSV"""
    fp = os.path.join(DB_DIR, f'{stock_id}_3y.csv')
    if not os.path.exists(fp):
        return None
    dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
    with open(fp, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dates.append(row['date'])
                opens.append(float(row['open']))
                highs.append(float(row.get('high', row.get('High', 0))))
                lows.append(float(row.get('low', row.get('Low', 0))))
                closes.append(float(row.get('close', row.get('Close', 0))))
                volumes.append(int(float(row.get('volume', row.get('Volume', 0)))))
            except (ValueError, KeyError):
                continue
    return {
        'dates': dates, 'opens': opens, 'highs': highs, 'lows': lows,
        'closes': closes, 'volumes': volumes
    }

def compute_kd(closes, highs, lows, rsv_days=9, k_smooth=3, d_smooth=3):
    """
    計算完整 KD 線（傳回所有 K, D 值）
    rsv_days: RSV 計算天數（預設 9）
    k_smooth: K 平滑因子（預設 3）
    d_smooth: D 平滑因子（預設 3）
    """
    n = len(closes)
    if n < rsv_days + 2:
        return [], []
    
    k_values = [50.0]
    d_values = [50.0]
    
    for i in range(n):
        # RSV
        start = max(0, i - rsv_days + 1)
        h9 = max(highs[start:i+1])
        l9 = min(lows[start:i+1])
        if h9 == l9:
            rsv = 50.0
        else:
            rsv = (closes[i] - l9) / (h9 - l9) * 100
        
        # K = (K_prev * (k_smooth-1) + RSV) / k_smooth
        k_i = (k_values[-1] * (k_smooth - 1) + rsv) / k_smooth
        # D = (D_prev * (d_smooth-1) + K) / d_smooth
        d_i = (d_values[-1] * (d_smooth - 1) + k_i) / d_smooth
        
        k_values.append(k_i)
        d_values.append(d_i)
    
    return k_values[1:], d_values[1:]


# ══════════════════════════════════════════════
#  回測核心
# ══════════════════════════════════════════════

def backtest_stock(data, k_smooth=3, d_smooth=3, rsv_days=9,
                    buy_threshold=40, sell_mode='dead_cross',
                    stop_loss=3, take_profit=5):
    """
    對一檔股票用指定參數回測
    
    回傳: { trades, wins, losses, total_profit, win_rate, score }
    """
    closes = data['closes']
    highs = data['highs']
    lows = data['lows']
    
    k_vals, d_vals = compute_kd(closes, highs, lows, rsv_days, k_smooth, d_smooth)
    if not k_vals:
        return None
    
    trades = []
    position = 0  # 0=空手, 1=持有
    entry_price = 0
    entry_idx = 0
    
    for i in range(rsv_days + 5, len(closes)):
        k = k_vals[i]
        d = d_vals[i]
        k_prev = k_vals[i-1]
        d_prev = d_vals[i-1]
        
        price = closes[i]
        
        # 金叉：K 從下往上穿 D
        golden = k_prev < d_prev and k > d
        
        # 買入：金叉 + K 值在超賣區
        if not position and golden and k < buy_threshold:
            position = 1
            entry_price = price
            entry_idx = i
            continue
        
        # 持有中檢查出場
        if position:
            profit_pct = (price / entry_price - 1) * 100
            
            # 停損
            if profit_pct <= -stop_loss:
                trades.append({
                    'entry_idx': entry_idx, 'exit_idx': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit_pct, 2),
                    'exit_reason': 'stop_loss'
                })
                position = 0
                continue
            
            # 停利
            if profit_pct >= take_profit:
                trades.append({
                    'entry_idx': entry_idx, 'exit_idx': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit_pct, 2),
                    'exit_reason': 'take_profit'
                })
                position = 0
                continue
            
            # 死叉出場
            dead = k_prev > d_prev and k < d
            if dead:
                trades.append({
                    'entry_idx': entry_idx, 'exit_idx': i,
                    'entry_price': entry_price, 'exit_price': price,
                    'profit_pct': round(profit_pct, 2),
                    'exit_reason': 'dead_cross'
                })
                position = 0
                continue
    
    # 最後一筆強制平倉
    if position:
        price = closes[-1]
        profit_pct = (price / entry_price - 1) * 100
        trades.append({
            'entry_idx': entry_idx, 'exit_idx': len(closes)-1,
            'entry_price': entry_price, 'exit_price': price,
            'profit_pct': round(profit_pct, 2),
            'exit_reason': 'forced'
        })
    
    if not trades:
        return None
    
    wins = sum(1 for t in trades if t['profit_pct'] > 0)
    losses = sum(1 for t in trades if t['profit_pct'] <= 0)
    total = wins + losses
    win_rate = wins / total * 100 if total > 0 else 0
    total_profit = sum(t['profit_pct'] for t in trades)
    avg_profit = total_profit / total if total > 0 else 0
    max_loss = min(t['profit_pct'] for t in trades) if trades else 0
    max_gain = max(t['profit_pct'] for t in trades) if trades else 0
    
    # 評分公式：勝率權重 + 總報酬權重
    score = win_rate * 0.6 + avg_profit * 5 * 0.4
    
    return {
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate, 1),
        'total_profit': round(total_profit, 2),
        'avg_profit': round(avg_profit, 2),
        'max_loss': round(max_loss, 2),
        'max_gain': round(max_gain, 2),
        'score': round(score, 1),
        'trades_sample': trades[:5],
    }


# ══════════════════════════════════════════════
#  參數搜尋
# ══════════════════════════════════════════════

def find_best_params(data):
    """搜尋最佳 KD 參數組合"""
    best = None
    best_score = -999
    
    param_grid = []
    for k_s in [2, 3, 4, 5]:
        for d_s in [2, 3, 4, 5]:
            for rsv in [5, 7, 9, 12, 14]:
                for buy_k in [30, 35, 40, 45, 50]:
                    for sl in [2, 3, 4]:
                        for tp in [3, 4, 5, 6]:
                            if k_s == d_s == 2:
                                continue
                            param_grid.append((k_s, d_s, rsv, buy_k, sl, tp))
    
    # 如果組合太多，抽樣測試
    total_combos = len(param_grid)
    step = max(1, total_combos // 200)  # 最多測 200 組
    test_grid = param_grid[::step]
    
    for params in test_grid:
        k_s, d_s, rsv, buy_k, sl, tp = params
        result = backtest_stock(data, k_s, d_s, rsv, buy_k, 'dead_cross', sl, tp)
        if result and result['total_trades'] >= 5:
            s = result['score']
            if s > best_score:
                best_score = s
                best = {
                    'k_period': k_s, 'd_period': d_s, 'rsv_days': rsv,
                    'buy_threshold': buy_k,
                    'stop_loss': sl, 'take_profit': tp,
                    **result
                }
    
    return best


# ══════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════

def run_all_backtest():
    """對所有持股跑 KD 回測"""
    print('=' * 70)
    print('  🦞 KD 黃金交叉回測（本機 3 年日K資料）')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 70)
    
    results = {}
    
    for sid, sname in STOCKS:
        print(f'\n  📊 {sid} {sname}...', end=' ', flush=True)
        
        data = read_csv_data(sid)
        if not data or len(data['closes']) < 100:
            print('❌ 資料不足')
            continue
        
        best = find_best_params(data)
        if best:
            results[sid] = best
            print(f'✅ K{best["k_period"]}/D{best["d_period"]}/RSV{best["rsv_days"]}  '
                  f'買K<{best["buy_threshold"]} 停損{best["stop_loss"]}%停利{best["take_profit"]}%  '
                  f'勝率{best["win_rate"]}% 交易{best["total_trades"]}次')
        else:
            print('❌ 回測失敗')
    
    if not results:
        print('\n  ❌ 沒有任何股票回測成功')
        return
    
    # 儲存
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'data_source': 'database/*_3y.csv (3年日K)',
        'stocks': results,
    }
    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print('=' * 70)
    print(f'  ✅ 完成！{len(results)} 檔股票參數已儲存')
    print(f'  📁 {PARAMS_FILE}')
    print('=' * 70)
    
    return results


def get_kd_params(stock_id):
    """晨報讀取某檔股票的 KD 參數"""
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('stocks', {}).get(stock_id, {
                'k_period': 3, 'd_period': 3, 'rsv_days': 9,
                'buy_threshold': 40, 'stop_loss': 3, 'take_profit': 5
            })
        except:
            pass
    return {'k_period': 3, 'd_period': 3, 'rsv_days': 9,
            'buy_threshold': 40, 'stop_loss': 3, 'take_profit': 5}


if __name__ == '__main__':
    run_all_backtest()
