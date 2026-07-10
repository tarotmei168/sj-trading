# 🦞 設定 Windows 工作排程 — 小龍蝦自動晨報 + 盤中監控
# 以系統管理員身分執行：powershell -ExecutionPolicy Bypass .\setup_scheduler.ps1

$TaskNameMorning = "小龍蝦晨報 08:30"
$TaskNameAfternoon = "小龍蝦晨報 16:30"
$PythonPath = "C:\Program Files\Python312\python.exe"
$ScriptPath = "C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\scheduler_cockpit.py"
$WorkDir = "C:\Users\User\.openclaw\workspace\sj-trading"

# 刪除舊的任務（重新建立）
schtasks /delete /tn "$TaskNameMorning" /f 2>$null
schtasks /delete /tn "$TaskNameAfternoon" /f 2>$null

# 建立 08:30 晨報任務
schtasks /create /tn "$TaskNameMorning" `
    /tr "`"$PythonPath`" `"$ScriptPath`"" `
    /sc daily /st 08:30 `
    /ru "$env:USERNAME" `
    /rl highest `
    /f

# 建立 16:30 盤後更新任務
schtasks /create /tn "$TaskNameAfternoon" `
    /tr "`"$PythonPath`" `"$ScriptPath`"" `
    /sc daily /st 16:30 `
    /ru "$env:USERNAME" `
    /rl highest `
    /f

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  🦞 小龍蝦排程設定完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ 08:30 → 晨報產出 + 盤中 KD 監控"
Write-Host "  ✅ 16:30 → 盤後資料更新"
Write-Host "  🔗 盤中金叉/死叉自動 Git Push"
Write-Host "  🔗 投信滲透率變動自動 Git Push"
Write-Host "  📂 log: output\scheduler.log"
Write-Host "========================================" -ForegroundColor Cyan

# 立即測試
Write-Host "`n📡 執行立即測試（只跑晨報，不進盤中監控）..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath $PythonPath -ArgumentList "`"$ScriptPath`" --morning"
