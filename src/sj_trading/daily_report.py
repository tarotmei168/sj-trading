# -*- coding: utf-8 -*-
"""
每日晨報/晚報產生器
產出格式：代號 + 股價 + K/D值 + RSI + 注意事項
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from ticker_fix import get_yfinance_ticker, get_stock_info, download_with_fallback

NOW = datetime.now()
TAIPEI_TZ = NOW

def calc_indicators(sid):
    """回傳一檔股票的完整技術指標 dict"""
    result = {"sid": sid, "has_data": False}
    try:
        ticker_str = get_yfinance_ticker(sid)
        t = yf.Ticker(ticker_str)
        df = t.history(period="6mo")
        if df is None or len(df) < 30:
            alt = ticker_str.replace(".TW",".TWO") if ".TW" in ticker_str else ticker_str.replace(".TWO",".TW")
            t = yf.Ticker(alt)
            df = t.history(period="6mo")
        if df is None or len(df) < 30:
            return result

        close = df['Close'].values.astype(float)
        high = df['High'].values.astype(float)
        low = df['Low'].values.astype(float)
        n = len(close)

        # KD
        k = np.zeros(n); d = np.zeros(n)
        k[0]=50; d[0]=50
        for i in range(1,n):
            ps=max(0,i-9+1)
            hh=np.max(high[ps:i+1]); ll=np.min(low[ps:i+1])
            rsv=(close[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
            k[i]=(2/3)*k[i-1]+(1/3)*rsv
            d[i]=(2/3)*d[i-1]+(1/3)*k[i]

        # RSI
        rsi=np.full(n,50.0)
        pp=14
        dc=np.diff(close)
        gains=dc[:pp][dc[:pp]>0].sum()/pp
        losses=abs(dc[:pp][dc[:pp]<0]).sum()/pp
        rsi[pp]=100-(100/(1+gains/losses)) if losses!=0 else 100
        for i in range(pp+1,n):
            chg=close[i]-close[i-1]
            g=chg if chg>0 else 0; l=abs(chg) if chg<0 else 0
            gains=(gains*(pp-1)+g)/pp; losses=(losses*(pp-1)+l)/pp
            rsi[i]=100-(100/(1+gains/losses)) if losses!=0 else 100

        # MACD
        def ema(d,p):
            m=2/(p+1); r=np.zeros(len(d)); r[0]=d[0]
            for i in range(1,len(d)): r[i]=(d[i]-r[i-1])*m+r[i-1]
            return r
        ef=ema(close,12); es=ema(close,26)
        macd=2*(ef-es-ema(ef-es,9))

        # MA20
        ma20=np.full(n,close[0])
        for i in range(20,n): ma20[i]=np.mean(close[i-19:i+1])

        # 60天波動
        df60=df.tail(60)
        h60=float(df60['High'].max()); l60=float(df60['Low'].min())
        swing60=(h60-l60)/h60*100 if h60>0 else 999

        # 最近3天的價格變化
        last5=df.tail(5)
        price_trend=[]
        for idx,row in last5.iterrows():
            price_trend.append(float(row['Close']))

        # 成交量大增檢查
        avg_vol=np.mean(df.tail(20)['Volume'].values)
        last_vol=float(df.tail(5)['Volume'].mean())
        vol_surge=last_vol > avg_vol * 1.5 if avg_vol>0 else False

        last_k=round(float(k[-1]),1); last_d=round(float(d[-1]),1)
        last_rsi=round(float(rsi[-1]),1); last_macd=round(float(macd[-1]),2)
        last_price=float(close[-1]); last_ma20=float(ma20[-1])

        # KD狀態
        kd_status="K>D多頭" if k[-1]>d[-1] else "K<D空頭"
        if k[-1]>d[-1] and k[-2]<=d[-2]: kd_status+=" ⭐金叉"
        elif k[-1]<d[-1] and k[-2]>=d[-2]: kd_status+=" 💀死叉"

        # 注意事項
        notes=[]
        if last_k<25: notes.append("低檔超賣區，跌深反彈機會")
        elif last_k>80: notes.append("高檔過熱區，注意拉回風險")
        elif last_k>65 and last_k<last_d: notes.append("高檔死叉形成中")
        if last_rsi<30: notes.append("RSI極端超賣")
        elif last_rsi>70: notes.append("RSI過熱")
        if last_price>last_ma20*1.05: notes.append("站上月線(+5%)")
        elif last_price<last_ma20*0.95: notes.append("跌破月線(-5%)")
        if vol_surge: notes.append("成交量放大1.5倍")
        if swing60<20: notes.append(f"橫盤{swing60:.0f}天波動{swing60:.0f}%")
        if not notes: notes.append("正常震盪")

        # 黃金交叉/死亡交叉提醒
        cross_note=""
        if "金叉" in kd_status and last_k<40: cross_note="⭐低檔金叉！買點浮現"
        elif "死叉" in kd_status and last_k>65: cross_note="💀高檔死叉！注意賣出"

        result.update({
            "has_data":True,
            "price":last_price,
            "k_val":last_k,"d_val":last_d,
            "rsi":last_rsi,"macd":last_macd,
            "swing_60":round(swing60,1),
            "ma20":round(last_ma20,1),
            "above_ma20":last_price>last_ma20,
            "kd_status":kd_status,
            "notes":" | ".join(notes),
            "cross_note":cross_note,
            "price_trend":price_trend,
            "vol_surge":vol_surge,
        })
    except:
        pass
    return result


# ══════════════════════════════════════════
#  主要報表
# ══════════════════════════════════════════
def generate_report():
    info = get_stock_info  # short ref
    
    # ── 核心持股（第1層）──
    CORE_HOLDINGS = [
        "2436","2337","5351",    # Rescue
        "3673","3711","4958","3042",  # Peak
    ]
    
    # ── ASIC 晶片股──
    ASIC_STOCKS = ["3443","2454","3661","3035"]
    
    # ── 投顧老師潛力股──
    TEACHER_PICKS = [
        "2481","6435","5425","5289","3260","8033","6207",  # 補充7檔
        "3006","2059","2467","3090","4960",  # 高勝率/低檔
        "2408","2337","2344","6770",  # 記憶體
        "2383","6213","8046","3189",  # PCB
        "6139","8150","2327",  # 投信認養/被動
    ]
    
    lines=[]
    lines.append("=" * 75)
    lines.append("  🦞 小龍蝦每日核心持股 & 潛力股晨報")
    lines.append("  %s" % NOW.strftime('%Y-%m-%d %H:%M'))
    lines.append("=" * 75)
    
    # ── 第1層：核心持股救援 ──
    lines.append("")
    lines.append("🔒 【第1層：核心持股救援】")
    lines.append("-" * 75)
    
    rescue_map = {"2436":"偉詮電(救援)","2337":"旺宏(救援)","5351":"鈺創(救援)"}
    peak_map = {"3673":"TPK-KY(高檔)","3711":"日月光(高檔)","4958":"臻鼎-KY(高檔)","3042":"晶技(高檔)"}
    all_core = {**rescue_map, **peak_map}
    
    for sid, label in all_core.items():
        r=calc_indicators(sid)
        if not r.get("has_data"):
            lines.append("  %s %s: 無資料" % (sid, label))
            continue
        info_d=get_stock_info(sid)
        name=info_d.get("name",sid)
        
        price_str="{:,.0f}".format(r["price"]) if r["price"]>100 else "{:.1f}".format(r["price"])
        rsi_icon="💎" if r["rsi"]<30 else ("📉" if r["rsi"]<40 else ("🔥" if r["rsi"]>70 else "⚪"))
        note=r.get("cross_note","") or r.get("notes","")
        
        lines.append("")
        lines.append("  %s %s (%s)" % (sid, name, label))
        lines.append("    股價:%s | K:%.1f D:%.1f %s | RSI:%.1f%s | MACD:%.2f" % (
            price_str, r["k_val"], r["d_val"], r["kd_status"], r["rsi"], rsi_icon, r["macd"]))
        lines.append("    波動60:%.1f%% | 月線:%.0f | %s" % (r["swing_60"], r["ma20"], 
            "站上月線✅" if r["above_ma20"] else "跌破月線❌"))
        lines.append("    ⚠️ %s" % note)
    
    # ── ASIC 晶片股 ──
    lines.append("")
    lines.append("🎯 【ASIC 晶片股】")
    lines.append("-" * 75)
    for sid in ASIC_STOCKS:
        r=calc_indicators(sid)
        if not r.get("has_data"): continue
        info_d=get_stock_info(sid)
        name=info_d.get("name",sid)
        price_str="{:,.0f}".format(r["price"]) if r["price"]>100 else "{:.1f}".format(r["price"])
        rsi_icon="💎" if r["rsi"]<30 else ("📉" if r["rsi"]<40 else ("🔥" if r["rsi"]>70 else "⚪"))
        
        # 賣點提醒
        sell_note=""
        if r["k_val"]>80 and r["k_val"]<r["d_val"]:
            sell_note=" ⚠️高檔頓化注意賣出"
        elif r["k_val"]>65 and "死叉" in r["kd_status"]:
            sell_note=" 💀死亡交叉形成中"
        
        lines.append("")
        lines.append("  %s %s" % (sid, name))
        lines.append("    股價:%s | K:%.1f D:%.1f %s | RSI:%.1f%s | MACD:%.2f%s" % (
            price_str, r["k_val"], r["d_val"], r["kd_status"], r["rsi"], rsi_icon, r["macd"], sell_note))
        lines.append("    波動60:%.1f%% | 月線:%.0f | %s" % (r["swing_60"], r["ma20"],
            "站上月線✅" if r["above_ma20"] else "跌破月線❌"))
    
    # ── 投顧老師潛力股 ──
    lines.append("")
    lines.append("📋 【投顧老師潛力股追蹤】")
    lines.append("-" * 75)
    
    for sid in TEACHER_PICKS:
        r=calc_indicators(sid)
        if not r.get("has_data"): continue
        info_d=get_stock_info(sid)
        name=info_d.get("name",sid)
        theme=info_d.get("theme","")
        feature=info_d.get("feature","")
        
        price_str="{:,.0f}".format(r["price"]) if r["price"]>100 else "{:.1f}".format(r["price"])
        rsi_icon=("💎超跌" if r["rsi"]<30 else ("📉偏低" if r["rsi"]<40 else ("🔥過熱" if r["rsi"]>70 else "⚪中性")))
        
        # 買點提醒
        buy_signal=""
        if r["k_val"]<30 and "多頭" in r["kd_status"]:
            buy_signal=" ⭐低檔黃金交叉！"
        elif r["k_val"]<25:
            buy_signal=" 💎極度超賣區"
        elif r["k_val"]>80 and "死叉" in r["kd_status"]:
            buy_signal=" ⚠️高檔死叉勿追"
        
        lines.append("")
        lines.append("  %s %s [%s] %s" % (sid, name, theme, buy_signal))
        lines.append("    股價:%s | K:%.1f D:%.1f %s | RSI:%.1f(%s) | MACD:%.2f | 波動:%.1f%%" % (
            price_str, r["k_val"], r["d_val"], r["kd_status"], r["rsi"], rsi_icon, r["macd"], r["swing_60"]))
        lines.append("    月線:%.0f | %s" % (r["ma20"],
            "站上月線✅" if r["above_ma20"] else "跌破月線❌"))
        if feature:
            lines.append("    💡 %s" % feature)
        lines.append("    ⚠️ %s" % r["notes"])
    
    # ── 總結 ──
    lines.append("")
    lines.append("-" * 75)
    lines.append("  💡 今日關注")
    lines.append("")
    
    # 低檔機會清單
    low_entries=[]
    for sid in CORE_HOLDINGS + ASIC_STOCKS + TEACHER_PICKS:
        r=calc_indicators(sid)
        if r.get("has_data") and r["k_val"]<30:
            info_d=get_stock_info(sid)
            low_entries.append((sid, info_d.get("name",sid), r["k_val"], r["rsi"], r["price"]))
    low_entries.sort(key=lambda x: x[2])
    
    if low_entries:
        lines.append("  📉 K值<30超賣區（潛在買點）：")
        for sid, nm, kv, rsi_v, pr in low_entries:
            lines.append("    %s %s | 股價%.0f | K值%.1f | RSI%.1f" % (sid, nm, pr, kv, rsi_v))
    
    # 高檔風險清單
    high_risk=[]
    for sid in CORE_HOLDINGS + ASIC_STOCKS + TEACHER_PICKS:
        r=calc_indicators(sid)
        if r.get("has_data") and r["k_val"]>75:
            info_d=get_stock_info(sid)
            if "死叉" in r["kd_status"] or r["k_val"]<r["d_val"]:
                high_risk.append((sid, info_d.get("name",sid), r["k_val"], r["d_val"], r["price"]))
    if high_risk:
        lines.append("")
        lines.append("  🔴 K值高檔+死叉（注意賣出）：")
        for sid, nm, kv, dv, pr in high_risk:
            lines.append("    %s %s | 股價%.0f | K%.1f D%.1f 死叉" % (sid, nm, pr, kv, dv))
    
    lines.append("")
    lines.append("-" * 75)
    lines.append("  ✅ 晨報完畢")
    lines.append("=" * 75)
    
    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(report)
    
    # 同步產出網頁版到 web/index.html
    from daily_web_report import gen_html, push_to_github
    html = gen_html()
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")
    os.makedirs(web_dir, exist_ok=True)
    
    with open(os.path.join(web_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("  ✅ web/index.html 已更新")
    
    # 自動 Git Push
    push_to_github()
