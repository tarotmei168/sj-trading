# 🦞 小龍蝦晨報系統 — 開機記憶卡
# 每次重啟先讀這個檔案，就知道全部設定

## 📍 專案位置
C:\Users\User\.openclaw\workspace\sj-trading\

## 🔐 重要金鑰
- GITHUB_TOKEN → 在 .env 檔裡面
- SJ_API_KEY / SJ_SEC_KEY → 也在 .env
- GIT 位置: D:\StableDiffusion\Git\bin\git.exe (PATH 已加，直接打 git)
- GitHub Pages: https://tarotmei168.github.io/sj-trading/

## ⏰ 自動排程（已用 cron 設定好）
| 時間 | 任務 | 腳本 |
|:---:|:---|:---|
| 08:30 | 產晨報 + 上傳 GitHub + 啟動盤中監控 | daily_web_report.py → upload.py |
| 16:30 | 全市場投信掃描 + 更新晨報 + 上傳 | daily_market_update.py → daily_web_report.py |
| 08:30~13:30 | 盤中每5分KD監控 | day_engine_v2.py + day_notify_sender.py |

## 🏦 投信掃描（已改為全市場）
- 之前 bug: 只掃 watchlist 30 檔
- 已修正: daily_market_update.py 抓 TWSE T86 全市場資料
- 輸出: output/trust_scan_latest.json（晨報可讀）
- 篩選條件: 連買 ≥ 3 天，總額 > 50 萬

## 📊 19檔持股
### 第1層（核心持倉）
2436偉詮電、2337旺宏、5351鈺創、3673 TPK-KY、3711日月光、
4958臻鼎-KY、3042晶技、2454聯發科、2317鴻海

### 第2層（潛力股）
3443創意、3661世芯、3035智原、3231緯創、2382廣達、
3017奇鋐、2451創見、8150南茂、2344華邦電、6770力積電

### 輔助
2330台積電（風向球）

## 🧠 永遠的規則
1. 每天08:30前一定要產出晨報 → 上傳到 GitHub Pages
2. 晨報要有：費半SOX、開盤基調、19檔技術面、未來事件、台美聯動、投信建倉
3. 投信資料要用 TWSE T86 API 抓，不是 watchlist 過濾
4. 永豐金 Shioaji API 在 .env 裡面，用來拿即時報價
5. git push 不行就用 upload.py（GitHub API）
6. 08:30~13:30 要開盤中監控

## ✅ 今天做的事（2026-07-10）
- [x] Git 裝好 (D:\StableDiffusion\Git\bin\git.exe)
- [x] GitHub Pages 上傳成功
- [x] 投信掃描改為全市場
- [x] daily_market_update.py 修正
- [x] daily_web_report.py git push 改用 git 命令
- [x] cron 更新（08:30 + 16:30）
