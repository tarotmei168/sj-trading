# GitHub Push 腳本
# 用法: .\github_push.ps1 "更新訊息"

param(
    [string]$Message = "🦞 晨報更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $PSScriptRoot

Write-Host "=== 🦞 小龍蝦 GitHub Push ===" -ForegroundColor Cyan
Write-Host "目錄: $RepoDir"
Write-Host "訊息: $Message"
Write-Host ""

# 1. 複製 index.html & architecture.html 到根目錄（讓 GitHub Pages 可以直接看到）
Copy-Item "$PSScriptRoot\index.html" "$RepoDir\index.html" -Force
Write-Host "✅ 複製 index.html 到根目錄" -ForegroundColor Green
Copy-Item "$PSScriptRoot\architecture.html" "$RepoDir\architecture.html" -Force
Write-Host "✅ 複製 architecture.html 到根目錄" -ForegroundColor Green

# 2. Git 操作
try {
    Set-Location $RepoDir
    
    # 檢查是否有 .git
    if (-not (Test-Path ".git")) {
        Write-Host "⚠️ .git 不存在，初始化..." -ForegroundColor Yellow
        git init
        git remote add origin https://github.com/tarotmei168/sj-trading.git
        Write-Host "✅ Git 初始化完成" -ForegroundColor Green
    }
    
    # Add all
    git add -A
    Write-Host "✅ git add 完成" -ForegroundColor Green
    
    # Commit
    git commit -m $Message
    Write-Host "✅ git commit 完成" -ForegroundColor Green
    
    # Push
    git push -u origin main
    Write-Host "✅ git push 完成，已上傳到 GitHub!" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "🌐 GitHub Pages: https://tarotmei168.github.io/sj-trading/" -ForegroundColor Cyan
    Write-Host ""
}
catch {
    Write-Host "❌ 錯誤: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 如果第一次使用，請先執行：" -ForegroundColor Yellow
    Write-Host "  git config --global user.name ""你的GitHub帳號""" -ForegroundColor Yellow
    Write-Host "  git config --global user.email ""你的Email""" -ForegroundColor Yellow
    Write-Host "  然後再執行這個腳本" -ForegroundColor Yellow
}

Set-Location $PSScriptRoot
pause
