# 🦞 小龍蝦早報系統 — 開機記憶卡（完整版）
# ⚠️ 每次重啟後，先讀這個檔案！全部設定都在這裡。

## 📍 專案位置
```
C:\Users\User\.openclaw\workspace\sj-trading\
```

## 🔐 重要金鑰在哪裡
- **GitHub Token** → `.env`（GITHUB_TOKEN）
- **永豐金 API** → `.env`（SJ_API_KEY, SJ_SEC_KEY）
- **Git**: `D:\StableDiffusion\Git\bin\git.exe`（PATH已加，打 `git` 可用）
- **GitHub Pages**: https://tarotmei168.github.io/sj-trading/

## ✅ 上傳 GitHub Pages 的方式

### 方法A：Git Push（推薦）
```
cd C:\Users\User\.openclaw\workspace\sj-trading
git add -A
git commit -m "更新說明"
git push origin main --force
```
remote URL 已設好含 token，直接 push 即可。

### 方法B：upload.py（備援）
```
cd C:\Users\User\.openclaw\workspace\sj-trading\web
python upload.py
```

### 每改完東西後一定要做的事
1. 本地修改完成
2. 測試：產一次早報（`python src/sj_trading/daily_web_report.py`）
3. 上傳：`git push origin main --force`
4. 更新 MORNING_CHECKLIST.md 記錄
5. git push 上傳 MORNING_CHECKLIST.md

---

## ⏰ 自動排程（cron，已設定好）
| 時間 | 任務 | 腳本 |
|:---:|:---|:---|
| 08:30 | 🦞 產早報（Shioaji 60天1分K→30分K→TA-Lib KD/MACD/RSI）+ git push + 啟動盤中監控 | ta_strategy_engine.py |
| 16:30 | 🏦 盤後更新（同引擎，重跑一次含富邦投信資料）+ git push | ta_strategy_engine.py |
| 08:30~13:30 | 📊 盤中每5分KD監控（含逼近金叉預警） | day_engine_v2.py |

---

## 📊 持股

### 第1層（核心持倉 12檔）
2436偉詮電、2337旺宏、5351鈺創、3673 TPK-KY、3711日月光、
4958臻鼎-KY、3042晶技、2454聯發科、2317鴻海、8150南茂、2330台積電、0050元大台灣50

### 第2層（潛力股 — 動態從富邦投信爬蟲載入）
每天 16:30 從富邦證券投信買超排行爬蟲，取前20名中非核心持股

**要修改核心持股 → 改這個檔案：**
- `src/sj_trading/ta_strategy_engine.py` → `CORE_19` 變數（在檔案開頭）

---

## 🏦 投信掃描（TWSE T86 證交所）
- **來源**: `https://www.twse.com.tw/fund/T86` 證交所投信買賣超 API（JSON）
- `ta_strategy_engine.py` 自動爬取，取投信買超前20名作為潛力股
- **穩定策略**: `requests.Session()` + 完整 HTTP 標頭 + 嘗試5個交易日 + 每日期重試3次
- **更新時間**: 證交所盤後 16:00 後才有資料，早盤執行只會出核心12檔
- **富邦爬蟲已全部刪除**（2026-07-23）

---

## 📰 新聞（鉅亨網 API）
- API: `https://news.cnyes.com/api/v3/news/category/{分類}`
- 分類: `us_stock`(美股)、`tw_stock`(台股)、`tech`(科技)、`tw_macro`(台灣總經)
- **中國新聞全面過濾**（中國、北京、港股、中概、華為、中芯等）
- 腳本: `src/sj_trading/morning_news.py`
- 標記規則:
  - ⭐ 漲價 / 缺料 / 營收創高 / EPS / 股利 / 三率三升 / 訂單 / 虧轉盈 / 轉機
  - 🔴 川普 / 關稅 / 聯準會 / 制裁
  - 🟠 半導體 / AI / 法說 / 財報 / 除息

---

## 📊 KD 黃金交叉（已完成每檔獨立回測）

### ⚠️ 每日必須先更新 database 再跑早報
FinMind API 每天盤後更新。CSV 過期會讓 KD 用舊資料算，金叉判斷不準。
**早報流程第一步先跑：**
```
python src/sj_trading/download_all_3y.py
```
現在已加 6770 力積電 + 2330 台積電進 download list。

