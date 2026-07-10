# 🦞 小龍蝦晨報系統 — 開機記憶卡（完整版）
# ⚠️ 每次重啟後，先讀這個檔案！全部設定都在這裡。

## 📍 專案位置
```
C:\Users\User\.openclaw\workspace\sj-trading\
```

## 🔐 重要金鑰在哪裡
- **GitHub Token** → `.env` 檔案（`GITHUB_TOKEN=***）
- **永豐金 API** → `.env`（`SJ_API_KEY`, `SJ_SEC_KEY`）
- **Git**: `D:\StableDiffusion\Git\bin\git.exe`（PATH已加，打 `git` 可用）
- **GitHub Pages**: https://tarotmei168.github.io/sj-trading/

## ✅ 上傳 GitHub Pages 的正確方式

### 方法A：Git Push（推薦，最快）
```
cd C:\Users\User\.openclaw\workspace\sj-trading
git add -A
git commit -m "更新說明"
git push origin main --force
```
注意：remote URL 已設好含 token，直接 push 即可。

### 方法B：upload.py（備援）
```
cd C:\Users\User\.openclaw\workspace\sj-trading\web
python upload.py
```

### 每改完東西後一定要做的事
1. ✅ 本地修改完成
2. ✅ 測試：產一次晨報（`python src\sj_trading\daily_web_report.py`）
3. ✅ 上傳：`git push origin main --force`
4. ✅ 更新 MORNING_CHECKLIST.md 記錄
5. ✅ git push 上傳 MORNING_CHECKLIST.md

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
- `src\sj_trading\daily_web_report.py` → `CORE_19` 變數
- `src\sj_trading\daily_market_update.py` → `watch_19` 變數

---

## 🏦 投信掃描（正確的全市場方式）
- **必須抓 TWSE T86 全市場**，不能只掃 watchlist
- 每天16:30自動跑 `daily_market_update.py`
- 腳本位置: `src\sj_trading\daily_market_update.py`
- 篩選: 連買 ≥ 3天，總額 > 50萬
- 輸出: `output\trust_scan_latest.json`

---

## 📰 新聞（鉅亨網 API）
- API: `https://news.cnyes.com/api/v3/news/category/{分類}`
- 分類: `us_stock`(美股)、`tw_stock`(台股)、`tech`(科技)、`tw_macro`(台灣總經)
- **中國新聞全面過濾**（中國、北京、港股、中概、華為、中芯等）
- 腳本: `src\sj_trading\morning_news.py`
- 標記規則:
  - ⭐ 漲價 / 缺料 / 營收創高 / EPS / 股利 / 三率三升 / 訂單 / 虧轉盈 / 轉機
  - 🔴 川普 / 關稅 / 聯準會 / 制裁
  - 🟠 半導體 / AI / 法說 / 財報 / 除息

---

## 📊 KD 黃金交叉（本地資料 + 回測）
- **每檔股票 KD 參數不同**，不能全部用同一組
- 資料源：`database\` 下的各股 3年日K線 CSV
- 本地離線計算 → `src\sj_trading\calc_tech.py`（含 KD、RSI、支撐）
- 30分K的黃金交叉 → `src\sj_trading\kd_30min_monitor.py`
- 每檔股票的 KD 參數是經過回測優化的

---

## 📝 晨報流程（完整正確版）

### 08:30 晨報產出
```
1. python src\sj_trading\daily_web_report.py
   ├── Shioaji 永豐API → 19檔即時報價
   ├── database/*_3y.csv → KD/RSI/支撐（每檔不同參數）
   ├── output/SITC_Accumulation.csv → 股本滲透率
   ├── global_weather → SOX(費半) + 台指期即時指數 → 開盤基調
   ├── morning_news → 鉅亨網新聞（過濾中國）
   └── 組裝 HTML → web/index.html
2. git push → GitHub Pages 更新
3. 啟動 day_engine_v2.py → 盤中監控
```

### 16:30 盤後更新
```
1. python src\sj_trading\daily_market_update.py
   ├── TWSE T86 全市場投信資料
   ├── 輸出 trust_scan_latest.json
2. python src\sj_trading\daily_web_report.py
3. git push
```

---

## 🧠 永遠記住的事
1. **每天08:30前產出晨報** → git push 上傳
2. **投信資料要掃全市場**，不只 watchlist
3. **新聞只留台股+美股**，過濾中國
4. **KD 用本地資料回測**，每檔參數不同
5. **上傳用 git push**（含 token 的 remote URL 已設好）
6. **永豐金 API 在 .env**
7. **漲跌統一用 +/-**

---

## ✅ 歷史記錄
### 2026-07-10（全部已上傳 GitHub）
- [x] Git 裝好 + PATH + remote URL 含 token
- [x] 投信掃描改全市場（daily_market_update.py）
- [x] 新聞引擎（morning_news.py，鉅亨網 API）
- [x] SOX + 台指期雙指數（daily_web_report.py + global_weather.py）
- [x] 股價催化劑標籤（⭐漲價/缺料/營收創高）
- [x] Cron 更新（08:30 + 16:30）
- [x] MORNING_CHECKLIST.md 完整版
- [x] CHANGELOG_2026-07-10.md
- [x] git push 確認成功
