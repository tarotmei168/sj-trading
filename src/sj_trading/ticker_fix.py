# -*- coding: utf-8 -*-
"""
============================================
 台股代碼自動校正機制 (Ticker Auto-Fix)
============================================
用法：
  from ticker_fix import get_yfinance_ticker, TICKER_MAP
  
  ticker = get_yfinance_ticker("2481")  # -> "2481.TW"
  ticker = get_yfinance_ticker("6435")  # -> "6435.TWO"
  
  或直接從 TICKER_MAP 查完整對照表
============================================
"""

# ── 完整台股代碼對照表（上市 .TW / 上櫃 .TWO）──
# 持續擴充中
TICKER_MAP = {
    # ===== 投顧老師清單 =====
    # ===== 投顧老師補充清單（含產業特徵）=====
    # 功率元件
    "2481": "2481.TW",   # 強茂 (上市, 車用二極體、低檔整理股)
    "8261": "8261.TW",   # 富鼎 (上市)
    "6435": "6435.TWO",  # 大中 (上櫃, MOSFET 指標、IC 設計)
    "5425": "5425.TWO",  # 台半 (上櫃, 車用二極體、橫盤打底股)
    
    # 面板封裝
    "2409": "2409.TW",   # 友達 (上市)
    "3481": "3481.TW",   # 群創 (上市)
    "8215": "8215.TW",   # 明碁材 (上市)
    "4960": "4960.TW",   # 誠美材 (上市)
    
    # 生技化工
    "1729": "1729.TW",   # 三晃 (上市)
    "6446": "6446.TW",   # 藥華藥 (上市)
    "1723": "1723.TW",   # 中華化 (上市)
    "1718": "1718.TW",   # 中纖 (上市)
    
    # 機器人
    "1536": "1536.TW",   # 和大 (上市)
    "4576": "4576.TW",   # 大銀微 (上市)
    "2049": "2049.TW",   # 上銀 (上市)
    "6215": "6215.TW",   # 和椿 (上市)
    
    # 六月營收亮眼
    "5289": "5289.TWO",  # 宜鼎 (上櫃, 工控記憶體、6月營收創高預期)
    "3260": "3260.TWO",  # 威剛 (上櫃, 記憶體模組、第三季補漲黑馬)
    "2059": "2059.TW",   # 川湖 (上市)
    "6535": "6535.TW",   # 穎威 (上市)
    
    # 軍工概念
    "8033": "8033.TW",   # 雷虎 (上市, 軍工無人機、題材概念股)
    "6207": "6207.TWO",  # 雷科 (上櫃, 被動元件設備、CoWoS/CPO材料隱藏版)
    
    # 軍工概念
    "8033": "8033.TW",   # 雷虎 (上市)
    "2637": "2637.TW",   # 長榮航太 (上市)
    "8399": "8399.TW",   # 晟田 (上市)
    "5371": "5371.TW",   # 中光電 (上市)
    
    # PCB
    "2383": "2383.TW",   # 台光電 (上市)
    "3189": "3189.TW",   # 景碩 (上市)
    "6213": "6213.TW",   # 聯茂 (上市)
    "8046": "8046.TW",   # 南電 (上市)
    
    # IC設計
    "3006": "3006.TW",   # 晶豪科 (上市)
    "6295": "6295.TW",   # 茂達 (上市)
    "6732": "6732.TWO",  # 昇佳 (上櫃)
    "6799": "6799.TWO",  # 來頡 (上櫃)
    
    # 投信認養
    "4433": "4433.TW",   # 大量 (上市)
    "2427": "2427.TW",   # 興勤 (上市)
    "1307": "1307.TW",   # 南亞 (上市)
    "6139": "6139.TW",   # 亞翔 (上市)
    
    # 先進封裝
    "6257": "6257.TW",   # 矽格 (上市)
    "6525": "6525.TW",   # 捷敏-KY (上市)
    "8131": "8131.TW",   # 福懋科 (上市)
    "8150": "8150.TW",   # 南茂 (上市)
    
    # 記憶體
    "2408": "2408.TW",   # 南亞科 (上市)
    "2337": "2337.TW",   # 旺宏 (上市)
    "2344": "2344.TW",   # 華邦電 (上市)
    "6770": "6770.TW",   # 力積電 (上市)
    
    # 矽晶圓
    "3707": "3707.TW",   # 漢磊 (上市)
    "3532": "3532.TW",   # 台勝科 (上市)
    "6182": "6182.TW",   # 合晶 (上市)
    "6488": "6488.TW",   # 環球晶 (上市)
    
    # 半導體設備
    "8028": "8028.TW",   # 昇陽半 (上市)
    "1717": "1717.TW",   # 長興 (上市)
    "5536": "5536.TW",   # 聖暉 (上市)
    "2467": "2467.TW",   # 志聖 (上市)
    
    # 矽光子
    "3163": "3163.TWO",  # 波若威 (上櫃)
    "4979": "4979.TWO",  # 華星光 (上櫃)
    "3105": "3105.TW",   # 穩懋 (上櫃) - 代碼3105雖是上櫃但yahoo用.TWO
    "3363": "3363.TWO",  # 上詮 (上櫃)
    
    # 被動元件
    "2463": "2463.TW",   # 蜜望實 (上市)
    "2327": "2327.TW",   # 國巨 (上市)
    "3090": "3090.TW",   # 日電貿 (上市)
    "2472": "2472.TW",   # 禾伸堂 (上市)
    
    # ===== 原監控清單 =====
    "2330": "2330.TW",   # 台積電
    "2454": "2454.TW",   # 聯發科
    "2317": "2317.TW",   # 鴻海
    "3711": "3711.TW",   # 日月光投控
    "3042": "3042.TW",   # 晶技
    "2344": "2344.TW",   # 華邦電
    "2337": "2337.TW",   # 旺宏
    "2436": "2436.TW",   # 偉詮電
    "3673": "3673.TW",   # TPK-KY
    "3706": "3706.TW",   # 神達
    "4958": "4958.TW",   # 臻鼎-KY
    "5351": "5351.TWO",  # 鈺創 (上櫃)
    "8150": "8150.TW",   # 南茂
    
    # ===== ASIC 清單 =====
    "3443": "3443.TW",   # 創意
    "3661": "3661.TW",   # 世芯-KY
    "3035": "3035.TW",   # 智原
    "3529": "3529.TW",   # 力旺
    "6643": "6643.TW",   # M31
    
    # ===== 擴充 =====
    "2303": "2303.TW",   # 聯電
    "2382": "2382.TW",   # 廣達
    "3231": "3231.TW",   # 緯創
    "2308": "2308.TW",   # 台達電
    "3008": "3008.TW",   # 大立光
    "2327": "2327.TW",   # 國巨
    "3017": "3017.TW",   # 奇鋐
    "3324": "3324.TW",   # 雙鴻
    "2421": "2421.TW",   # 建準
    "3131": "3131.TW",   # 弘塑
    "3583": "3583.TW",   # 辛耘
    "6187": "6187.TW",   # 萬潤
    "5469": "5469.TW",   # 進鵬
    "4979": "4979.TWO",  # 華星光 (上櫃)
    "3234": "3234.TWO",  # 光環 (上櫃)
    "3449": "3449.TW",   # 宜鼎 (另一個上市代號?)
    "6207": "6207.TWO",  # 雷科 (上櫃)
}


