@echo off
chcp 65001 >nul
title ARKCROW OBRA - consola
cd /d "%~dp0"
set "PYTHONPATH=%~dp0nucleo"
set "PYTHONUTF8=1"
set "OLLAMA_MODELS=%~dp0modelos\ollama"
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
".venv\Scripts\python.exe" -m arkcrow.chat
pause
