# -*- coding: utf-8 -*-
"""
回測投顧老師提供的股票清單
用 3 年資料回測 KD 低檔金叉績效
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yfinance as yf
import numpy as np
from datetime import datetime

NOW = datetime.now()
TAIPEI_NOW = NOW

# 投顧老師清單（按主題分類）
TEACHER_STOCKS = {
    "功率元件": [("8253","強茂"), ("8261","富鼎"), ("6453","大中"), ("5425","台半")],
    "面板封裝": [("2409","友達"), ("3481","群創"), ("8215","明碁材"), ("4960","誠美材")],
    "生技化工": [("1729","三晃"), ("6446","藥華藥"), ("1723","中華化"), ("1718","中纖")],
    "機器人": [("1536","和大"), ("4576","大銀微"), ("2049","上銀"), ("6215","和椿")],
    "六月營收亮眼": [("3449","宜鼎"), ("3260","威剛"), ("2059","川湖"), ("6535","穎威")],
    "軍工概念": [("5223","雷虎"), ("2637","長榮航太"), ("8399","晟田"), ("5371","中光電")],
    "PCB": [("2383","台光電"), ("3189","景碩"), ("6213","聯茂"), ("8046","南電")],
    "IC設計": [("3006","晶豪科"), ("6295","茂達"), ("6732","昇佳"), ("6799","來頡")],
    "投信認養": [("4433","大量"), ("2427","興勤"), ("1307","南亞"), ("6139","亞翔")],
    "先進封裝": [("6257","矽格"), ("6525","捷敏-KY"), ("8131","福懋科"), ("8150","南茂")],
    "記憶體": [("2408","南亞科"), ("2337","旺宏"), ("2344","華邦電"), ("6770","力積電")],
    "矽晶圓": [("3707","漢磊"), ("3532","台勝科"), ("6182","合晶"), ("6488","環球晶")],
    "半導體設備": [("8028","昇陽半"), ("1717","長興"), ("5536","聖暉"), ("2467","志聖")],
    "矽光子": [("3163","波若威"), ("4979","華星光"), ("3105","穩懋"), ("3363","上詮")],
    "被動元件": [("2463","蜜望實"), ("2327","國巨"), ("3090","日電貿"), ("2472","禾伸堂")],
}

def calc_kd(close, high, low):
    n = len(close)
    k = np.zeros(n); d = np.zeros(n)
    k[0] = 50; d[0] = 50
    for i in range(1, n):
        ps = max(0, i - 9 + 1)
        hh = np.max(high[ps:i+1])
        ll = np.min(low[ps:i+1])
        rsv = (close[i] - ll) / (hh - ll) * 100.0 if hh - ll > 0 else 50
        k[i] = (2.0/3) * k[i-1] + (1.0/3) * rsv
        d[i] = (2.0/3) * d[i-1] + (1.0/3) * k[i]
    return k, d

def calc_ema(data, period):
    m = 2.0 / (period + 1)
    r = np.zeros(len(data))
    r[0] = data[0]
    for i in range(1, len(data)):
        r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r

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

def analyze_stock_3y(sid, sname):
    """回傳 3 年 KD 低檔金叉績效（含上市櫃代碼自動校正）"""
    from ticker_fix import get_yfinance_ticker, try_alternate_ticker
    result = {"sid": sid, "name": sname, "has_data": False}
    try:
        ticker_str = get_yfinance_ticker(sid)
        t = yf.Ticker(ticker_str)
        df = t.history(period="3y")
        if df is None or len(df) < 100:
            alt_ticker, _ = try_alternate_ticker(ticker_str)
            t = yf.Ticker(alt_ticker)
            df = t.history(period="3y")
        if df is None or len(df) < 100:
            return result

        close = df['Close'].values.astype(float)
        high = df['High'].values.astype(float)
        low = df['Low'].values.astype(float)
        n = len(close)

        k, d = calc_kd(close, high, low)
        macd_arr = 2 * (calc_ema(close,12) - calc_ema(close,26) - calc_ema(calc_ema(close,12) - calc_ema(close,26), 9))

        rsi = calc_rsi(close)

        # 60天波動
        df_60 = df.tail(60)
        swing60 = (float(df_60['High'].max()) - float(df_60['Low'].min())) / float(df_60['High'].max()) * 100

        last_price = float(close[-1])
        last_k = round(float(k[-1]), 1)
        last_d = round(float(d[-1]), 1)
        last_rsi = round(float(rsi[-1]), 1)
        last_macd = round(float(macd_arr[-1]), 2)

        # KD狀態
        kd_status = "K>D多頭" if k[-1] > d[-1] else "K<D空頭"
        if k[-1] > d[-1] and k[-2] <= d[-2]: kd_status += " ⭐金叉!"
        elif k[-1] < d[-1] and k[-2] >= d[-2]: kd_status += " 💀死叉"

        # 找所有低檔金叉（不限時間範圍）
        trades = []
        i = 0
        while i < n:
            if i > 0 and k[i-1] <= d[i-1] and k[i] > d[i] and k[i] < 40:
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
                        hold = (sell_date - buy_date).days
                        max_p = max(close[i:j+1])
                        max_profit = (max_p - buy_p) / buy_p * 100
                        trades.append({
                            "buy_date": buy_date, "buy_price": buy_p,
                            "buy_k": buy_k, "buy_d": buy_d,
                            "sell_date": sell_date, "sell_price": sell_p,
                            "profit": profit, "hold_days": hold,
                            "max_profit": max_profit, "win": profit > 0,
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
                        "win": profit > 0,
                    })
                    i += 1
            else:
                i += 1

        closed = [t for t in trades if t["sell_date"] is not None]
        profits = [t["profit"] for t in closed]
        wins = sum(t["win"] for t in closed)
        total = len(closed)

        result.update({
            "has_data": True,
            "price": last_price,
            "k_val": last_k, "d_val": last_d, "rsi": last_rsi,
            "macd": last_macd,
            "swing_60": round(swing60, 1),
            "kd_status": kd_status,
            "trades": trades,
            "total_trades": total,
            "wins": wins,
            "win_rate": round(wins / total * 100, 0) if total > 0 else 0,
            "avg_profit": round(np.mean(profits), 2) if profits else 0,
            "best_trade": round(max(profits), 2) if profits else 0,
            "worst_trade": round(min(profits), 2) if profits else 0,
        })
    except:
        pass
    return result

def format_report(all_results):
    """排版報表"""
    lines = []
    lines.append("=" * 90)
    lines.append("  投顧老師股票清單 — 3年KD低檔金叉回測")
    lines.append("  %s" % NOW.strftime('%Y-%m-%d %H:%M'))
    lines.append("=" * 90)

    for theme, stocks in TEACHER_STOCKS.items():
        lines.append("")
        lines.append("─" * 90)
        lines.append("  [%s]" % theme)
        lines.append("─" * 90)

        theme_results = []
        for sid, sname in stocks:
            r = analyze_stock_3y(sid, sname)
            if r.get("has_data"):
                theme_results.append(r)

        if not theme_results:
            lines.append("  無可用資料")
            continue

        # 按勝率排序
        theme_results.sort(key=lambda x: x["win_rate"], reverse=True)

        for r in theme_results:
            price_str = "{:,.0f}".format(r["price"]) if r["price"] > 100 else "{:.1f}".format(r["price"])
            rsi_icon = "💎超跌" if r["rsi"] < 30 else ("📉偏低" if r["rsi"] < 40 else ("🔥過熱" if r["rsi"] > 70 else "⚪中性"))
            kd_s = r["kd_status"]
            wr = r["win_rate"]
            avg_p = r["avg_profit"]
            best = r["best_trade"]
            worst = r["worst_trade"]
            total = r["total_trades"]

            # 評分
            score = 0
            if wr >= 65: score += 30
            elif wr >= 50: score += 15
            if avg_p >= 8: score += 30
            elif avg_p >= 4: score += 15
            if r["k_val"] < 40: score += 20
            if r["rsi"] < 50: score += 10
            if r["swing_60"] < 35: score += 10

            if score >= 60: tag = "⭐強烈"
            elif score >= 40: tag = "🔔觀察"
            elif score >= 20: tag = "👀留意"
            else: tag = "⏳等待"

            lines.append("")
            lines.append("  %s %s | %s 評分%d" % (r["sid"], r["name"], tag, score))
            price_display = "{:,.0f}".format(r["price"])
            lines.append("    股價%s | RSI:%.1f(%s) | K:%.1f %s | 波動%.1f%%" % (
                price_display, r["rsi"], rsi_icon, r["k_val"], kd_s, r["swing_60"]))
            
            if total > 0:
                lines.append("    3年低檔金叉%d次 | 勝率%d%% | 平均%+.2f%% | 最佳%+.2f%% | 最差%+.2f%%" % (
                    total, wr, avg_p, best, worst))
                # 最近3次交易
                recent_trades = r["trades"][-3:]
                for t in recent_trades:
                    bd = t["buy_date"].strftime('%m/%d')
                    lines.append("      %s 買%.0f K=%.1f → %+.2f%% %s" % (
                        bd, t["buy_price"], t["buy_k"], t["profit"], "✅" if t["win"] else "❌"))
            else:
                lines.append("    3年內無低檔金叉訊號")

    lines.append("")
    lines.append("=" * 90)
    lines.append("  回測完成")
    lines.append("=" * 90)

    return "\n".join(lines)

if __name__ == "__main__":
    # 收集所有結果
    all_r = {}
    for theme, stocks in TEACHER_STOCKS.items():
        for sid, sname in stocks:
            all_r[(sid, sname)] = analyze_stock_3y(sid, sname)

    print(format_report(all_r))

    # 額外：排名前10
    valid = [r for r in all_r.values() if r.get("has_data")]
    valid.sort(key=lambda x: (
        30 if x["win_rate"] >= 65 else (15 if x["win_rate"] >= 50 else 0) +
        20 if x["k_val"] < 40 else 0 +
        10 if x["rsi"] < 50 else 0), reverse=True)

    print()
    print("=" * 90)
    print("  TOP 10 潛力股排名（依賽局評分）")
    print("=" * 90)
    print("  %-6s %-8s %8s %6s %6s %6s %6s %6s" % ("代號", "名稱", "股價", "K值", "RSI", "勝率", "均報酬", "次數"))
    for r in valid[:10]:
        print("  %-6s %-8s %8.0f %5.1f %5.1f %5d%% %+6.2f%% %4d" % (
            r["sid"], r["name"], r["price"], r["k_val"], r["rsi"],
            r["win_rate"], r["avg_profit"], r["total_trades"]))
