# 首次設定 GitHub 倉庫
Write-Host "=== 🦞 設定 GitHub 倉庫 ===" -ForegroundColor Cyan

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

# 如果沒有 git，提示安裝
$gitCheck = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCheck) {
    Write-Host "⚠️ 找不到 Git，正在安裝..." -ForegroundColor Yellow
    try {
        winget install --id Git.Git -e --source winget
        Write-Host "✅ Git 安裝完成，請重開終端機再執行此腳本" -ForegroundColor Green
        pause
        exit
    } catch {
        Write-Host "❌ 無法自動安裝 Git" -ForegroundColor Red
        Write-Host "請手動下載: https://git-scm.com/download/win" -ForegroundColor Yellow
        pause
        exit
    }
}

# 設定 Git 使用者
$userName = Read-Host "輸入 GitHub 使用者名稱 (預設: tarotmei168)"
if ([string]::IsNullOrWhiteSpace($userName)) { $userName = "tarotmei168" }

$userEmail = Read-Host "輸入 GitHub Email"
if ([string]::IsNullOrWhiteSpace($userEmail)) {
    Write-Host "⚠️ 需要 Email 才能送出 commits" -ForegroundColor Yellow
    pause
    exit
}

git config --global user.name $userName
git config --global user.email $userEmail
Write-Host "✅ Git 使用者設定完成" -ForegroundColor Green

# 初始化 repo
if (Test-Path ".git") {
    Write-Host "⚠️ .git 已存在，跳過初始化" -ForegroundColor Yellow
} else {
    git init
    Write-Host "✅ git init 完成" -ForegroundColor Green
}

# 複製 web 檔案到根目錄
Copy-Item ".\web\index.html" ".\index.html" -Force
Copy-Item ".\web\architecture.html" ".\architecture.html" -Force
Write-Host "✅ 複製 HTML 到根目錄" -ForegroundColor Green

# 加入 remote
$remoteCheck = git remote
if ($remoteCheck) {
    Write-Host "⚠️ remote 已存在: $remoteCheck" -ForegroundColor Yellow
} else {
    git remote add origin https://github.com/tarotmei168/sj-trading.git
    Write-Host "✅ remote 加入完成" -ForegroundColor Green
}

# 設定 Pages 用 main 分支
Write-Host ""
Write-Host "=== 🌐 下一步 ===" -ForegroundColor Cyan
Write-Host "1. 手動建立 GitHub repo: github.com/tarotmei168/sj-trading (不要勾選 README)" -ForegroundColor White
Write-Host "2. 執行: .\web\github_push.ps1" -ForegroundColor White
Write-Host "3. 到 GitHub repo Settings -> Pages -> 選 main branch / (root)" -ForegroundColor White
Write-Host "4. 等待 1-2 分鐘，訪問: https://tarotmei168.github.io/sj-trading/" -ForegroundColor White
Write-Host ""

pause
