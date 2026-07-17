# -*- coding: utf-8 -*-
"""
全球聯動與總經氣象台
=====================
第一維度：美股四大指數 + 台指期夜盤
第二維度：未來14天關鍵事件（除權息/法說/期貨結算/投信季底結帳）
第三維度：台美產業聯動牆（美股漲什麼台股跟著動）
"""
import os, json, csv, sys
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, "database")
OUTPUT = os.path.join(BASE, "output")
sys.path.insert(0, os.path.join(BASE, "src", "sj_trading"))

# ═══════════════════════════════════════════════
#  第一維度：美股四大指數 + 費半
# ═══════════════════════════════════════════════
def get_us_indexes():
    """只抓費城半導體 SOX（唯一大盤風向球）"""
    result = {}
    try:
        import yfinance as yf
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            t = yf.Ticker("^SOX")
            df = t.history(period="5d")
        if df is not None and len(df) >= 2:
            closes = df["Close"].values
            change = (closes[-1] / closes[-2] - 1) * 100
            result["費城半導體"] = {"close": round(closes[-1], 2), "change": round(change, 2)}
    except Exception:
        pass
    return result

def get_taiwan_futures():
    """台指期即時指數 — 抓當下最新報價（不分日夜盤）"""
    
    # 方式1：用 Shioaji 永豐 API 抓即時
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from shioaji_helper import ShioajiClient
        import shioaji as sj
        sjc = ShioajiClient()
        if sjc.login():
            # 台指期近月合約
            contract = sj.BaseContract(
                code='TXFC1F',
                exchange=sj.Exchange.TAIFEX,
                security_type=sj.SecurityType.Stock  # Future 會 crash，用 Stock 可建立
            )
            snap = sjc.api.snapshots([contract])
            if snap and len(snap) > 0:
                close = snap[0].close
                change_price = snap[0].change_price
                if close and close > 0:
                    change_rate = (change_price / (close - change_price)) * 100 if (close - change_price) != 0 else 0
                    sjc.logout()
                    return {"close": round(close, 2), "change": round(change_rate, 2), "source": "永豐即時"}
            sjc.logout()
    except:
        pass
    
    # 方式2：用 yfinance 抓台指期即時（最新一根 K 線）
    for sym in ["TX00.TW", "^TX00", "TW00.TF"]:
        try:
            import yfinance as yf
            import io, contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                t = yf.Ticker(sym)
                df = t.history(period="2d", interval="1h")
                if df is not None and len(df) >= 2:
                    closes = df["Close"].values
                    change = (closes[-1] / closes[-2] - 1) * 100
                    return {"close": round(closes[-1], 2), "change": round(change, 2), "source": "yfinance即時"}
                df = t.history(period="5d")
                if df is not None and len(df) >= 2:
                    closes = df["Close"].values
                    change = (closes[-1] / closes[-2] - 1) * 100
                    return {"close": round(closes[-1], 2), "change": round(change, 2), "source": "yfinance日K"}
        except:
            continue
    
    return None

