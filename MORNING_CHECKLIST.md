# 🦞 小龍蝦晨報系統 — 開機記憶卡（完整版）
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
2. 測試：產一次晨報（`python src/sj_trading/daily_web_report.py`）
3. 上傳：`git push origin main --force`
4. 更新 MORNING_CHECKLIST.md 記錄
5. git push 上傳 MORNING_CHECKLIST.md

---

## ⏰ 自動排程（cron，已設定好）
| 時間 | 任務 | 腳本 |
|:---:|:---|:---|
| 08:30 | 🦞 產晨報 + git push + 啟動盤中監控 | daily_web_report.py |
| 16:30 | 🏦 全市場投信掃描 + 更新晨報 + git push | daily_market_update.py → daily_web_report.py |
| 08:30~13:30 | 📊 盤中每5分KD金叉監控 | day_engine_v2.py |

---

## 📊 19檔持股

### 第1層（核心持倉）
2436偉詮電、2337旺宏、5351鈺創、3673 TPK-KY、3711日月光、
4958臻鼎-KY、3042晶技、2454聯發科、2317鴻海

### 第2層（潛力股）
3443創意、3661世芯、3035智原、3231緯創、2382廣達、
3017奇鋐、2451創見、8150南茂、2344華邦電、6770力積電

### 輔助
2330台積電

**要修改持股 → 改這兩個檔案：**
- `src/sj_trading/daily_web_report.py` → `CORE_19` 變數
- `src/sj_trading/daily_market_update.py` → `watch_19` 變數

---

## 🏦 投信掃描（全市場）
- **必須抓 TWSE T86 全市場**，不能只掃 watchlist
- 每天16:30自動跑 `daily_market_update.py`
- 腳本: `src/sj_trading/daily_market_update.py`
- 篩選: 連買 >= 3天，總額 > 50萬
- 輸出: `output/trust_scan_latest.json`

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

### ⚠️ 每日必須先更新 database 再跑晨報
FinMind API 每天盤後更新。CSV 過期會讓 KD 用舊資料算，金叉判斷不準。
**晨報流程第一步先跑：**
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

### 手動重跑回測
```
cd C:\Users\User\.openclaw\workspace\sj-trading
python -X utf8 src\sj_trading\kd_backtest.py
```

---

## 📝 晨報流程（完整正確版）

### 08:30 晨報產出
```
0. python src/sj_trading/download_all_3y.py  ← 先更新 database，否則KD用舊資料
1. python src/sj_trading/daily_web_report.py
   - Shioaji 永豐API → 19檔即時報價
   - database/*_3y.csv → KD/RSI/支撐（每檔參數不同，讀 kd_params.json）
   - output/SITC_Accumulation.csv → 股本滲透率
   - global_weather → SOX(費半) + 台指期即時指數 → 開盤基調
   - morning_news → 鉅亨網新聞（過濾中國）
   - 組裝 HTML → web/index.html
2. git push → GitHub Pages 更新
3. 啟動 day_engine_v2.py → 盤中監控
```

### 16:30 盤後更新
```
1. python src/sj_trading/daily_market_update.py
   - TWSE T86 全市場投信資料
   - 輸出 trust_scan_latest.json
2. python src/sj_trading/daily_web_report.py
3. git push
```

---

## 🧠 永遠記住的事
1. **每天08:30前產出晨報** → git push 上傳
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