### 本機資料（不要刪掉！）
```
C:\Users\User\.openclaw\workspace\sj-trading\database\
├── 2436_3y.csv  ← 726 天日K（約3年）
├── 2337_3y.csv  ← 726 天日K
├── 5351_3y.csv  ← 726 天日K
... 共 20 檔，每檔約 726 天
└── kd_params.json  ← 2026-07-10 已完成回測
```

### 腳本
- 回測引擎: `src/sj_trading/kd_backtest.py`
- 參數存檔: `database/kd_params.json`
- 資料源: `database/*_3y.csv`（本機3年日K，每檔726天）

### 每檔 KD 參數（已完成，獨立的）
```
2454 聯發科 K5/D5/RSV7  買K<30  停損4% 停利3%  勝率100.0%  ✅
3711 日月光 K5/D4/RSV12 買K<40  停損4% 停利5%  勝率88.9%  ✅
2382 廣達   K5/D5/RSV12 買K<45  停損3% 停利5%  勝率88.9%  ✅
3443 創意   K3/D5/RSV7  買K<30  停損4% 停利5%  勝率83.3%  ✅
5351 鈺創   K3/D4/RSV9  買K<30  停損4% 停利3%  勝率82.4%  ✅
8150 南茂   K2/D5/RSV5  買K<35  停損3% 停利3%  勝率76.9%  ✅
2330 台積電 K5/D5/RSV7  買K<50  停損3% 停利3%  勝率73.3%  ✅
3042 晶技   K4/D4/RSV5  買K<30  停損3% 停利5%  勝率70.0%  ✅
3661 世芯   K2/D4/RSV5  買K<30  停損4% 停利3%  勝率70.0%  ✅
2317 鴻海   K4/D3/RSV5  買K<35  停損4% 停利3%  勝率69.2%  ✅
3673 TPK   K3/D3/RSV5  買K<30  停損4% 停利5%  勝率68.8%  ✅
3017 奇鋐   K3/D4/RSV14 買K<35  停損4% 停利3%  勝率68.8%  ✅
3231 緯創   K5/D5/RSV7  買K<30  停損4% 停利3%  勝率66.7%  ✅
2451 創見   K4/D5/RSV12 買K<30  停損4% 停利5%  勝率63.6%  ✅
3035 智原   K5/D3/RSV14 買K<40  停損4% 停利3%  勝率61.8%  ✅
2436 偉詮電 K5/D5/RSV14 買K<50  停損2% 停利3%  勝率57.1%  ✅
2337 旺宏   K4/D5/RSV9  買K<30  停損3% 停利3%  勝率57.1%  ✅
2344 華邦電 K5/D5/RSV5  買K<30  停損2% 停利5%  勝率57.1%  ✅
4958 臻鼎   K5/D5/RSV9  買K<50  停損4% 停利5%  勝率52.2%  ✅
```

### ⚠️ 逼近金叉預警（2026-07-21 新增）
day_engine_v2.py 和 kd_30min_monitor.py 均已加入提前預警機制：
- **定義：** K < D，差距 ≤ 3.0，且 K 值比前一根上升（K 往上追）
- **盤中輸出：** 每支股票旁邊標 `⚠️逼近金叉!`
- **底部彙總：** 列出所有逼近金叉的股票、K/D值、差距、RSI位階
- **意義：** 不等真的金叉才通知，提前1~3根K棒預警

### 手動重跑回測
```
cd C:\Users\User\.openclaw\workspace\sj-trading
python -X utf8 src\sj_trading\kd_backtest.py
```

---

## 📝 早報流程（全新版 — ta_strategy_engine.py 統一引擎）

### 核心引擎：ta_strategy_engine.py（唯一入口）
**只有一個指令，Everything 自動搞定：**
```
python src/sj_trading/ta_strategy_engine.py
```

### 自動包含：
1. ✅ Shioaji 即時登入（SJ_API_KEY / SJ_SEC_KEY 從 .env 讀取）
2. ✅ 爬富邦主力買超排行（BS4，不用 Shioaji）
3. ✅ 爬富邦投信買超排行（BS4）
4. ✅ 下載 32 檔標的 60 天 1分K（分段14天/段，Shioaji）
5. ✅ 合併 30分K，過濾 09:00~13:30
6. ✅ TA-Lib 計算: STOCH(14,1,3) + MACD + RSI(14)
7. ✅ 輸出 today_signal.json + web/index.html
8. ✅ 數據防呆: K>50 不判定低檔金叉; K>80 標示高檔過熱
9. ⚠️ **注意：引擎跑完後不會自動 git push**，需手動或等 cron