# ═══════════════════════════════════════════════
#  第二維度：未來14天關鍵事件
# ═══════════════════════════════════════════════
KNOWN_EVENTS_2026 = {
    # ═══════════════════ 7月 ═══════════════════
    "2026-07-10": [("除權息", "2317鴻海除息4.0元", "🔥重要"),
                   ("除權息", "2382廣達除息6.0元", "🔥重要")],
    "2026-07-13": [("除權息", "3231緯創除息2.6元", "重要")],
    "2026-07-14": [("除權息", "2308台達電除息5.2元", "重要")],
    "2026-07-15": [("台指期", "台指期月結算大震盪日", "🔥🔥重要"),
                   ("總經", "FOMC主席鮑爾國會聽證", "重要")],
    "2026-07-16": [("總經", "🇺🇸 美國6月CPI消費者物價指數", "🔥🔥🔥關鍵")],
    "2026-07-17": [("投信", "投信Q2季底結帳倒數洗盤", "🔥重要"),
                   ("總經", "🇺🇸 美國6月PPI", "重要")],
    "2026-07-20": [("法說", "🔥 2330台積電法說會（Q2財報+Q3展望）", "🔥🔥🔥關鍵")],
    "2026-07-21": [("法說", "🔥 2454聯發科法說會", "🔥重要")],
    "2026-07-22": [("法說", "2317鴻海法說會", "重要")],
    "2026-07-23": [("法說", "1301台塑法說會｜2308台達電法說會", "重要")],
    "2026-07-27": [("除權息", "🔥🔥🔥 2330台積電除息3.5元（加權蒸發28點）", "🔥🔥🔥關鍵")],
    "2026-07-28": [("總經", "🔥🔥🔥 FOMC利率決策會議（7/28~7/29）", "🔥🔥🔥關鍵"),
                   ("總經", "投信季底作帳最後一週", "🔥重要")],
    "2026-07-29": [("總經", "🔥🔥🔥 FOMC利率公佈", "🔥🔥🔥關鍵"),
                   ("除權息", "2002中鋼除息1.2元", "注意")],
    "2026-07-30": [("總經", "🇺🇸 美國Q2 GDP初值", "🔥🔥重要"),
                   ("投信", "投信季底結帳倒數2天", "🔥重要")],
    "2026-07-31": [("投信", "🔥🔥🔥 投信季底結帳日", "🔥🔥🔥關鍵"),
                   ("總經", "🇺🇸 美國6月PCE核心通膨", "🔥🔥🔥關鍵")],
    # ═══════════════════ 8月 ═══════════════════
    "2026-08-03": [("除權息", "2408南亞科除息", "重要")],
    "2026-08-05": [("除權息", "3042晶技除息", "注意"),
                   ("總經", "🇺🇸 美國7月ISM服務業PMI", "🔥重要")],
    "2026-08-06": [("除權息", "3034聯詠除息9.0元", "重要")],
    "2026-08-07": [("總經", "🔥🔥🔥 美國7月非農就業+失業率", "🔥🔥🔥關鍵")],
    "2026-08-10": [("財報", "📅 全市場7月營收公告截止", "🔥重要")],
    "2026-08-12": [("法說", "3661世芯-KY法說會", "注意")],
    "2026-08-13": [("總經", "🔥🔥🔥 美國7月CPI", "🔥🔥🔥關鍵")],
    "2026-08-14": [("台指期", "台指期月結算", "🔥重要")],
    "2026-08-20": [("總經", "FOMC 7月會議紀要公布", "注意"),
                   ("除權息", "2379瑞昱除息", "注意")],
    "2026-08-27": [("總經", "🔥 傑克森霍爾全球央行年會（鮑爾談話）", "🔥重要")],
    # ═══════════════════ 9月 ═══════════════════
    "2026-09-01": [("財報", "📅 全市場8月營收公告截止", "重要")],
    "2026-09-03": [("除權息", "3037欣興除息", "注意")],
    "2026-09-16": [("總經", "🔥🔥🔥🔥 FOMC利率決策（含點陣圖）", "🔥🔥🔥🔥關鍵"),
                   ("總經", "FOMC會議9/16~9/17", "🔥🔥🔥🔥關鍵")],
    "2026-09-18": [("台指期", "台指期月結算", "🔥重要")],
    "2026-09-24": [("投信", "🔥🔥 投信Q3季底作帳白熱化", "🔥🔥重要")],
    "2026-09-30": [("投信", "🔥🔥🔥 投信季底結帳最後交易日", "🔥🔥🔥關鍵"),
                   ("台指期", "富時台灣指數季度調整生效日", "🔥🔥🔥關鍵")],
}

