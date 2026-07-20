@echo off
title Encoding Task - Remote Launcher
cd /d "%~dp0"
echo Starting Encoding Task with ngrok public URL...
python -u run_remote.py
pause