def get_yfinance_ticker(stock_id):
    """
    台股代碼自動校正機制
    - 先在對照表查詢
    - 查不到時先試 .TW，失敗再試 .TWO
    """
    stock_id = str(stock_id).strip()
    
    # 1. 如果在對照表中，直接回傳
    if stock_id in TICKER_MAP:
        return TICKER_MAP[stock_id]
    
    # 2. 如果已有 .TW 或 .TWO 後綴，直接回傳
    if stock_id.endswith(".TW") or stock_id.endswith(".TWO"):
        return stock_id
    
    # 3. 預設先試上市 .TW
    return f"{stock_id}.TW"


def try_alternate_ticker(stock_id):
    """
    如果 .TW 失敗，試 .TWO
    回傳 (ticker_str, 是否為上櫃)
    """
    stock_id = str(stock_id).strip()
    if stock_id.endswith(".TW"):
        return stock_id.replace(".TW", ".TWO"), True
    elif stock_id.endswith(".TWO"):
        return stock_id.replace(".TWO", ".TW"), False
    else:
        return f"{stock_id}.TWO", True


def download_with_fallback(sid, period="3y", interval="1d"):
    """
    自動嘗試上市櫃代碼下載 yfinance 資料
    回傳 (df, used_ticker)
    如果都失敗回傳 (None, None)
    """
    import yfinance as yf
    
    ticker_str = get_yfinance_ticker(sid)
    attempts = []
    
    # 先試對照表的
    attempts.append(ticker_str)
    
    # 再試另一種
    alt_ticker, _ = try_alternate_ticker(ticker_str)
    if alt_ticker != ticker_str:
        attempts.append(alt_ticker)
    
    for t in attempts:
        try:
            df = yf.Ticker(t).history(period=period, interval=interval)
            if df is not None and len(df) > 20:
                return df, t
        except:
            pass
    
    return None, None


