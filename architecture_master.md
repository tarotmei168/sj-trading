# 股票操盤雷達 — 全系統架構（最高執行準則）

> **最後更新：** 2026-07-21 晚間  
> **系統地位：** 這是本專案唯一正式架構文件，所有程式碼與排程皆以此為準。  

---

## 一、時程排程（硬性規則）

| 時間 | 任務 | 指令 |
|------|------|------|
| **08:30**  | **早報**產出 + Git Push | `daily_web_report.py` |
| **08:30~13:30** 📡 | 盤中30分K KD監控（每5分鐘）並且用PYTHON寫入本機0TOKEN | cron 啟動 |
| **16:30** 📊 | 全市場投信掃描 + 更新早報 + git push | `daily_market_update.py` → `daily_web_report.py` |

### 🚨 總經風控閾值

| 指標 | 閾值 | 行動 |
|------|------|------|
| 費半SOX (唯一關注指數) | >±3% | 開盤基調強烈標記 |
| 台指期 | 盤前08:45前後 | 開盤基調判斷 |

---

## 二、核心持股（11檔 + 潛力股）

### 🔒 第1層：核心持股（硬持倉，全部監控）KD/MACD/RSI/都用Tranding view的指標,這樣打開tranding view看圖時,看起來會是相同的
目標：抓 60 天 1 分 K 合成 30 分 K。
限制：單次只能抓 500 根、要用迴圈往前推。
安全：每次要 time.sleep(1.5) 避免被永豐金封鎖。

| | 名稱/下排股票代號 | 股價/下排股價漲跌 | 30日前最低股價 | KD(圖像化,下排說明狀態) | MACD,下排說明狀態 | RSI下排說明狀態 |策略
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 2337 | 旺宏 |  |
| 2330 | 台積電 |  |
| 2436 | 偉詮電 | |
| 5351 | 鈺創 |  |
| 3673 | TPK-KY | |
| 3711 | 日月光 |  |
| 4958 | 臻鼎-KY | |
| 3042 | 晶技 |  |
| 2454 | 聯發科 |  |
| 2317 | 鴻海 |  |
| 8150 | 南茂 |  |


### 🎯 第2層：潛力股（動態從全市場投信掃描載入）
每天 16:30 從 TWSE T86 全市場掃描，取非核心持股、投信買超20名
|  名稱/下排股票代號 | 股價/下排股價漲跌 | 30日前最低股價 |買超張數|買超天數| KD(圖像化,下排說明狀態) | MACD,下排說明狀態 | RSI下排說明狀態 |策略

---

## 三、數據源架構

### 🎯 Shioaji（即時報價 + PHTHON爬前60天30分K KD用Tranding view的規則來計算kd黃金交叉）
請在 KD 欄位加上一個**『迷你折線圖（SVG / Canvas Sparkline）』**。藍線 代表 $K$ 值走勢，橘線 代表 $D$ 值走勢。請將這兩條線畫在同一個小方格內，呈現兩條線交叉、向上或向下的走勢圖。保留文字標註：圖表旁邊繼續保留 🏹 低檔金叉 (K:10 / D:9) 的狀態文字。請幫我更新 index.html，讓 KD 欄位也能看到漂亮的 $K$ $D$ 雙線交叉走勢！」

MACD 欄位的顯示方式，用『視覺化的微型柱狀圖（Sparkline Bar Chart）』，規格如下：零軸基準線：圖表中間要有一條水平的 0 軸線。紅綠柱狀圖：數值 $> 0$（正數）：在 0 軸線上方顯示紅色柱狀體。數值 $< 0$（負數）：在 0 軸線下方顯示綠色柱狀體。5 天趨勢：水平排列顯示最近 5 期的柱狀高低變化，柱子高度請依數值大小自動縮放。提示文字：柱圖旁邊只需保留『最新當期的 Hist 數字』與『趨勢狀態（如：綠柱縮短 / 紅柱擴大）』即可，不需要再印出那串帶箭頭的歷史數字！請直接修改 index.html 的 CSS / JS 繪圖邏輯，讓 MACD 欄位呈現出真正的圖表視覺效果！」D 欄位』也加上視覺化的雙線走勢圖：後端資料（Python + TA-Lib）：請用 talib.STOCH() 計算出最近 5 期的 $K$ 值陣列與 $D$ 值陣列。前端繪圖（index.html）：


