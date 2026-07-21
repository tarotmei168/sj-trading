"""
晨報 v3.2 — 30分K核心持股+潛力精選
"""
import os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import shioaji as sj
import pandas as pd
import numpy as np

load_dotenv()
BASE = r"C:\Users\User\.openclaw\workspace\sj-trading"
now = datetime.now()
OUTPUT_FILE = os.path.join(BASE, f"{now.strftime('%m%d')}_晨報.html")

def login():
    api = sj.Shioaji(simulation=True)
    api.login(api_key=os.environ['SJ_API_KEY'], secret_key=os.environ['SJ_SEC_KEY'])
    return api

def get_all_30min(api, sids):
    """一次抓多支股票的30分K資料"""
    results = {}
    for sid in sids:
        try:
            contract = api.Contracts.Stocks[sid]
            end = datetime.now()
            start = end - timedelta(days=15)
            all_dfs = []
            seg_end = end
            while seg_end > start:
                seg_start = max(seg_end - timedelta(days=14), start)
                kbars = api.kbars(contract=contract, start=seg_start.strftime("%Y-%m-%d"), end=seg_end.strftime("%Y-%m-%d"))
                if len(kbars.ts)==0: break
                df = pd.DataFrame({"datetime":pd.to_datetime(kbars.ts),"open":kbars.Open,"high":kbars.High,"low":kbars.Low,"close":kbars.Close,"volume":kbars.Volume})
                all_dfs.append(df)
                seg_end = seg_start - timedelta(seconds=1)
            if all_dfs:
                min_df = pd.concat(all_dfs)
                min_df.drop_duplicates(subset=["datetime"],inplace=True)
                min_df.sort_values("datetime",inplace=True)
                min_df.set_index("datetime",inplace=True)
                df30 = min_df.resample("30min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
                if len(df30)>=15:
                    low_min = df30["low"].rolling(9).min()
                    high_max = df30["high"].rolling(9).max()
                    rsv = ((df30["close"]-low_min)/(high_max-low_min))*100
                    rsv = rsv.fillna(50)
                    k_vals,d_vals=[50]*9,[50]*9
                    for i in range(9,len(df30)):
                        k_new=(2/3)*k_vals[-1]+(1/3)*rsv.iloc[i]
                        d_new=(2/3)*d_vals[-1]+(1/3)*k_new
                        k_vals.append(k_new);d_vals.append(d_new)
                    df30["K"]=k_vals;df30["D"]=d_vals
                    df30["vol_ma5"]=df30["volume"].rolling(5).mean()
                    df30["vol_ratio"]=df30["volume"]/df30["vol_ma5"].replace(0,np.nan)
                    results[sid]=df30
        except: pass
    return results

# ---- 核心持股（手中有持股的） ----
CORE_HOLDINGS = [
    ("2436","\u5049\u8a66\u96fb","USB PD / IC\u8a2d\u8a08\uff08\u4e2d\u5c0f\u578b\u984c\u6750\u80a1\uff09\u80a1\u6027\u6d3b\u6f51","\u9ad8\u6a94\u9632\u5b88\uff0c\u4e0d\u7834\u7e8c\u62b1\n30\u5206K MA20\uff08\u7d0474.5~75\u5143\uff09\u70ba\u591a\u982d\u9632\u5b88\u9ede\uff0c\u5b88\u7a69\u5247\u6ce2\u6bb5\u7e8c\u62b1"),
    ("2337","\u65fa\u5b8f","NOR Flash \u8a18\u61b6\u9ad4\uff08\u6a19\u6e96\u666f\u6c23\u5faa\u74b0\u80a1\uff09\u9aa8\u6027\u6c89\u9583","\u975c\u5f8530\u5206K\u91d1\u53c9\u88dc\u91cf\uff0c\u57f7\u884c\u9ad8\u629b\u89e3\u5957\n\u591a\u55ae\u4fdd\u7559\uff0c\u975c\u5f8530\u5206K\u518d\u6b21\u91cf\u589e\u9ec3\u91d1\u4ea4\u53c9\u6642\u9022\u9ad8\u8abf\u7bc0"),
    ("3042","\u6676\u6280","\u77f3\u82f1\u5143\u4ef6\uff08\u80a1\u6027\u6eab\u548c\u4e4b\u7e3e\u512a\u80a1\uff09","\u9ad8\u6a94\u80cc\u96e2\uff0c\u56b4\u8a2d30\u5206K\u7834\u7dda\u505c\u5229\n\u56b4\u5b88\u4eca\u65e5\u5c3e\u76e4\u9577\u7d05\u68d2\u4f4e\u9ede\uff0c\u660e\u65e5\u82e5\u8dcc\u7834\u61c9\u7372\u5229\u4e86\u7d5050%"),
    ("5351","\u9213\u5275","\u5229\u57fa\u578bIC\u8a2d\u8a08/\u8a18\u61b6\u9ad4\uff08\u9ad8\u6d3b\u767c\u5ea6\u984c\u6750\uff09\u4e3b\u529b\u8272\u5f69\u91cd","\u56b4\u9632\u6bba\u591a\uff0c\u9632\u5b88\u7dca\u8cbc\u524d\u4f4e\n\u660e\u65e5\u65e9\u76e4\u82e5\u672a\u4f34\u96a8\u5927\u91cf\u885d\u904e\u4eca\u65e5\u9ad8\u9ede\u4e14\u968a\u5f8c\u7834\u5e95\uff0c\u591a\u55ae\u61c9\u51fa\u6e05"),
    ("2317","\u9d3b\u6d77","AI\u4f3a\u670d\u5668\u7d55\u5c0d\u6838\u5fc3/\u5927\u578b\u6b0a\u503c\u80a1\u6027\u6975\u5177\u97cc\u6027","\u8d85\u8ce3\u5340\u4e0d\u6bba\u4f4e\uff0c\u6e96\u5099\u5206\u6279\u52a0\u78bc\n\u6b7b\u53c9\u5e38\u70ba\u591a\u982d\u5047\u6454\uff0c\u975c\u5f8530\u5206K\u9996\u6839\u5e36\u91cf\u7d05K\u91d1\u53c9\u6642\u53f3\u5074\u4f4e\u63a5"),
    ("2454","\u806f\u767c\u79d1","IC\u8a2d\u8a08\u9f8d\u982d/\u9ad8\u50f9\u82af\u7247\u6838\u5fc3\u80a1\u5927\u6236\u8207\u5916\u8cc7\u638c\u63a7","\u7e8c\u62b1\u6ce2\u6bb5\uff0c\u4e0d\u88ab\u77ed\u7dda\u6b7b\u53c9\u5687\u8dd1\n\u65e5K\u591a\u982d\u6163\u6027(MA10\u3001MA20)\u6c92\u7834\uff0c\u591a\u55ae\u5805\u5b9a\u7e8c\u62b1"),
    ("8150","\u5357\u8302","\u9762\u677f/\u8a18\u61b6\u9ad4\u5c01\u6e2c\uff08\u666f\u6c23\u5faa\u74b0\u80a1\uff09\u5340\u959390~120","\U0001f3af50\u842c\u7b49\u9032\u5834\uff1a\u7dad\u6301\u56b4\u683c\u7b49\u5f85\n\u7b49\u8dcc\u523095-98\u5143\u5340\u9593\u4e1490\u5206K\u51fa\u73fe\u5e36\u91cf\u91d1\u53c9\u6642\u4e00\u64ca\u5fc5\u6bba"),
    ("4958","\u81fb\u9f0eKY","PCB\u5927\u5ee0\uff0c\u80a1\u6027\u7a69\u5065","\u8da8\u52e2\u504f\u591a\uff0cK<D\u4f46MACD\u67f1\u8ca0\uff0c\u91cf\u80fd\u840e\u7e2e\n\u9632\u5b8830\u5206K MA20\u7d04570\uff0c\u7b49\u91cf\u589e\u91d1\u53c9\u518d\u8003\u616e\u52a0\u78bc"),
    ("3673","TPKKY","PCB小而美，股性活潑","買氣93%超強，暫不需急賣\n今日K=81高檔死叉，注意回檔，防守75"),
   ("3711","\u65e5\u6708\u5149","\u5168\u7403\u5c01\u6e2c\u9f8d\u982d\uff0c\u6b0a\u503c\u80a1","K81\u8d85\u8cb7+RSI83\uff0c\u8ffd\u50f9\u529b\u9053\u76e4\u6574\n\u9ad8\u6a94\u6ce8\u610f\u56de\u6a94\uff0c\u5b88\u4eca\u65e5\u4f4e\u9ede680\uff0c\u8dcc\u7834\u6e1b\u78bc"),
]


# ---- 潛力波段 ----
# 這份清單為常見候選觀察名，實際第2層潛力股應依前一日16:30盤後投信買超結果動態更新。
POTENTIAL = [
    ("2330","台積電","中位區盤整+🔥爆量(2.6倍)","主力強力築底，今日爆量低點不破，任何拉回都是波段絕佳切入點"),
    ("4961","天鈺","偏高區+🔥爆量(1.89倍)","明日開盤15分內守穩165元則換手成功，標準順勢追擊標的"),
    ("6451","訊芯KY","中位區+🔴死叉(量縮)","空手等待回測500-510元整數關卡，止跌且出現大量金叉即是時機"),
    ("3532","台勝科","中位區+🟢金叉(量正常)","底部成形，金叉可信度高，適合第一筆波段試單"),
    ("2327","國巨","超賣區(KD=16.6)+💤量縮","等待30分K出現首根大量金叉，將引發強烈右側反彈"),
    ("8016","矽創","偏低區+✅量能回復","量能回升代表大戶暗中吸籌，30分K完成金叉即是高勝率第一買點"),
    ("2464","盟立","超賣區(KD=13.6)+💤量縮","股性極投機，極小資金左側埋伏，博取暴利反彈"),
]

# ---- 避開 ----
AVOID = [
    ("6139","亞翔","偏高區+🔴死叉","建廠設備飆股，高檔死叉動能轉弱，無持股切勿追高"),
    ("1303","南亞","高檔區+🔴死叉(量縮)","傳統塑化循環股，高檔量縮死叉是波段見頂訊號，應完全避開"),
    ("5425","台半","極高檔(KD=96.5)+💤量縮","K值96但成交量窒息，標準假突破，明日極易砸盤修正，空手絕不碰"),
]

def build_html():
    api = login()
    
    # 收集所有需要的股票代號
    all_sids = []
    for items in [CORE_HOLDINGS, POTENTIAL, AVOID]:
        for item in items:
            all_sids.append(item[0])
    
    data = get_all_30min(api, all_sids)
    api.logout()
    
    def get_info(sid):
        df = data.get(sid)
        if df is None or len(df)<12: return None
        last=df.iloc[-1]; prev=df.iloc[-2]
        k=round(last["K"],1); d=round(last["D"],1)
        kp=round(prev["K"],1); dp=round(prev["D"],1)
        price=round(last["close"],2)
        vol_r=round(last["vol_ratio"],2) if not pd.isna(last.get("vol_ratio",np.nan)) else 0
        
        sig="NONE"
        if kp<=dp and k>d: sig="GOLDEN"
        elif kp>=dp and k<d: sig="DEATH"
        
        k_pos=""
        if k>80:k_pos="高檔"
        elif k>60:k_pos="偏高"
        elif k>40:k_pos="中位"
        elif k>20:k_pos="偏低"
        else:k_pos="超賣"
        
        vol_s=""
        if vol_r>1.5:vol_s="🔥爆量"
        elif vol_r>0.8:vol_s="✅正常"
        else:vol_s="💤量縮"
        
        return {"price":price,"k":k,"d":d,"vol_r":vol_r,"vol_s":vol_s,"sig":sig,"k_pos":k_pos}
    
    html = f"""<!DOCTYPE html><html lang="zh-TW"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>晨報 {now.strftime('%m/%d')}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Microsoft JhengHei',sans-serif;background:#f0f2f5;padding:20px;color:#333}}
.container{{max-width:1300px;margin:0auto}}
.header{{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:25px 30px;border-radius:16px;margin-bottom:20px;border:1px solid #e0e0e0}}
.header h1{{font-size:24px}}
.header p{{opacity:.8;font-size:13px}}
.section{{background:#fff;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.3);border:1px solid #e0e0e0}}
.section h2{{font-size:17px;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #e0e0e0;color:#1a237e}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#f5f5f5;padding:8px 6px;text-align:left;font-weight:600;border-bottom:2px solid #e0e0e0;color:#666;font-size:11px;position:sticky;top:0}}
td{{padding:8px 6px;border-bottom:1px solid #f5f5f5;vertical-align:top}}
tr:hover{{background:#f8f9ff}}
.golden{{border-left:3px solid #2e7d32!important}}
.death{{border-left:3px solid #c62828!important}}
.normal{{border-left:3px solid #e0e0e0}}
.vol-up{{color:#2e7d32;font-weight:600}}
.vol-down{{color:#c62828}}
.price-up{{color:#2e7d32}}
.price-down{{color:#c62828}}
.k-high{{color:#c62828;font-weight:bold}}
.k-low{{color:#2e7d32;font-weight:bold}}
.nature{{font-size:11px;color:#666;line-height:1.5}}
.strategy{{font-size:11px;color:#1565c0;line-height:1.5}}
.footer{{text-align:center;padding:20px;color:#999;font-size:11px}}
.assist{{color:#999;font-size:10px}}
.sig-pos{{color:#2e7d32}}
.sig-neg{{color:#c62828}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600}}
.badge-buy{{background:#e8f5e9;color:#2e7d32}}
.badge-sell{{background:#ffebee;color:#c62828}}
.badge-hold{{background:#fff3e0;color:#e65100}}
.section-title-part1{{color:#2e7d32}}
.section-title-part2{{color:#1a237e}}
.section-title-avoid{{color:#c62828}}
</style></head><body>
<div class=container>
<div class=header><h1>📊 晨報系統 v3.2 — 30分K 核心持股與潛力精選</h1>
<p>{now.strftime('%Y/%m/%d %H:%M')} | 資料來源：永豐金 Shioaji API（即時0延遲）</p></div>
"""
    
    # === 第一部分：核心持股 ===
    html += f'<div class="section"><h2 class="section-title-part1">💼 第一部分：核心持股追蹤（手中持股防守、解套與區間操作）</h2>'
    html += '<p class="assist" style="margin-bottom:12px">此區專注於您目前的實際持股，著重於各別股票的「骨性」、支撐防守以及最大報酬或解套策略。</p>'
    html += '<table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>量能</th><th>訊號</th><th>專業骨性與操作指引</th><th>最大報酬/解套交易策略</th>'
    html += '</tr></thead><tbody>'
    
    for sid, name, nature, strategy in CORE_HOLDINGS:
        info = get_info(sid)
        if not info:
            html += f'<tr class="normal"><td><b>{name}</b><br><small>{sid}</small></td><td colspan="7" style="color:#999">無資料</td></tr>'
            continue
        
        sig_str = "⚪ 盤整無訊號"
        sig_mark = "normal"
        if info["sig"]=="GOLDEN":
            sig_str = "🟢 黃金交叉"; sig_mark = "golden"
        elif info["sig"]=="DEATH":
            sig_str = "🔴 30分K死叉"; sig_mark = "death"
        
        vol_cls = "vol-up" if info["vol_r"]>1 else ("vol-down" if info["vol_r"]<0.5 else "")
        k_cls = "k-high" if info["k"]>70 else ("k-low" if info["k"]<30 else "")
        
        nature_short = nature.replace("\n","<br>")
        strategy_short = strategy.replace("\n","<br>")
        
        html += f'<tr class="{sig_mark}"><td><b>{name}</b><br><small class=assist>{sid}</small></td>'
        html += f'<td class="price-up"><b>{info["price"]}</b></td>'
        html += f'<td class="{k_cls}">{info["k"]}/{info["d"]}</td>'
        html += f'<td>{info["k_pos"]}</td>'
        html += f'<td class="{vol_cls}">{info["vol_s"]}</td>'
        html += f'<td>{sig_str}</td>'
        html += f'<td class="nature">{nature_short}</td>'
        html += f'<td class="strategy">{strategy_short}</td></tr>'
    
    html += '</tbody></table></div>'
    
    # === 第二部分：潛力波段 ===
    html += f'<div class="section"><h2 class="section-title-part2">🚀 第二部分：潛力波段標的追蹤（尋找下一個高效益進場點）</h2>'
    html += '<table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>量能</th><th>狀態</th><th>操作策略</th>'
    html += '</tr></thead><tbody>'
    
    for sid, name, status, strategy in POTENTIAL:
        info = get_info(sid)
        if not info:
            html += f'<tr class="normal"><td><b>{name}</b><br><small class=assist>{sid}</small></td><td colspan="6" style="color:#999">無資料</td></tr>'
            continue
        
        vol_cls = "vol-up" if info["vol_r"]>1 else ("vol-down" if info["vol_r"]<0.5 else "")
        k_cls = "k-high" if info["k"]>70 else ("k-low" if info["k"]<30 else "")
        
        sig_str = "⚪ 盤整"
        if info["sig"]=="GOLDEN": sig_str = "🟢 金叉"
        elif info["sig"]=="DEATH": sig_str = "🔴 死叉"
        
        html += f'<tr class="golden"><td><b>{name}</b><br><small class=assist>{sid}</small></td>'
        html += f'<td class="price-up"><b>{info["price"]}</b></td>'
        html += f'<td class="{k_cls}">{info["k"]}/{info["d"]}</td>'
        html += f'<td>{info["k_pos"]}</td>'
        html += f'<td class="{vol_cls}">{info["vol_s"]}</td>'
        html += f'<td style="font-size:11px">{status}</td>'
        html += f'<td class="strategy">{strategy}</td></tr>'
    
    html += '</tbody></table></div>'
    
    # === 第三部分：避開 ===
    html += f'<div class="section"><h2 class="section-title-avoid">🔴 類別C：高檔多頭轉弱（拉回修正或避開）</h2>'
    html += '<table><thead><tr>'
    html += '<th>股票</th><th>股價</th><th>K/D</th><th>K位置</th><th>量能</th><th>狀態</th><th>原因</th>'
    html += '</tr></thead><tbody>'
    
    for sid, name, status, reason in AVOID:
        info = get_info(sid)
        if not info:
            html += f'<tr class="death"><td><b>{name}</b><br><small class=assist>{sid}</small></td><td colspan="6" style="color:#999">無資料</td></tr>'
            continue
        
        vol_cls = "vol-up" if info["vol_r"]>1 else ("vol-down" if info["vol_r"]<0.5 else "")
        k_cls = "k-high" if info["k"]>70 else ("k-low" if info["k"]<30 else "")
        
        html += f'<tr class="death"><td><b>{name}</b><br><small class=assist>{sid}</small></td>'
        html += f'<td class="price-down">{info["price"]}</td>'
        html += f'<td class="{k_cls}">{info["k"]}/{info["d"]}</td>'
        html += f'<td>{info["k_pos"]}</td>'
        html += f'<td class="{vol_cls}">{info["vol_s"]}</td>'
        html += f'<td style="font-size:11px">{status}</td>'
        html += f'<td class="strategy">{reason}</td></tr>'
    
    html += '</tbody></table></div>'
    
    # footer
    html += f'<div class="footer">晨報系統 v3.2 | {now.strftime("%Y/%m/%d %H:%M")} | 30分K使用Shioaji API即時資料，無延遲</div>'
    html += '</div></body></html>'
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {OUTPUT_FILE}")

if __name__ == "__main__":
    build_html()
