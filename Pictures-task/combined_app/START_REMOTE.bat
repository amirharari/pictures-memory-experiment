@echo off
title Encoding + Memory Test - Remote Launcher
cd /d "%~dp0"
echo Starting combined server with ngrok public URL...
"C:\Users\amirhar.RESLAB\AppData\Local\Programs\Python\Python311\python.exe" -u run_remote.py
pause
