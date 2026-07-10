# -*- coding: utf-8 -*-
"""即時完整晨報"""
import os, sys, json, csv
from datetime import datetime
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
OUTPUT = os.path.join(BASE, "output")
sys.path.insert(0, os.path.join(BASE, "src", "sj_trading"))

# 讀新聞
news_data = {}
news_path = os.path.join(OUTPUT, "news_filtered.json")
if os.path.exists(news_path):
    with open(news_path, "r", encoding="utf-8") as f:
        news_data = json.load(f).get("results", {})

def get_kd(sid):
    path = os.path.join(DB, "%s_3y.csv" % sid)
    if not os.path.exists(path): return None
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    c = np.array([float(r["close"]) for r in rows], dtype=float)
    hk = "high" if "high" in rows[0] else "max"; lk = "low" if "low" in rows[0] else "min"
    h = np.array([float(r[hk]) for r in rows], dtype=float)
    l = np.array([float(r[lk]) for r in rows], dtype=float)
    n = len(c); k=np.zeros(n); d=np.zeros(n)
    k[0]=50; d[0]=50
    for i in range(1,n):
        ps=max(0,i-9+1); hh=np.max(h[ps:i+1]); ll=np.min(l[ps:i+1])
        rsv=(c[i]-ll)/(hh-ll)*100 if hh-ll>0 else 50
        k[i]=(2/3)*k[i-1]+(1/3)*rsv; d[i]=(2/3)*d[i-1]+(1/3)*k[i]
    rsi_v = 50
    if n>=20:
        g=sum(c[j]-c[j-1] for j in range(n-14,n) if c[j]>c[j-1])/14
        ls=sum(abs(c[j]-c[j-1]) for j in range(n-14,n) if c[j]<c[j-1])/14
        rsi_v = round(100-100/(1+g/ls) if ls>0 else 100, 1)
    low20 = round(min(l[-20:]), 1)
    ma20 = round(np.mean(c[-20:]), 1)
    return {"price":round(c[-1],1),"k":round(k[-1],1),"d":round(d[-1],1),"up":k[-1]>d[-1],"rsi":rsi_v,"support":low20,"ma20":ma20}

CORE = ["2436","2337","5351","3673","3711","4958","3042","2454","2317"]
POTENTIAL = ["3443","3661","3035","3231","2382","3017","2451","8150","2344","6770"]
NM = {"2436":"偉詮電","2337":"旺宏","5351":"鈺創","3673":"TPK-KY","3711":"日月光",
      "4958":"臻鼎-KY","3042":"晶技","2454":"聯發科","2317":"鴻海",
      "3443":"創意","3661":"世芯","3035":"智原","3231":"緯創","2382":"廣達",
      "3017":"奇鋐","2451":"創見","8150":"南茂","2344":"華邦電","6770":"力積電"}