### 08:30 cron 會做的事
```
0. python src/sj_trading/ta_strategy_engine.py  ← 18~30分
1. git add -A && git commit -m "YYMMDD 早報"
2. git push origin main --force
3. python src/sj_trading/core_intraday_kd_monitor.py --loop  ← 盤中監控
```

### 16:30 cron 會做的事
```
0. python src/sj_trading/ta_strategy_engine.py  ← 重跑一次含富邦投信
1. git push
```

### ⚡ 鐵則：每！次！開！啟！都！用 Python 抓即時數據！絕不用快取！
- 0 Token：全部 Python 本地用 TA-Lib 完成
- 不讀舊快取／資料庫／靜態檔案
- 只有 Shioaji 連線很慢時會卡（約18~30分鐘）

### 手動測試產早報
```
cd C:\Users\User\.openclaw\workspace\sj-trading
python src/sj_trading/ta_strategy_engine.py
```

### 根目錄 index.html 同步
- 根目錄 `index.html` 和 `web/index.html` 不同步會導致 GitHub Pages 顯示舊版
- `Copy-Item -Force web\index.html index.html` 手動同步
- cron 已經會自動同步，但手動測試後記得檢查

---

## 🧠 永遠記住的事
1. **每天08:30前產出早報** → git push 上傳
2. **投信資料要掃全市場**，不只 watchlist
3. **新聞只留台股+美股**，過濾中國
4. **KD 用本機 database/*_3y.csv 資料回測**，每檔參數不同，存 database/kd_params.json
5. **上傳用 git push**（含 token 的 remote URL 已設好）
6. **永豐金 API 在 .env**
7. **漲跌統一用 +/-**

---

## ✅ 歷史記錄
### 2026-07-10（全部已上傳 GitHub）
- [x] Git 裝好 + PATH + remote URL 含 token
- [x] 投信掃描改全市場（daily_market_update.py）
- [x] 新聞引擎（morning_news.py，鉅亨網 API，過濾中國新聞）
- [x] SOX + 台指期雙指數（daily_web_report.py + global_weather.py）
- [x] 股價催化劑標籤（⭐漲價/缺料/營收創高/轉機）
- [x] Kron 更新（08:30 + 16:30）
- [x] KD 黃金交叉回測（19檔獨立參數，用 database/*_3y.csv）
- [x] database/kd_params.json 參數存檔
- [x] MORNING_CHECKLIST.md 完整版
- [x] git push 確認成功

### 2026-07-21（🔥核心11檔30分K KD歷史資料庫 + 盤中即時監控）
- [x] `download_intraday_kd_data.py` — 用 Shioaji 分批下載核心11檔1分K，合併30分K/15分K，存 database/30min_kd/
- [x] `core_intraday_kd_monitor.py` — 盤中即時掃描，用本地歷史KD+即時1分K判斷金叉/死叉/逼近金叉
- [x] 已成功下載11檔各620根30分K KD資料
- [x] 14:49首次測試抓到: TPK金叉✅、鴻海死叉❌、偉詮電逼近死叉⚠️
- [x] 支援 --loop 循環監控模式

### 2026-07-22（🔥 ta_strategy_engine.py 統一引擎 + 富邦爬蟲）
- [x] `ta_strategy_engine.py` — 唯一量化核心引擎：Shioaji 60天1分K→30分K→TA-Lib KD/MACD/RSI
- [x] 0 Token：全部 Python 本地運算
- [x] 富邦爬蟲取代 TWSE T86 投信掃描
- [x] `fubon_force_crawler.py` — 富邦主力+投信買超排行爬蟲（requests + BS4）
- [x] 輸出 today_signal.json（精簡信號）+ web/index.html（完整早報）
- [x] 舊檔保留但不再呼叫: daily_web_report.py / daily_market_update.py / download_all_3y.py
- [x] cron 08:30/16:30 指令改為 ta_strategy_engine.py
- [x] MEMORY.md + MORNING_CHECKLIST.md 同步更新
