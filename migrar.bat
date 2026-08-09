@echo off
chcp 65001 >nul 2>&1

cd /d "%~dp0"

"C:\Users\FZero\AppData\Local\Programs\Python\Python314\python.exe" migrator\run_pipeline.py

echo.
pause