def gen():
    now = datetime.now()
    lines = []
    lines.append("="*80)
    lines.append("  🦞 小龍蝦晨報 | %s" % now.strftime('%Y-%m-%d %H:%M'))
    lines.append("="*80)

    # 大盤
    lines.append("")
    try:
        with open(os.path.join(DB,"TAIEX_daily_kline.csv"),"r",encoding="utf-8") as f:
            tr = list(csv.DictReader(f))
        tc = np.array([float(r["close"]) for r in tr], dtype=float)
        trsi=50
        if len(tc)>=20:
            g=sum(tc[j]-tc[j-1] for j in range(len(tc)-14,len(tc)) if tc[j]>tc[j-1])/14
            ls=sum(abs(tc[j]-tc[j-1]) for j in range(len(tc)-14,len(tc)) if tc[j]<tc[j-1])/14
            trsi=round(100-100/(1+g/ls) if ls>0 else 100,1)
        txt = "📈偏多" if trsi>50 else "📉偏空" if trsi>30 else "💎超賣"
        lines.append("🌤【大盤天氣】TAIEX %.0f | RSI(14)=%.1f %s" % (tc[-1], trsi, txt))
    except:
        lines.append("🌤【大盤天氣】資料暫缺")

    # 核心持股
    lines.append("")
    lines.append("🔒【第1層：核心持股】— 有部位")
    lines.append("-"*80)
    lines.append("  %-6s %-6s %6s %4s %6s %4s %-6s %s" % ("代號","名稱","收盤","K/D","狀態","RSI","支撐","新聞📰"))
    lines.append("-"*80)

    for sid in CORE:
        r = get_kd(sid)
        if not r: continue
        nm = NM.get(sid,sid)
        kd_s = "🟢K>D" if r["up"] else "🔴K<D"
        if r["rsi"]<30: lv="超賣"
        elif r["rsi"]<40: lv="偏低"
        elif r["rsi"]<55: lv="中性"
        elif r["rsi"]<70: lv="偏多"
        else: lv="過熱"
        n = news_data.get(sid,{})
        ns = n.get("summaries",[None])[0] if n.get("summaries") else ""
        if ns: ns = ns[:30]
        lines.append("  %-6s %-6s %6.0f %4s %6s %4d %-6s %s" % (
            sid, nm, r["price"], "%d/%.0f"%(r["k"],r["d"]), kd_s, r["rsi"], "%.0f"%r["support"], ns))

    # 潛力股
    lines.append("")
    lines.append("🎯【第2層：潛力股】— 等右側開槍")
    lines.append("-"*80)
    lines.append("  %-6s %-6s %6s %4s %6s %4s %-6s %s" % ("代號","名稱","收盤","K/D","狀態","RSI","支撐","新聞📰"))
    lines.append("-"*80)

    for sid in POTENTIAL:
        r = get_kd(sid)
        if not r: continue
        nm = NM.get(sid,sid)
        kd_s = "🟢K>D" if r["up"] else "🔴K<D"
        if r["rsi"]<30: lv="超賣"
        elif r["rsi"]<40: lv="偏低"
        elif r["rsi"]<55: lv="中性"
        elif r["rsi"]<70: lv="偏多"
        else: lv="過熱"
        n = news_data.get(sid,{})
        ns = n.get("summaries",[None])[0] if n.get("summaries") else ""
        if ns: ns = ns[:30]
        lines.append("  %-6s %-6s %6.0f %4s %6s %4d %-6s %s" % (
            sid, nm, r["price"], "%d/%.0f"%(r["k"],r["d"]), kd_s, r["rsi"], "%.0f"%r["support"], ns))

    # 投信
    lines.append("")
    lines.append("🏦【第3層：投信秘密建倉】")
    lines.append("-"*80)
    sitc = os.path.join(OUTPUT, "SITC_Accumulation.csv")
    if os.path.exists(sitc):
        with open(sitc,"r",encoding="utf-8") as f:
            sr = list(csv.DictReader(f))
        all_sids = CORE + POTENTIAL
        for sid in all_sids:
            tr = [r for r in sr if r["stock_id"]==sid and int(r["trust_net"])>0]
            if tr:
                days = len(set(r["date"] for r in tr[-5:]))
                total = sum(int(r["trust_net"]) for r in tr[-5:])
                lines.append("  %s %s | 投信連買%d天 淨%+.0f萬股" % (sid, NM.get(sid,sid), days, total/10000))
    else:
        lines.append("  (盤後16:30更新)")

    # 新聞
    lines.append("")
    lines.append("📰【第4層：產業大事】")
    lines.append("-"*80)
    has = False
    for sid in CORE + POTENTIAL:
        n = news_data.get(sid,{})
        if n.get("summaries"):
            has = True
            nm = NM.get(sid,sid)
            for s in n["summaries"][:2]:
                lines.append("  %s %s | %s" % (sid, nm, s[:50]))
    if not has: lines.append("  (新聞16:30後更新)")

    lines.append("")
    lines.append("-"*80)
    lines.append("  ⚡ 08:30~13:35 DayMonitor盤中監控")
    lines.append("  ⚡ 16:30 全市場資料庫更新")
    lines.append("="*80)

    return "\n".join(lines)

if __name__ == "__main__":
    print(gen())