# ── 合併投顧老師清單 + 原監控清單的完整 target_stocks ──
def get_all_target_stocks():
    """回傳 {中文名: "代號.TW/.TWO"} 完整對照"""
    # 名稱對照
    name_map = {
        "強茂": "2481.TW",
        "大中": "6435.TWO",
        "台半": "5425.TWO",
        "宜鼎": "5289.TWO",
        "威剛": "3260.TWO",
        "雷虎": "8033.TW",
        "雷科": "6207.TWO",
        "富鼎": "8261.TW",
        "友達": "2409.TW",
        "群創": "3481.TW",
        "明碁材": "8215.TW",
        "誠美材": "4960.TW",
        "三晃": "1729.TW",
        "藥華藥": "6446.TW",
        "中華化": "1723.TW",
        "中纖": "1718.TW",
        "和大": "1536.TW",
        "大銀微": "4576.TW",
        "上銀": "2049.TW",
        "和椿": "6215.TW",
        "川湖": "2059.TW",
        "穎威": "6535.TW",
        "長榮航太": "2637.TW",
        "晟田": "8399.TW",
        "中光電": "5371.TW",
        "台光電": "2383.TW",
        "景碩": "3189.TW",
        "聯茂": "6213.TW",
        "南電": "8046.TW",
        "晶豪科": "3006.TW",
        "茂達": "6295.TW",
        "昇佳": "6732.TWO",
        "來頡": "6799.TWO",
        "大量": "4433.TW",
        "興勤": "2427.TW",
        "南亞": "1307.TW",
        "亞翔": "6139.TW",
        "矽格": "6257.TW",
        "捷敏-KY": "6525.TW",
        "福懋科": "8131.TW",
        "南茂": "8150.TW",
        "漢磊": "3707.TW",
        "台勝科": "3532.TW",
        "合晶": "6182.TW",
        "環球晶": "6488.TW",
        "昇陽半": "8028.TW",
        "長興": "1717.TW",
        "聖暉": "5536.TW",
        "志聖": "2467.TW",
        "波若威": "3163.TWO",
        "華星光": "4979.TWO",
        "穩懋": "3105.TWO",
        "上詮": "3363.TWO",
        "蜜望實": "2463.TW",
        "國巨": "2327.TW",
        "日電貿": "3090.TW",
        "禾伸堂": "2472.TW",
    }
    return name_map


