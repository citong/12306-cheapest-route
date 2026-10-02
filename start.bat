@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (py -3 scripts\launcher.py) || (python scripts\launcher.py)
pause
