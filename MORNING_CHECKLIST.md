# 🦞 小龍蝦晨報系統 — 開機記憶卡（完整版）
# ⚠️ 每次重啟後，先讀這個檔案！全部設定都在這裡。

## 📍 專案位置
```
C:\Users\User\.openclaw\workspace\sj-trading\
```

## 🔐 重要金鑰在哪裡
- **GitHub Token** → 在 `.env` 檔案（`GITHUB_TOKEN=ghp_...`）
- **永豐金 API** → 也在 `.env`（`SJ_API_KEY`, `SJ_SEC_KEY`）
- **Git 位置**: `D:\StableDiffusion\Git\bin\git.exe`（PATH已加，可直接打 `git`）
- **GitHub Pages**: https://tarotmei168.github.io/sj-trading/

## ⏰ 自動排程（已用 cron 設定好，不要手動刪掉）
| 時間 | 任務 | 執行什麼 |
|:---:|:---|:---|
| 🕐 **08:30** | 🦞 產晨報 + 上傳 GitHub + 啟動盤中監控 | daily_web_report.py → upload.py |
| 🕐 **16:30** | 🏦 全市場投信掃描 + 更新晨報 + 上傳 | daily_market_update.py → daily_web_report.py → upload.py |
| 🕐 **08:30~13:30** | 📊 盤中每5分KD金叉監控 | day_engine_v2.py + day_notify_sender.py |

## 📊 19檔持股完整清單

### 第1層（核心持倉 — 硬持倉）
| 代號 | 名稱 | 產業 |
|:---:|:---|:---|
| 2436 | 偉詮電 | USB-C/面板驅動IC |
| 2337 | 旺宏 | NOR Flash記憶體 |
| 5351 | 鈺創 | DRAM利基型記憶體 |
| 3673 | TPK-KY | 奈米銀觸控 |
| 3711 | 日月光投控 | 全球封測龍頭 |
| 4958 | 臻鼎-KY | FPC軟板 |
| 3042 | 晶技 | 石英元件/頻率元件 |
| 2454 | 聯發科 | 手機/ASIC晶片 |
| 2317 | 鴻海 | AI伺服器/電子代工 |

### 第2層（潛力股 — 右側等進場）
| 代號 | 名稱 | 產業 |
|:---:|:---|:---|
| 3443 | 創意 | ASIC/IP |
| 3661 | 世芯-KY | 高效能運算ASIC |
| 3035 | 智原 | ASIC/IP |
| 3231 | 緯創 | AI伺服器組裝 |
| 2382 | 廣達 | AI伺服器龍頭 |
| 3017 | 奇鋐 | 散熱模組 |
| 2451 | 創見 | 記憶體模組/Flash |
| 8150 | 南茂 | 驅動IC封裝 |
| 2344 | 華邦電 | DDR3/4/LPDDR記憶體 |
| 6770 | 力積電 | 成熟製程晶圓代工 |

### 輔助觀察
| 代號 | 名稱 | 作用 |
|:---:|:---|:---|
| 2330 | 台積電 | 大盤風向球 |

## 🏦 投信掃描（已改為全市場）
- ⚠️ 不要只掃 watchlist！要抓 **TWSE T86 全市場**資料
- 腳本: `src/sj_trading/daily_market_update.py`
- 篩選條件: 連買 ≥ 3 天，總額 > 50 萬
- 輸出: `output/trust_scan_latest.json`（晨報會讀這個）
- 時間: 每天16:30自動跑

## 📰 新聞資料源（鉅亨網 Anue API）
- API: `https://news.cnyes.com/api/v3/news/category/{分類}`
- 分類:
  - `us_stock` → 美股/國際（最優先）
  - `tw_stock` → 台股重點
  - `tech` → 科技產業
  - `tw_macro` → 台灣總經
- ⚠️ 中國新聞全面過濾（含中國/北京/上海/港股/中概/華為/中芯等關鍵字）
- 腳本: `src/sj_trading/morning_news.py`
- 標記規則:
  - ⭐ 股價催化劑：漲價、缺料、營收創高、EPS、股利、三率三升、訂單、虧轉盈、轉機、熱門
  - 🔴 政治/地緣：川普、關稅、聯準會、制裁
  - 🟠 產業大事：半導體、AI、法說、財報、除息

## 🧠 永遠的規則（不要忘記！）
1. **每天08:30前一定要產出晨報** → 上傳到 GitHub Pages
2. **晨報內容必須有**：費半SOX + 台指期指數（當下即時）→ 開盤基調、19檔技術面(KD/RSI/支撐)、未來14天事件、台美聯動、投信建倉、新聞
3. **投信資料**要用 TWSE T86 API 抓**全市場**，不是只掃 watchlist
4. **永豐金 Shioaji API** 在 `.env`，用來拿即時報價
5. **上傳方式**：`cd web && python upload.py`（用 GitHub API）
6. **Git 路徑**：`D:\StableDiffusion\Git\bin\git.exe`（或直接打 `git`）
7. **08:30~13:30** 要開盤中監控（day_engine_v2.py）
8. **新聞只留台股+美股**，過濾掉所有中國相關新聞
9. **漲跌統一用 +/-**，不用 emoji 圖示

## 🔧 常用操作指令

### 產晨報（手動跑）
```
cd C:\Users\User\.openclaw\workspace\sj-trading
python -X utf8 src\sj_trading\daily_web_report.py
```

### 上傳到 GitHub Pages
```
cd C:\Users\User\.openclaw\workspace\sj-trading\web
python upload.py
```

### 跑投信全市場掃描
```
cd C:\Users\User\.openclaw\workspace\sj-trading
python -X utf8 src\sj_trading\daily_market_update.py
```

### 修改持股清單
- 改 `daily_web_report.py` 裡的 `CORE_19` 變數
- 改 `daily_market_update.py` 裡的 `watch_19` 變數
- 改 `morning_news.py` 沒必要動
- 改完 → 跑一次晨報 → 上傳

### Git 相關
```
git add .
git commit -m "修改說明"
git push origin main
```

## ✅ 歷史記錄
### 2026-07-10
- [x] Git 裝好（D:\StableDiffusion\Git\bin\git.exe，PATH已加）
- [x] GitHub Pages 上傳成功（upload.py）
- [x] 投信掃描改為全市場（daily_market_update.py）
- [x] daily_web_report.py 修正：git push + 新聞 + SOX+台指期雙指數
- [x] morning_news.py 建立（鉅亨網 API，過濾中國新聞）
- [x] 股價催化劑標籤（⭐漲價/缺料/營收創高/轉機等）
- [x] cron 更新完畢（08:30晨報、16:30盤後）
- [x] MORNING_CHECKLIST.md 完整版建立