# ── 完整股票資訊字典（含產業特徵描述）──
STOCK_INFO = {
    # 功率元件
    "2481": {"name": "強茂",   "market": "上市", "suffix": ".TW",  "theme": "功率元件", "feature": "車用二極體、低檔整理股"},
    "8261": {"name": "富鼎",   "market": "上市", "suffix": ".TW",  "theme": "功率元件", "feature": ""},
    "6435": {"name": "大中",   "market": "上櫃", "suffix": ".TWO", "theme": "功率元件", "feature": "MOSFET 指標、IC 設計"},
    "5425": {"name": "台半",   "market": "上櫃", "suffix": ".TWO", "theme": "功率元件", "feature": "車用二極體、橫盤打底股"},
    # 面板封裝
    "2409": {"name": "友達",   "market": "上市", "suffix": ".TW",  "theme": "面板封裝", "feature": ""},
    "3481": {"name": "群創",   "market": "上市", "suffix": ".TW",  "theme": "面板封裝", "feature": ""},
    "8215": {"name": "明碁材", "market": "上市", "suffix": ".TW",  "theme": "面板封裝", "feature": ""},
    "4960": {"name": "誠美材", "market": "上市", "suffix": ".TW",  "theme": "面板封裝", "feature": ""},
    # 生技化工
    "1729": {"name": "三晃",   "market": "上市", "suffix": ".TW",  "theme": "生技化工", "feature": ""},
    "6446": {"name": "藥華藥", "market": "上市", "suffix": ".TW",  "theme": "生技化工", "feature": ""},
    "1723": {"name": "中華化", "market": "上市", "suffix": ".TW",  "theme": "生技化工", "feature": ""},
    "1718": {"name": "中纖",   "market": "上市", "suffix": ".TW",  "theme": "生技化工", "feature": ""},
    # 機器人
    "1536": {"name": "和大",   "market": "上市", "suffix": ".TW",  "theme": "機器人", "feature": ""},
    "4576": {"name": "大銀微", "market": "上市", "suffix": ".TW",  "theme": "機器人", "feature": ""},
    "2049": {"name": "上銀",   "market": "上市", "suffix": ".TW",  "theme": "機器人", "feature": ""},
    "6215": {"name": "和椿",   "market": "上市", "suffix": ".TW",  "theme": "機器人", "feature": ""},
    # 六月營收亮眼
    "5289": {"name": "宜鼎",   "market": "上櫃", "suffix": ".TWO", "theme": "六月營收亮眼", "feature": "工控記憶體、6月營收創高預期"},
    "3260": {"name": "威剛",   "market": "上櫃", "suffix": ".TWO", "theme": "六月營收亮眼", "feature": "記憶體模組、第三季補漲黑馬"},
    "2059": {"name": "川湖",   "market": "上市", "suffix": ".TW",  "theme": "六月營收亮眼", "feature": ""},
    "6535": {"name": "穎威",   "market": "上市", "suffix": ".TW",  "theme": "六月營收亮眼", "feature": ""},
    # 軍工概念
    "8033": {"name": "雷虎",   "market": "上市", "suffix": ".TW",  "theme": "軍工概念", "feature": "軍工無人機、題材概念股"},
    "2637": {"name": "長榮航太","market": "上市", "suffix": ".TW",  "theme": "軍工概念", "feature": ""},
    "8399": {"name": "晟田",   "market": "上市", "suffix": ".TW",  "theme": "軍工概念", "feature": ""},
    "5371": {"name": "中光電", "market": "上市", "suffix": ".TW",  "theme": "軍工概念", "feature": ""},
    # 雷科（被動元件設備）
    "6207": {"name": "雷科",   "market": "上櫃", "suffix": ".TWO", "theme": "被動元件設備", "feature": "被動元件設備、CoWoS/CPO材料隱藏版"},
}


def get_stock_info(stock_id):
    """回傳股票完整資訊 dict"""
    stock_id = str(stock_id).strip()
    if stock_id in STOCK_INFO:
        return STOCK_INFO[stock_id]
    return {"name": stock_id, "market": "未知", "suffix": "", "theme": "", "feature": ""}


if __name__ == "__main__":
    # 測試全部代碼
    print("=== 台股代碼自動校正機制測試 ===")
    print()
    
    failed = []
    for sid, expected in TICKER_MAP.items():
        actual = get_yfinance_ticker(sid)
        status = "✅" if actual == expected else "❌"
        if actual != expected:
            failed.append((sid, expected, actual))
    
    print(f"測試 {len(TICKER_MAP)} 筆代碼")
    if failed:
        print(f"失敗 {len(failed)} 筆:")
        for s, e, a in failed:
            print(f"  {s}: 預期 {e} 實際 {a}")
    else:
        print("全部正確 ✅")
    
    # 測試 yfinance 下載
    print()
    print("測試 yfinance 下載（取 3 檔樣本）:")
    for name, ticker in [("強茂", "2481.TW"), ("大中", "6435.TWO"), ("宜鼎", "5289.TWO")]:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            df = t.history(period="1mo")
            if df is not None and len(df) > 5:
                print(f"  {name} ({ticker}): ✅ {len(df)} 筆, 最近收盤 {float(df['Close'].iloc[-1]):.2f}")
            else:
                print(f"  {name} ({ticker}): ❌ 資料不足")
        except Exception as e:
            print(f"  {name} ({ticker}): ❌ {str(e)[:40]}")
