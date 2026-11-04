@echo off
chcp 65001 >nul
title ARKCROW OBRA
cd /d "%~dp0"
set "PYTHONPATH=%~dp0nucleo"
set "PYTHONUTF8=1"
set "OLLAMA_MODELS=%~dp0modelos\ollama"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecute INSTALAR.bat
  pause
  exit /b 1
)
rem Arranca el motor local si no esta corriendo
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
  ) else (
    where ollama >nul 2>nul && start "" /min ollama serve
  )
  timeout /t 3 /nobreak >nul
)
rem Respaldo diario (solo si el ultimo tiene mas de 24 h)
".venv\Scripts\python.exe" -m arkcrow.respaldo si-toca
rem Abre el chat en el navegador (cierre esta ventana para salir)
".venv\Scripts\python.exe" -m arkcrow.web
if errorlevel 1 (
  echo.
  echo *** ARKCROW OBRA se cerro por un error. Tome una captura de esta ventana y enviela. ***
  pause
)