| 功能 | 說明 |
|------|------|
| 即時快照 `api.snapshots()` | 核心持股現價/漲跌/最高最低/成交量 |
| 歷史1分K `api.kbars()` | 每次14天，分79段拉取3年，合成30分K 用於歷史資料來回測最佳KD黃金交叉 |
| 開盤基調 `check_market_tone()` | 用台積電即時漲跌判斷 |
| **database/3y_kd/** | 每檔約6,500根30分K KD（3年回測用） |

### 🎯 新聞來源

| 來源 | 分類 | 過濾 |
|------|------|------|
| 鉅亨網 `news.cnyes.com` | us_stock, tw_stock, tech, tw_macro | 中國新聞全面過濾 |
| 標記規則 | ⭐漲價/營收/EPS ⚠️ 川普/關稅 🔵半導體/AI | — |
| 腳本 | `morning_news.py` |

### 🎯 技術指標（完全本機離線計算）

| 指標 | 計算方式 | 資料源 |
|------|---------|--------|
| KD | 30分K KD，每檔使用3年回測最佳K值 | `database/3y_kd/{sid}_kd.csv` |
| RSI | 日收盤價14期RSI | `database/3y_kd/{sid}_kd.csv` |
| 量能 | 當前量/前5根均量，<0.8=量縮 >1.5=放量 | 即時snapshot |
| MACD |  | — |

### 🎯 投信掃描

| 項目 | 說明 |
|------|------|
| 資料源 | TWSE T86 全市場 |
| 更新時間 | 每日16:30 |
| 腳本 | `daily_market_update.py` |
| 輸出 | `output/trust_scan_latest.json` |
| 篩選 | 連買≥3天, 總額>50萬 |

---

## 四、早報產出規則（daily_web_report.py）

### 📐 版型規範

| 項目 | 要求 |
|------|------|
| 字體 | **22px** 全頁統一 |
| 色系 | 深色模式（背景 #0d1117） |
| 指數 | **只留費半SOX + 台指期** |
| 響應式 | mobile-first（橫向表格，不做卡片） |

### 📊 必備區塊（由上到下）

1. **🇺🇸 費半SOX + 🇹🇼 台指期** — 開盤基調
2. **🔒 核心持股表格** — 代號/名稱/股價/KD(KD,MACD,RSI都用TRANDING VIEW 規則,並且圖像化)/MACD/RSI/策略（橫向表格）
3.**🎯 投信連買非持股（橫向表格，含/30日前最低股價/投信買超幾張/買超幾張/KD/MACD/RSI/策略）
   - 資料源: output/trust_scan_latest.json
   - 篩選: 連買≥3天+累計>50萬，按 total_trust 降序
 
4. **📅 未來14天台股進程** — 除息/法說/FOMC/季底
5. **🇺🇸 未來14天美股/總經關鍵事件** — 自動計算四物日 + 規則推算CPI/NFP/PPI/ISM + FOMC官網即時爬取
6. **🔗 台美產業聯動** — 美股波動影嚮台股連動的股票 美股>=2.5% 跟下跌5%高度相關台股半導體和電子股類的要排上去
7. **📰 股巿新聞** — 鉅亨網(過濾中國)

---

## 五、KD 黃金交叉策略（3年30分K KD回測）

### 參數說明

每檔股票獨立回測36種參數組合（K值5/9/14/21 × 成交量過濾 × KD位置過濾），
取總報酬+勝率加權最高的一組，寫入 `daily_web_report.py` 的 `KD3Y_PARAMS`。

### 策略判斷

| 條件 | 策略 |
|------|------|
| K金叉(gap>3) + RSI<60 | 🟢 K金叉 可持股 |
| 逼近金叉(gap>0) + RSI<50 | 🟡 近金叉 觀望期待 |
| 死叉(gap<-3) | 🔴 死叉中 避開 |
| RSI>70 | 🔴 RSI過熱 注意回檔 |
| RSI<30 + 金叉 | 🟢 RSI超賣+金叉 留意買點 |
| 其他 | ➖ 觀望 |

### 資料源

- **位置：** `database/3y_kd/{sid}_kd.csv`（每檔約6,500根30分K KD）
- **範圍：** 約2023-07 ~ 2026-07-21
- **腳本：** `download_3y_intraday_kd_v2.py`（高效版，每段100天，3年約11段）
- **回測腳本：** `bt_3y_kd_gc.py`
- **回測報告：** `output/bt_3y_kd_report.html`

### 新增核心持股 SOP
1. 把代號寫進 `CORE_19` + `KD3Y_PARAMS`（在 `daily_web_report.py`）
2. 跑 `download_3y_intraday_kd_v2.py` 抓3年資料（約2分鐘/檔）
3. 產早報確認 KD 正常
4. 更新 MEMORY.md 持股清單
5. ❌ 不准 git push，只放本機

---

## 六、GitHub 部署

| 項目 | 內容 |
|------|------|
| GitHub Pages | `https://tarotmei168.github.io/sj-trading/` |
| 發布方式 | `git push origin main --force`（只有主人說才上傳） |
| GITHUB_TOKEN | 寫在 `.env` |
| Git 路徑 | `D:\StableDiffusion\Git\bin\git.exe` |
| 根目錄同步 | push 前必須 `Copy-Item -Force web\index.html index.html` |

---

## 七、檔案組織

```
workspace/
├── MEMORY.md                   ← 主人偏好/工作模式/通訊頻道
├── MORNING_CHECKLIST.md        ← 開機記憶卡（完整設定）
├── HEARTBEAT.md                ← 復活指令
├── architecture_master.md      ← 本文件（最高準則）
├── test_qw.py / test_us_events.py / test_fed.html / test_bls_aug.html  ← 測試用暫存檔
├── SOUL.md / IDENTITY.md / USER.md / TOOLS.md / HEARTBEAT.md ← 開機設定
│
└── sj-trading/
    ├── web/
    │   └── index.html          ← 早報（GitHub Pages）
    ├── database/
    │   └── 3y_kd/              ← 11檔×6500根30分K KD
    ├── output/
    │   ├── trust_scan_latest.json   ← 投信掃描結果
    │   ├── SITC_Accumulation.csv    ← 投信買賣超累積
    │   ├── bt_3y_kd_report.html     ← 3年回測報告
    │   └── news_headlines.json      ← 新聞快取
    └── src/sj_trading/
        ├── daily_web_report.py      ← 早報產生器（主程式）
        ├── daily_market_update.py   ← 16:30 投信掃描
        ├── global_weather.py        ← 總經氣象台（SOX+台指期+事件）
        ├── morning_news.py          ← 新聞引擎（鉅亨網過濾中國）
        ├── calc_trust_rate.py       ← 股本滲透率
        ├── shioaji_helper.py        ← 永豐金API
        ├── us_tw_mapping_matrix.py  ← 台美聯動40組
        ├── day_engine_v2.py         ← 盤中監控引擎
        └── download_3y_intraday_kd.py / bt_3y_kd_gc.py  ← 3年KD回測
```

---

## 八、錯誤處理原則

1. **Shioaji 登入失敗** → 模擬模式（用本機CSV最後收盤價）
2. **Shioaji session cache** → 約5分鐘消退，舊key cache消退後即可用新key
3. **Git Push 失敗** → 只存檔，下次重試
4. **任何例外** → `try/except` 捕獲，不讓流程崩潰
5. **所有API Key** → 只在 `.env` 中，永不上傳GitHub

---

*本架構文件為小龍蝦系統最高執行準則。*
