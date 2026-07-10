# -*- coding: utf-8 -*-
"""
個股最佳化參數回测系統
======================
找出每檔股票「歷史勝率最高」的參數組合：
- KD 週期 (K/D 天數)
- 黃金交叉買入的K值門檻
- 量價過濾（成交量放大條件）
- RSI輔助過濾
- 30分K / 日K 不同週期

輸出：每檔股票的最佳參數組合 + 對應勝率/報酬
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from ticker_fix import get_yfinance_ticker, try_alternate_ticker

NOW = datetime.now()

def calc_kd(close, high, low, k_period=9, d_period=3):
    """計算KD值，可自訂週期"""
    n = len(close)
    k = np.zeros(n); d = np.zeros(n)
    k[0] = 50; d[0] = 50
    for i in range(1, n):
        ps = max(0, i - k_period + 1)
        hh = np.max(high[ps:i+1])
        ll = np.min(low[ps:i+1])
        rsv = (close[i] - ll) / (hh - ll) * 100.0 if hh - ll > 0 else 50
        k[i] = (d_period - 1) / d_period * k[i-1] + (1/d_period) * rsv
        d[i] = (d_period - 1) / d_period * d[i-1] + (1/d_period) * k[i]
    return k, d

def calc_rsi(close, period=14):
    n = len(close)
    rsi = np.full(n, 50.0)
    diff = np.diff(close)
    gains = diff[:period][diff[:period] > 0].sum() / period
    losses = abs(diff[:period][diff[:period] < 0]).sum() / period
    rsi[period] = 100.0 - (100.0 / (1.0 + gains/losses)) if losses != 0 else 100.0
    for i in range(period+1, n):
        chg = close[i] - close[i-1]
        g = chg if chg > 0 else 0
        l = abs(chg) if chg < 0 else 0
        gains = (gains * (period-1) + g) / period
        losses = (losses * (period-1) + l) / period
        rsi[i] = 100.0 - (100.0 / (1.0 + gains/losses)) if losses != 0 else 100.0
    return rsi

def calc_volume_ma(volume, period=20):
    """計算成交量均線"""
    vm = np.zeros(len(volume))
    for i in range(period, len(volume)):
        vm[i] = np.mean(volume[i-period:i])
    for i in range(min(period, len(volume))):
        vm[i] = np.mean(volume[:i+1]) if i > 0 else volume[0]
    return vm

def test_parameters(sid, k_range=[5,7,9,12,14], d_range=[3,5,7], 
                    k_entry_range=[30,35,40,45], 
                    rsi_filter_range=[None, 40, 45, 50],
                    vol_filter_range=[None, 1.0, 1.2, 1.5],
                    use_30min=False):
    """
    對一檔股票測試所有參數組合，找出最佳化設定
    
    回傳：{ 最佳參數dict, 所有結果list }
    """
    try:
        ticker_str = get_yfinance_ticker(sid)
        period_str = "3y"
        
        t = yf.Ticker(ticker_str)
        df = t.history(period=period_str)
        
        if df is None or len(df) < 100:
            alt, _ = try_alternate_ticker(ticker_str)
            t = yf.Ticker(alt)
            df = t.history(period=period_str)
        
        if df is None or len(df) < 100:
            return None
        
        close = df['Close'].values.astype(float)
        high = df['High'].values.astype(float)
        low = df['Low'].values.astype(float)
        volume = df['Volume'].values.astype(float)
        n = len(close)
        
        results = []
        
        for kp in k_range:
            for dp in d_range:
                k, d = calc_kd(close, high, low, kp, dp)
                rsi = calc_rsi(close)
                vol_ma = calc_volume_ma(volume)
                
                for ke in k_entry_range:
                    for rf in rsi_filter_range:
                        for vf in vol_filter_range:
                            # 跑回测
                            trades = []
                            i = 0
                            while i < n:
                                if i > 50 and k[i-1] <= d[i-1] and k[i] > d[i] and k[i] < ke:
                                    buy_p = float(close[i])
                                    buy_k = float(k[i])
                                    
                                    # RSI過濾
                                    if rf is not None and rsi[i] > rf:
                                        i += 1
                                        continue
                                    
                                    # 量價過濾
                                    if vf is not None and vol_ma[i] > 0 and volume[i] < vol_ma[i] * vf:
                                        i += 1
                                        continue
                                    
                                    sell_found = False
                                    for j in range(i+3, n):
                                        if k[j-1] >= d[j-1] and k[j] < d[j]:
                                            sell_p = float(close[j])
                                            profit = (sell_p - buy_p) / buy_p * 100
                                            trades.append(profit)
                                            i = j
                                            sell_found = True
                                            break
                                    if not sell_found:
                                        i += 1
                                else:
                                    i += 1
                            
                            total = len(trades)
                            if total >= 5:  # 至少5筆交易才有統計意義
                                wins = sum(1 for p in trades if p > 0)
                                wr = wins / total * 100
                                avg = np.mean(trades)
                                best = max(trades)
                                worst = min(trades)
                                sharpe = (avg / np.std(trades)) if np.std(trades) > 0 else 0
                                
                                # 綜合評分 = 勝率權重 + 平均報酬權重
                                score = wr * 0.4 + avg * 5 + sharpe * 10
                                
                                param_desc = "K%sD%s" % (kp, dp)
                                filters = []
                                if ke < 40: filters.append("K<%d" % ke)
                                if rf is not None: filters.append("RSI<%d" % rf)
                                if vf is not None: filters.append("量>%.1f倍" % vf)
                                
                                results.append({
                                    "k_period": kp, "d_period": dp,
                                    "k_entry": ke, "rsi_filter": rf,
                                    "vol_filter": vf,
                                    "param": param_desc,
                                    "filters": "+".join(filters) if filters else "無",
                                    "total_trades": total,
                                    "win_rate": round(wr, 1),
                                    "avg_profit": round(avg, 2),
                                    "best": round(best, 2),
                                    "worst": round(worst, 2),
                                    "sharpe": round(sharpe, 2),
                                    "score": round(score, 1),
                                })
        
        if not results:
            return None
        
        # 依綜合評分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        best_params = results[0]
        
        # 用當前價格算現況
        last_price = float(close[-1])
        k_now, d_now = calc_kd(close, high, low, best_params["k_period"], best_params["d_period"])
        
        return {
            "sid": sid,
            "has_data": True,
            "best": best_params,
            "top5": results[:5],
            "all_count": len(results),
            "current_k": round(float(k_now[-1]), 1),
            "current_d": round(float(d_now[-1]), 1),
            "current_price": last_price,
        }
        
    except Exception as e:
        return None


def batch_optimize(stock_list):
    """批量優化所有股票"""
    print("=" * 85)
    print("  個股最佳化參數回測")
    print("  %s" % NOW.strftime('%Y-%m-%d %H:%M'))
    print("=" * 85)
    
    all_results = []
    
    for sid, sname in stock_list:
        print("  %s %s 優化中..." % (sid, sname), end=" ", flush=True)
        r = test_parameters(sid)
        if r and r.get("has_data"):
            b = r["best"]
            all_results.append({
                "sid": sid, "name": sname,
                "best_kp": b["k_period"], "best_dp": b["d_period"],
                "k_entry": b["k_entry"], "rsi_filter": b["rsi_filter"],
                "vol_filter": b["vol_filter"],
                "param": b["param"], "filters": b["filters"],
                "total": b["total_trades"], "win_rate": b["win_rate"],
                "avg_profit": b["avg_profit"], "score": b["score"],
                "current_k": r["current_k"],
                "current_d": r["current_d"],
                "price": r["current_price"],
            })
            print("✅ 勝率%.0f%% 均%+.2f%% K%sD%s K<%s %s" % (
                b["win_rate"], b["avg_profit"],
                b["k_period"], b["d_period"],
                b["k_entry"], b["filters"]))
        else:
            print("❌ 無資料")
    
    # 按評分排序
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    print()
    print("=" * 85)
    print("  🏆 最佳化參數排行")
    print("=" * 85)
    print("  %-6s %-8s %6s %6s %8s %6s %7s %5s %-12s %-14s" % (
        "代號", "名稱", "股價", "K值", "最佳參數", "勝率", "均報酬", "次數", "進場濾網", "評分"))
    print("  " + "-" * 80)
    
    for r in all_results:
        price_str = "{:,.0f}".format(r["price"]) if r["price"] > 100 else "{:.1f}".format(r["price"])
        param_str = "K%sD%s" % (r["best_kp"], r["best_dp"])
        k_entry_str = "K<%d" % r["k_entry"]
        filters = r["filters"]
        score_str = "{:.0f}".format(r["score"])
        
        print("  %-6s %-8s %6s %5.1f %8s %5d%% %+6.2f%% %4d %-12s %-14s" % (
            r["sid"], r["name"], price_str, r["current_k"],
            param_str, r["win_rate"], r["avg_profit"], r["total"],
            k_entry_str + "+" + filters if filters else k_entry_str, score_str))
    
    print("  " + "-" * 80)
    
    return all_results


if __name__ == "__main__":
    # 測試用股票
    test_list = [
        ("3443", "創意"), ("2454", "聯發科"), ("3661", "世芯"), ("3035", "智原"),
        ("2059", "川湖"), ("2467", "志聖"), ("3090", "日電貿"), 
        ("3711", "日月光"), ("6139", "亞翔"), ("6213", "聯茂"),
        ("3042", "晶技"), ("2327", "國巨"), ("3006", "晶豪科"),
        ("5289", "宜鼎"), ("6207", "雷科"), ("5425", "台半"),
        ("2337", "旺宏"), ("2408", "南亞科"), ("2344", "華邦電"),
    ]
    
    results = batch_optimize(test_list)