def get_future_events(days=14):
    """回傳未來14天的事件清單"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for date_str, event_list in KNOWN_EVENTS_2026.items():
        d = datetime.strptime(date_str, "%Y-%m-%d")
        diff = (d - today).days
        if 0 <= diff <= days:
            for etype, name, impact in event_list:
                events.append({"date": date_str, "days": diff, "type": etype, "name": name, "impact": impact})
    events.sort(key=lambda x: x["days"])
    return events

# ═══════════════════════════════════════════════
#  第三維度：台美產業聯動牆（40組完整版）
# ═══════════════════════════════════════════════
from us_tw_mapping_matrix import LINKAGE_40

# 轉換成 symbol -> info 格式，方便用美股代號查詢
LINKAGE_MAP = {}
for gid, info in LINKAGE_40.items():
    for us_sym, us_name in info["us"]:
        tw_codes = [c for c, n in info["tw"]]
        tw_names = {c: n for c, n in info["tw"]}
        LINKAGE_MAP[us_sym.upper()] = {
            "name": us_name,
            "tw_sectors": [info["sector"]],
            "tw_stocks": tw_codes,
            "tw_names": tw_names,
            "desc": info["desc"],
            "group": gid,
        }

def get_us_stock_change(symbol):
    """用yfinance抓美股單日漲跌幅，失敗則回傳 None（完全靜默，不印任何垃圾）"""
    try:
        import yfinance as yf
        # 全面壓制 yfinance 的 stderr 垃圾訊息
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            t = yf.Ticker(symbol)
            df = t.history(period="5d")
        if df is not None and len(df) >= 2:
            closes = df["Close"].values
            change = (closes[-1] / closes[-2] - 1) * 100
            return round(change, 2), round(closes[-1], 2)
    except Exception:
        pass
    return None, None

def check_linkage():
    """檢查所有連動美股的漲跌幅，回傳警報"""
    alerts = []
    for symbol, info in LINKAGE_MAP.items():
        change, close = get_us_stock_change(symbol)
        if change is not None:
            # 漲跌超過2%就發警報
            level = "🔴🔴" if abs(change) >= 4 else ("🔴" if abs(change) >= 2 else "🟢")
            direction = "暴漲" if change > 0 else "暴跌"
            if abs(change) >= 2:
                alerts.append({
                    "symbol": symbol,
                    "name": info["name"],
                    "change": change,
                    "close": close,
                    "level": level,
                    "direction": direction,
                    "sectors": info["tw_sectors"],
                    "tw_stocks": info["tw_stocks"],
                    "desc": info["desc"],
                })
    return alerts


# ═══════════════════════════════════════════════
#  🚀 主輸出
# ═══════════════════════════════════════════════
NM = {"2436":"偉詮電","2337":"旺宏","5351":"鈺創","3673":"TPK-KY","3711":"日月光",
      "4958":"臻鼎-KY","3042":"晶技","2454":"聯發科","2317":"鴻海",
      "3443":"創意","3661":"世芯","3035":"智原","3231":"緯創","2382":"廣達",
      "3017":"奇鋐","2451":"創見","8150":"南茂","2344":"華邦電","6770":"力積電",
      "6207":"雷科","2327":"國巨","3090":"日電貿","6139":"亞翔",
      "2049":"上銀","1536":"和大","3008":"大立光","2408":"南亞科"}

def generate_weather_section():
    """產出完整的大盤天氣區塊"""
    lines = []
    
    # ── 美股四大指數 ──
    us = get_us_indexes()
    lines.append("🇺🇸【美股收盤】")
    for name, data in us.items():
        arrow = "🔺" if data["change"] > 0 else "🔻" if data["change"] < 0 else "➖"
        lines.append("  %s: %.0f %s%+.2f%%" % (name, data["close"], arrow, data["change"]))
    
    # 費半特別標示
    if "費城半導體" in us:
        sox = us["費城半導體"]
        sox_icon = "🔥" if sox["change"] > 2 else ("⚠️" if sox["change"] < -2 else "➖")
        lines.append("  %s 費半波動%.1f%% → 直接影響台股半導體族群開盤" % (sox_icon, sox["change"]))
    
    # ── 台指期夜盤 ──
    fut = get_taiwan_futures()
    if fut:
        arrow = "🔺" if fut["change"] > 0 else "🔻" if fut["change"] < 0 else "➖"
        lines.append("")
        lines.append("🇹🇼【台指期夜盤】%.0f %s%+.2f%%" % (fut["close"], arrow, fut["change"]))
        if fut["change"] > 0.5:
            lines.append("  夜盤上漲 → 今日台股有望跳空開高 ✅")
        elif fut["change"] < -0.5:
            lines.append("  夜盤下跌 → 今日台股可能開低洗盤 ⚠️")
        else:
            lines.append("  夜盤平穩 → 今日正常開盤 ➖")
    
    # ── 未來14天事件 ──
    lines.append("")
    lines.append("📅【未來14天關鍵事件】")
    events = get_future_events()
    if events:
        for e in events[:10]:
            days_str = "今天" if e["days"] == 0 else "明天" if e["days"] == 1 else "%d天後" % e["days"]
            icon = "🔥" if "關鍵" in e["impact"] else "⭐" if "重要" in e["impact"] else "📌"
            lines.append("  %s %s | %s %s" % (icon, e["date"], days_str, e["name"]))
    
    # ── 台美產業聯動 ──
    lines.append("")
    lines.append("🔗【台美產業聯動警報】")
    alerts = check_linkage()
    if alerts:
        for a in alerts:
            stocks_str = ", ".join(["%s(%s)"%(NM.get(s,s),s) for s in a["tw_stocks"] if s in NM])
            lines.append("  %s %s %s %+.2f%% → %s" % (a["level"], a["name"], a["direction"], a["change"], stocks_str))
    else:
        lines.append("  目前無顯著連動警報（美股波動<2%）")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print()
    print("🌤【全球聯動與總經氣象台】")
    print("-"*60)
    print(generate_weather_section())
