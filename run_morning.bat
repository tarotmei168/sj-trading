@echo off
cd /d C:\Users\User\.openclaw\workspace\sj-trading
"C:\Program Files\Python312\python.exe" -c "import sys; sys.path.insert(0,'src/sj_trading'); from daily_web_report import run; run()"
