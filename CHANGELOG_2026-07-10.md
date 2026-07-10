# 🦞 小龍蝦系統 — 2026-07-10 完整改動記錄

## 📌 工作守則（以後每次改完都要做）
1. ✅ 本地修改完成
2. ✅ 產出一次晨報測試
3. ✅ 上傳到 GitHub Pages（`cd web && python upload.py`）
4. ✅ 更新 MORNING_CHECKLIST.md（把新東西記進去）
5. ✅ 上傳 MORNING_CHECKLIST.md 到 GitHub

---

## 🔧 改動1：Git 安裝 + 環境設定

### 背景
本機沒有 git，upload.py 用 GitHub API 上傳，但 git push 更快。

### 做了什麼
1. 安裝 Git 2.55.0 → `C:\Program Files\Git\bin\git.exe`
2. 原本 D槽已有 Git → `D:\StableDiffusion\Git\bin\git.exe`
3. 加到 PATH（打 `git` 就能用）
4. 設定 remote → `https://github.com/tarotmei168/sj-trading.git`
5. .gitignore 建立（排除 .env、*.pyc、*.csv、大log檔等）

### 問題
- shioaji.log 1.6GB 卡在 git 歷史裡 → filter-branch 清除後 force push 因 token 驗證問題卡住
- **解決方案：以後上傳用 `upload.py`（GitHub API），不用 git push**

### 路徑
```
Git: D:\StableDiffusion\Git\bin\git.exe
.env: C:\Users\User\.openclaw\workspace\sj-trading\.env
GitHub Pages: https://tarotmei168.github.io/sj-trading/
```

---

## 🔧 改動2：投信掃描改為全市場（最核心的改動）

### 背景
原本 `daily_market_update.py` 的 `update_sitc_accumulation()` 只掃 WATCH_STOCKS 30 檔：
```python
if sid not in watch_sids:  # ← 這行是 bug
    continue
```
導致大聯大(4,022萬)、英業達(2,477萬)、佳世達(3,108萬)等真正的投信大戶完全不會出現在晨報中。

### 做了什麼
1. `update_sitc_accumulation()` 改成全市場下載，不跳過任何股票
2. 新增 `output/trust_top50_today.txt` — 每天投信買超 TOP50
3. 重寫 `generate_candidates()`:
   - 抓最近5個交易日的 TWSE T86 全市場資料
   - 篩選：連買 ≥ 3 天，總額 > 50 萬
   - 輸出 `output/trust_scan_latest.json`（晨報可讀取）
   - 同時檢查19檔持股中被投信賣超的

### 路徑
```
腳本: src\sj_trading\daily_market_update.py
輸出: output\trust_scan_latest.json
輸出: output\Potential_Candidates.txt
輸出: output\trust_top50_today.txt
```

### 7/8 掃描結果摘要
| 持股 | 投信動向 | 金額 |
|:---|:---|---:|
| 緯創 3231 | ✅ 5天連買 | 2,513萬 |
| 南茂 8150 | ✅ 5天連買 | 1,276萬 |
| 廣達 2382 | ✅ 5天連買 | 1,155萬 |
| 鴻海 2317 | ✅ 4天連買 | 668萬 |
| 日月光 3711 | ✅ 5天連買 | 587萬 |
| 奇鋐 3017 | ✅ 5天連買 | 221萬 |
| 華邦電 2344 | ❌ 被賣超 | -549萬 |
| 臻鼎-KY 4958 | ❌ 被賣超 | -128萬 |

---

## 🔧 改動3：Git Push 改用 git 命令

### 背景
原本 `push_to_github()` 用 subprocess run git，但 git 不在 PATH 上。

### 做了什麼
1. 改用 `D:\StableDiffusion\Git\bin\git.exe` 絕對路徑
2. 自動複製 `web/index.html` 和 `web/architecture.html` 到根目錄

### 路徑
```
程式碼位置: src\sj_trading\daily_web_report.py → push_to_github() 函數
```

---

## 🔧 改動4：新聞引擎（morning_news.py）全新建立

### 背景
晨報新聞區塊完全空白，`global_weather.py` 沒有爬新聞。

### 做了什麼
1. 建立全新 `morning_news.py`（鉅亨網 Anue API）
2. 支援分類：`us_stock`（美股/國際）、`tw_stock`（台股）、`tech`（科技）、`tw_macro`（台灣總經）
3. 關鍵字標記系統：
   - ⭐ 漲價、缺料、營收創高、EPS、股利、三率三升、訂單、虧轉盈、轉機、熱門
   - 🔴 川普、關稅、聯準會、制裁
   - 🟠 半導體、AI、法說、財報、除息
