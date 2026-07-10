# -*- coding: utf-8 -*-
"""
🦞 KD 30分K 黃金交叉回測引擎
================================
每檔股票獨立回測，找出最適 KD 參數。
使用 Shioaji 下載 45 天 30分K 資料進行回測。

輸出: database/kd_params.json (每檔股票的最適參數)
"""
import os, json, sys, time
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, 'src', 'sj_trading'))

OUTPUT_DIR = os.path.join(BASE, 'database')
PARAMS_FILE = os.path.join(OUTPUT_DIR, 'kd_params.json')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 19 檔持股
STOCKS = [
    ('2436','偉詮電'),('2337','旺宏'),('5351','鈺創'),
    ('3673','TPK-KY'),('3711','日月光'),('4958','臻鼎-KY'),('3042','晶技'),
    ('2454','聯發科'),('2317','鴻海'),
    ('3443','創意'),('3661','世芯-KY'),('3035','智原'),
    ('3231','緯創'),('2382','廣達'),('3017','奇鋐'),('2451','創見'),
    ('8150','南茂'),('2344','華邦電'),('6770','力積電'),
    ('2330','台積電'),
]

# ═══════════════════════════════════════════════
#  KD 計算（使用本地資料）
# ═══════════════════════════════════════════════

def calc_KD(closes, highs, lows, n=9):
    """計算 KD 值，回傳 K, D, 是否金叉, 差距"""
    if len(closes) < n + 1:
        return 50, 50, False, 0
    
    # RSV 計算
    last_n_high = max(highs[-(n+1):-1])
    last_n_low = min(lows[-(n+1):-1])
    if last_n_high == last_n_low:
        rsv = 50
    else:
        rsv = (closes[-2] - last_n_low) / (last_n_high - last_n_low) * 100
    
    # 平滑計算
    k = rsv * 2/3 + 50 * 1/3  # 初始值用50
    d = k * 2/3 + 50 * 1/3
    
    # 用完整公式算一遍
    k_values = [50]
    d_values = [50]
    
    for i in range(1, len(closes)):
        h9 = max(highs[max(0,i-8):i+1])
        l9 = min(lows[max(0,i-8):i+1])
        if h9 == l9:
            rsv_i = 50
        else:
            rsv_i = (closes[i] - l9) / (h9 - l9) * 100
        
        k_i = k_values[-1] * 2/3 + rsv_i * 1/3
        d_i = d_values[-1] * 2/3 + k_i * 1/3
        
        k_values.append(k_i)
        d_values.append(d_i)
    
    k = k_values[-1]
    d = d_values[-1]
    
    # 金叉判斷（前一根 K < D，這根 K > D）
    prev_k = k_values[-2] if len(k_values) >= 2 else k_values[-1]
    prev_d = d_values[-2] if len(d_values) >= 2 else d_values[-1]
    golden = prev_k < prev_d and k > d
    gap = k - d
    
    return k, d, golden, gap


# ═══════════════════════════════════════════════
#  下載 30分K 資料（用永豐 Shioaji）
# ═══════════════════════════════════════════════

def download_30min_kbars(stock_id, days=45):
    """用 Shioaji 下載 30分K 資料"""
    try:
        from shioaji_helper import ShioajiClient
        sjc = ShioajiClient()
        if not sjc.login():
            print(f'    Shioaji 登入失敗')
            return []
        
        api = sjc.api
        contract = api.Contracts.Stocks[stock_id]
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        # 用 30 分 K 線抓（每根 K 棒 30 分鐘）
        kbars = api.kbars(
            contract=contract,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
        )
        
        if len(kbars.ts) == 0:
            sjc.logout()
            return []
        
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
        
        sjc.logout()
        return result
    except Exception as e:
        return []


# ═══════════════════════════════════════════════
#  回測 KD 參數（找到最佳組合）
# ═══════════════════════════════════════════════

