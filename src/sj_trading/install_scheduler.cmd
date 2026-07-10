@echo off
chcp 65001 >nul
echo ========================================
echo   🦞 小龍蝦排程安裝精靈
echo   請「以系統管理員執行」本批次檔
echo ========================================
echo.

:: 08:30 晨報 + 盤中監控
schtasks /create /tn "LobsterMorning830" /tr "'C:\Program Files\Python312\python.exe' 'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\scheduler_cockpit.py'" /sc daily /st 08:30 /ru %USERNAME% /rl highest /f

:: 16:30 盤後更新
schtasks /create /tn "LobsterEvening1630" /tr "'C:\Program Files\Python312\python.exe' 'C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\scheduler_cockpit.py'" /sc daily /st 16:30 /ru %USERNAME% /rl highest /f

echo.
echo ========================================
echo   ✅ 排程安裝完成！
echo   🕐 08:30  LobsterMorning830 — 晨報+盤中監控
echo   🕐 16:30  LobsterEvening1630 — 盤後更新
echo ========================================
echo.
pause
