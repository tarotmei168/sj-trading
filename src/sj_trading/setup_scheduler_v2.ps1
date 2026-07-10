$taskNameMorning = "LobsterMorning830"
$taskNameEvening = "LobsterEvening1630"
$python = "C:\Program Files\Python312\python.exe"
$script = "C:\Users\User\.openclaw\workspace\sj-trading\src\sj_trading\scheduler_cockpit.py"

# 用 WMI 方式建立排程（不需 admin 彈窗）
$svc = New-Object -ComObject Schedule.Service
$svc.Connect()

# 刪除舊任務
try { $svc.GetFolder("\").DeleteTask($taskNameMorning, 0) } catch {}
try { $svc.GetFolder("\").DeleteTask($taskNameEvening, 0) } catch {}

# --- 08:30 ---
$td = $svc.NewTask(0)
$td.RegistrationInfo.Description = "小龍蝦晨報 08:30 → 盤中監控"
$td.Principal.UserId = $env:USERNAME
$td.Principal.LogonType = 3  # S4U
$td.Principal.RunLevel = 1   # 最高權限

$trigger = $td.Triggers.Create(2)  # 每天
$trigger.DaysInterval = 1
$trigger.StartBoundary = [DateTime]::Now.AddMinutes(1).ToString("HH:mm")  # 測試用：1分鐘後觸發
# 正式：$trigger.StartBoundary = "08:30:00"

$action = $td.Actions.Create(0)
$action.Path = $python
$action.Arguments = "`"$script`""

$svc.GetFolder("\").RegisterTaskDefinition($taskNameMorning, $td, 6, $null, $null, 3)
Write-Host "✅ 已建立: $taskNameMorning"

# --- 16:30 ---
$td2 = $svc.NewTask(0)
$td2.RegistrationInfo.Description = "小龍蝦盤後更新 16:30"
$td2.Principal.UserId = $env:USERNAME
$td2.Principal.LogonType = 3
$td2.Principal.RunLevel = 1

$trigger2 = $td2.Triggers.Create(2)
$trigger2.DaysInterval = 1
$trigger2.StartBoundary = "16:30:00"

$action2 = $td2.Actions.Create(0)
$action2.Path = $python
$action2.Arguments = "`"$script`""

$svc.GetFolder("\").RegisterTaskDefinition($taskNameEvening, $td2, 6, $null, $null, 3)
Write-Host "✅ 已建立: $taskNameEvening"

Write-Host "`n📋 目前排程狀態："
schtasks /query /tn "$taskNameMorning" /fo LIST /v 2>&1 | Select-String "TaskName|Status|Schedule|Next Run"
Write-Host "---"
schtasks /query /tn "$taskNameEvening" /fo LIST /v 2>&1 | Select-String "TaskName|Status|Schedule|Next Run"