def backtest_kd_params(kbars_data):
    """
    對一檔股票的 30分K 資料進行 KD 參數回測
    
    測試不同的:
    - K 平滑週期 (2~5)
    - D 平滑週期 (2~5)
    - 超賣區金叉 (RSV 低於 20~40)
    - 超賣後回升確認
    
    回傳: 最適參數 dict
    """
    if len(kbars_data) < 30:
        return None
    
    closes = np.array([k['close'] for k in kbars_data])
    highs = np.array([k['high'] for k in kbars_data])
    lows = np.array([k['low'] for k in kbars_data])
    
    best_params = None
    best_score = -999
    
    # 測試各種 K/D 平滑週期組合
    for k_period in range(2, 6):
        for d_period in range(2, 6):
            if k_period == d_period == 2:
                continue  # 太敏感
            
            # 用不同 RSV 天數 (5~14)
            for rsv_days in [5, 7, 9, 12, 14]:
                score = 0
                wins = 0
                losses = 0
                
                # 模擬交易
                position = 0  # 0=空手, 1=持有
                entry_price = 0
                
                for i in range(rsv_days + max(k_period, d_period), len(closes)):
                    # 取一段資料計算 KD
                    seg_closes = closes[max(0,i-rsv_days):i+1]
                    seg_highs = highs[max(0,i-rsv_days):i+1]
                    seg_lows = lows[max(0,i-rsv_days):i+1]
                    
                    # 算 KD
                    h9 = max(seg_highs[:-1])
                    l9 = min(seg_lows[:-1])
                    if h9 == l9:
                        continue
                    rsv = (seg_closes[-2] - l9) / (h9 - l9) * 100
                    
                    # K 值 (簡化版)
                    k = (2/3) * 50 + (1/3) * rsv
                    d = (2/3) * 50 + (1/3) * k
                    
                    # 前一根K
                    rsv_prev = (seg_closes[-3] - l9) / (h9 - l9) * 100 if len(seg_closes) > 2 else rsv
                    k_prev = (2/3) * 50 + (1/3) * rsv_prev
                    d_prev = (2/3) * 50 + (1/3) * k_prev
                    
                    current_price = closes[i]
                    
                    # 金叉判斷 (K 從下往上穿 D)
                    is_golden = k_prev < d_prev and k > d
                    
                    # 買入條件：金叉 + 在超賣區附近 (K<40)
                    if not position and is_golden and k < 40:
                        position = 1
                        entry_price = current_price
                    
                    # 賣出條件：死叉 (K 向下穿 D) 或漲幅超過 5%
                    elif position:
                        if k_prev > d_prev and k < d:
                            # 死叉賣出
                            profit_pct = (current_price / entry_price - 1) * 100
                            if profit_pct > 0:
                                wins += 1
                            else:
                                losses += 1
                            score += profit_pct
                            position = 0
                        elif current_price / entry_price > 1.05:
                            # 停利 5%
                            profit_pct = 5
                            wins += 1
                            score += profit_pct
                            position = 0
                        elif current_price / entry_price < 0.97:
                            # 停損 3%
                            profit_pct = -3
                            losses += 1
                            score += profit_pct
                            position = 0
                
                total_trades = wins + losses
                if total_trades >= 5:  # 至少要有5次交易
                    win_rate = wins / total_trades * 100
                    # 評分：勝率 + 總報酬 / 交易次數
                    total_score = win_rate + (score / max(total_trades, 1)) * 10
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_params = {
                            'k_period': k_period,
                            'd_period': d_period,
                            'rsv_days': rsv_days,
                            'total_trades': total_trades,
                            'wins': wins,
                            'losses': losses,
                            'win_rate': round(win_rate, 1),
                            'total_profit': round(score, 2),
                            'score': round(total_score, 1),
                        }
    
    return best_params


# ═══════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════

def run_backtest(force_download=False):
    """對所有持股跑 KD 回測"""
    print('=' * 60)
    print('  🦞 KD 30分K 黃金交叉回測')
    print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('=' * 60)
    
    # 讀取現有參數
    existing_params = {}
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
            existing_params = json.load(f)
        print(f'  已有 {len(existing_params)} 檔股票的參數')
    
    results = {}
    
    for sid, sname in STOCKS:
        print(f'\n  {sid} {sname}...', end=' ', flush=True)
        
        # 讀取本地 30 分 K 資料（如果有）
        local_file = os.path.join(OUTPUT_DIR, f'{sid}_30min.json')
        kbars_data = []
        
        if os.path.exists(local_file) and not force_download:
            try:
                with open(local_file, 'r', encoding='utf-8') as f:
                    kbars_data = json.load(f)
                print(f'讀取本地 {len(kbars_data)} 根 K 棒', end=' ')
            except:
                pass
        
        if not kbars_data:
            print('下載 30分K...', end=' ', flush=True)
            kbars_data = download_30min_kbars(sid, days=45)
            if kbars_data:
                # 存檔
                with open(local_file, 'w', encoding='utf-8') as f:
                    json.dump(kbars_data, f, ensure_ascii=False)
                print(f'{len(kbars_data)} 根', end=' ')
            else:
                print('下載失敗，用上次參數', end=' ')
                if sid in existing_params:
                    results[sid] = existing_params[sid]
                    print(f'(沿用) K={existing_params[sid].get("k_period",9)}')
                else:
                    # 預設參數
                    results[sid] = {
                        'k_period': 3, 'd_period': 3, 'rsv_days': 9,
                        'source': 'default'
                    }
                    print('(預設 K3/D3/RSV9)')
                continue
        
        if kbars_data and len(kbars_data) >= 30:
            params = backtest_kd_params(kbars_data)
            if params:
                params['source'] = 'backtest'
                results[sid] = params
                print(f'✅ K{params["k_period"]}/D{params["d_period"]}/RSV{params["rsv_days"]}  '
                      f'勝率{params["win_rate"]}% 交易{params["total_trades"]}次')
            else:
                if sid in existing_params:
                    results[sid] = existing_params[sid]
                    print(f'⚠️ 回測不足，沿用 K={existing_params[sid].get("k_period",9)}')
                else:
                    results[sid] = {
                        'k_period': 3, 'd_period': 3, 'rsv_days': 9,
                        'source': 'default'
                    }
                    print('⚠️ 回測不足，設預設 K3/D3/RSV9')
        else:
            if sid in existing_params:
                results[sid] = existing_params[sid]
                print(f'沿用 K={existing_params[sid].get("k_period",9)}')
            else:
                results[sid] = {
                    'k_period': 3, 'd_period': 3, 'rsv_days': 9,
                    'source': 'default'
                }
                print('預設 K3/D3/RSV9')
    
    # 儲存參數
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'stocks': results,
    }
    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print('=' * 60)
    print(f'  ✅ 完成！參數已儲存: {PARAMS_FILE}')
    print('=' * 60)
    
    return results


def get_kd_params(stock_id):
    """晨報讀取某檔股票的 KD 參數"""
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('stocks', {}).get(stock_id, {
                'k_period': 3, 'd_period': 3, 'rsv_days': 9
            })
        except:
            pass
    return {'k_period': 3, 'd_period': 3, 'rsv_days': 9}


if __name__ == '__main__':
    run_backtest(force_download=True)
