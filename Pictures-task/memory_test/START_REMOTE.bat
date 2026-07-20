@echo off
title Memory Test - Remote Launcher
cd /d "%~dp0"
echo Starting Memory Test with ngrok public URL...
python -u run_remote.py
pause
