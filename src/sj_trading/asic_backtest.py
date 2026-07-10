# -*- coding: utf-8 -*-
"""
ASIC backtest core - analyze_stock() function used by lobster_pipeline Layer3
"""
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime

def calc_ema(data, period):
    m = 2.0 / (period + 1)
    r = np.zeros(len(data))
    r[0] = data[0]
    for i in range(1, len(data)):
        r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r

def safe_days(t1, t2):
    if hasattr(t1, 'tz') and t1.tz is not None:
        t1 = t1.tz_localize(None)
    if hasattr(t2, 'tz') and t2.tz is not None:
        t2 = t2.tz_localize(None)
    return (t1 - t2).days

def analyze_stock(sid, name, theme, reason):
    """回傳一檔股票的完整分析 dict（含上市櫃代碼自動校正）"""
    from ticker_fix import get_yfinance_ticker, try_alternate_ticker
    result = {
        "sid": sid, "name": name, "theme": theme, "reason": reason,
        "has_data": False
    }
    try:
        ticker_str = get_yfinance_ticker(sid)
        t = yf.Ticker(ticker_str)
        df = t.history(period="3y")
        if df is None or len(df) < 100:
            # 試另一種櫃/市代碼
            alt_ticker, _ = try_alternate_ticker(ticker_str)
            t = yf.Ticker(alt_ticker)
            df = t.history(period="3y")
        if df is None or len(df) < 60:
            return result
        
        close = df['Close'].values.astype(float)
        high = df['High'].values.astype(float)
        low = df['Low'].values.astype(float)
        n = len(close)
        
        # KD
        k = np.zeros(n); d = np.zeros(n)
        k[0] = 50; d[0] = 50
        for i in range(1, n):
            ps = max(0, i - 9 + 1)
            hh = np.max(high[ps:i+1])
            ll = np.min(low[ps:i+1])
            rsv = (close[i] - ll) / (hh - ll) * 100.0 if hh - ll > 0 else 50
            k[i] = (2.0/3) * k[i-1] + (1.0/3) * rsv
            d[i] = (2.0/3) * d[i-1] + (1.0/3) * k[i]
        
        ef = calc_ema(close, 12)
        es = calc_ema(close, 26)
        dif = ef - es
        dea = calc_ema(dif, 9)
        macd = 2 * (dif - dea)
        
        rsi = np.full(n, 50.0)
        pd_p = 14
        diff_c = np.diff(close)
        gains = diff_c[:pd_p][diff_c[:pd_p] > 0].sum() / pd_p
        losses = abs(diff_c[:pd_p][diff_c[:pd_p] < 0]).sum() / pd_p
        rsi[pd_p] = 100.0 - (100.0 / (1.0 + gains/losses)) if losses != 0 else 100.0
        for i in range(pd_p+1, n):
            chg = close[i] - close[i-1]
            g = chg if chg > 0 else 0
            l = abs(chg) if chg < 0 else 0
            gains = (gains * (pd_p-1) + g) / pd_p
            losses = (losses * (pd_p-1) + l) / pd_p
            rsi[i] = 100.0 - (100.0 / (1.0 + gains/losses)) if losses != 0 else 100.0
        
        ma20 = np.full(n, close[0])
        for i in range(20, n):
            ma20[i] = np.mean(close[i-19:i+1])
        
        df_60 = df.tail(60)
        h60 = float(df_60['High'].max())
        l60 = float(df_60['Low'].min())
        swing60 = (h60 - l60) / h60 * 100 if h60 > 0 else 999
        last_price = float(close[-1])
        last_k = round(float(k[-1]), 1)
        last_d = round(float(d[-1]), 1)
        last_rsi = round(float(rsi[-1]), 1)
        last_macd = round(float(macd[-1]), 2)
        above_ma20 = last_price > ma20[-1]
        
        # 歷史低檔金叉績效
        cutoff = max(0, n - 130)
        trades = []
        i = 0
        while i < n:
            if i > cutoff and i > 0 and k[i-1] <= d[i-1] and k[i] > d[i] and k[i] < 40:
                buy_p = float(close[i])
                buy_k = float(k[i])
                buy_d = float(d[i])
                buy_date = df.index[i]
                sell_found = False
                for j in range(i+5, n):
                    if k[j-1] >= d[j-1] and k[j] < d[j]:
                        sell_p = float(close[j])
                        sell_date = df.index[j]
                        profit = (sell_p - buy_p) / buy_p * 100
                        hold = safe_days(sell_date, buy_date)
                        max_p = max(close[i:j+1])
                        max_profit = (max_p - buy_p) / buy_p * 100
                        trades.append({
                            "buy_date": buy_date, "buy_price": buy_p,
                            "buy_k": buy_k, "buy_d": buy_d,
                            "sell_date": sell_date, "sell_price": sell_p,
                            "profit": profit, "hold_days": hold,
                            "max_profit": max_profit, "status": "closed"
                        })
                        i = j; sell_found = True; break
                if not sell_found:
                    profit = (last_price - buy_p) / buy_p * 100
                    trades.append({
                        "buy_date": buy_date, "buy_price": buy_p,
                        "buy_k": buy_k, "buy_d": buy_d,
                        "sell_date": None, "sell_price": None,
                        "profit": profit, "hold_days": None,
                        "max_profit": max(max(close[i:]) - buy_p, 0) / buy_p * 100,
                        "status": "holding"
                    })
                    i += 1
            else:
                i += 1
        
        closed_trades = [t for t in trades if t["status"] == "closed"]
        profits = [t["profit"] for t in closed_trades]
        total = len(profits)
        wins = sum(1 for p in profits if p > 0)
        
        # 評分
        score = 0; reasons = []
        if k[-1] > d[-1] and k[-2] <= d[-2]:
            score += 30; reasons.append("KD金叉+30")
        elif k[-1] > d[-1]:
            score += 10; reasons.append("K>D+10")
        if k[-1] < 40:
            score += 20; reasons.append("K<40低檔+20")
        elif k[-1] < 50:
            score += 10; reasons.append("K<50+10")
        if swing60 < 25:
            score += 25; reasons.append("橫盤<25%+25")
        elif swing60 < 35:
            score += 10; reasons.append("波動適中+10")
        if last_rsi < 40:
            score += 15; reasons.append("RSI<40偏低+15")
        elif last_rsi < 50:
            score += 10; reasons.append("RSI<50+10")
        if last_rsi > 70:
            score -= 5; reasons.append("RSI過熱-5")
        if above_ma20:
            score += 5; reasons.append("站上月線+5")
        if macd[-1] > 0 and macd[-2] <= 0:
            score += 15; reasons.append("MACD轉正+15")
        elif macd[-1] > 0:
            score += 5; reasons.append("MACD正值+5")
        
        if score >= 60: level = "強烈佈局訊號!"
        elif score >= 40: level = "🔔 觀察佈局"
        elif score >= 20: level = "👀 持續關注"
        else: level = "⏳ 等待訊號"
        
        if last_rsi < 30: rsi_icon = "💎超跌"
        elif last_rsi < 40: rsi_icon = "📉偏低"
        elif last_rsi > 70: rsi_icon = "🔥過熱"
        else: rsi_icon = "⚪中性"
        
        kd_str = "K>D多頭" if k[-1] > d[-1] else "K<D空頭"
        if k[-1] > d[-1] and k[-2] <= d[-2]: kd_str += " ⭐金叉!"
        elif k[-1] < d[-1] and k[-2] >= d[-2]: kd_str += " 💀死叉"
        
        result.update({
            "has_data": True,
            "price": last_price,
            "k_val": last_k, "d_val": last_d,
            "rsi": last_rsi, "rsi_icon": rsi_icon,
            "macd": last_macd,
            "swing_60": round(swing60, 1),
            "above_ma20": above_ma20,
            "kd_str": kd_str,
            "score": score, "level": level,
            "reasons": " ".join(reasons),
            "trades": trades,
            "total_trades": total,
            "win_rate": round(wins / total * 100, 0) if total > 0 else 0,
            "avg_profit": round(np.mean(profits), 2) if profits else 0,
            "best_trade": max(profits) if profits else 0,
        })
    except:
        pass
    return result