4. 中國新聞過濾（中國/北京/港股/中概/華為/中芯等關鍵字自動跳過）
5. 把 news_html 參數傳入 `gen_html()` 顯示在晨報上

### 路徑
```
腳本: src\sj_trading\morning_news.py
快取: output\news_headlines.json
```

### 新聞顯示順序
1. 🌍 國際政治 × 總經大事（含川普/關稅/漲價等）
2. 🔥 股價催化劑（⭐漲價/缺料/營收創高/轉機）
3. 📊 台股重點
4. 🔬 科技產業

---

## 🔧 改動5：晨報指數區塊 — SOX + 台指期即時指數

### 背景
原本 SOX 指數是寫死的假數據，台指期完全沒有。

### 做了什麼
1. `global_weather.py` 的 `get_taiwan_futures_night()` 改名 `get_taiwan_futures()`，改抓當下即時報價
2. 支援多種資料源：Shioaji 永豐API → yfinance（1h K線→日K）
3. `daily_web_report.py` 的 `gen_html()` 加入兩個指數：
   - 🇺🇸 費城半導體 SOX → 美股收盤數據
   - 🇹🇼 台指期指數 → 當下即時報價（不區分日夜盤）
4. 漲跌統一用 `+` / `-` 表示

### 路徑
```
global_weather: src\sj_trading\global_weather.py → get_taiwan_futures()
晨報: src\sj_trading\daily_web_report.py → gen_html()
```

---

## 🔧 改動6：Cron 排程更新

### 做了什麼
1. **08:30 晨報 cron** — 更新為跑 `daily_web_report.py` + 上傳 GitHub
2. **16:30 盤後 cron** — 更新為跑 `daily_market_update.py` + `daily_web_report.py` + 上傳 GitHub

### 確認 cron 存在
```
openclaw cron list
```

---

## 📁 最終檔案架構

```
C:\Users\User\.openclaw\workspace\sj-trading\
├── .env                          ← 金鑰（GITHUB_TOKEN、SJ_API_KEY、SJ_SEC_KEY）
├── MORNING_CHECKLIST.md          ← 開機記憶卡（所有設定在這裡）
├── CHANGELOG_2026-07-10.md       ← 今天修改記錄（這個檔案）
├── .gitignore
├── index.html                    ← GitHub Pages 讀這個（自動從 web/ 複製）
├── architecture.html             ← 架構頁（自動從 web/ 複製）
│
├── web/
│   ├── index.html                ← 晨報本體
│   ├── architecture.html         ← 系統架構說明
│   └── upload.py                 ← 上傳腳本（cd web && python upload.py）
│
├── src/sj_trading/
│   ├── daily_web_report.py       ← 晨報產生器（主要）
│   ├── daily_market_update.py    ← 投信全市場掃描 + 基本面更新
│   ├── morning_news.py           ← 新聞引擎（鉅亨網 API）
│   ├── global_weather.py         ← SOX + 台指期 + 台美聯動
│   ├── calc_tech.py              ← KD/RSI 離線計算
│   ├── calc_trust_rate.py        ← 股本滲透率計算
│   ├── shioaji_helper.py         ← 永豐金 API 封裝
│   └── us_tw_mapping_matrix.py   ← 台美聯動矩陣40組
│
├── output/
│   ├── trust_scan_latest.json   ← 最新投信掃描（晨報讀這個）
│   ├── news_headlines.json      ← 最新新聞快取
│   ├── SITC_Accumulation.csv    ← 投信歷史資料
│   ├── Potential_Candidates.txt ← 潛力股清單
│   └── web_report.html          ← 晨報備份
│
└── database/                     ← 各股的 3 年日 K 線 CSV
```

## ⏰ 每天自動流程

### 08:30（交易日）
```
1. python src\sj_trading\daily_web_report.py
   ├── Shioaji 永豐API → 抓19檔即時報價（無API時→模擬模式）
   ├── 本機CSV → 算KD/RSI/支撐
   ├── output/SITC_Accumulation.csv → 算股本滲透率
   ├── global_weather → SOX + 台指期指數
   ├── morning_news.py → 鉅亨網新聞
   └── 組裝 HTML → web/index.html + output/web_report.html
2. cd web && python upload.py → GitHub Pages 更新
3. 啟動 day_engine_v2.py → 盤中監控
```

### 16:30（交易日）
```
1. python src\sj_trading\daily_market_update.py
   ├── TWSE T86 → 全市場投信買賣超
   ├── FinMind → 基本面（營收）
   └── output/trust_scan_latest.json
2. python src\sj_trading\daily_web_report.py
3. cd web && python upload.py
```
