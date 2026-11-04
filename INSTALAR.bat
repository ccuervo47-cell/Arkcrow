@echo off
chcp 65001 >nul
title ARKCROW OBRA - Instalacion
rem Ejecuta el instalador SOLO para este proceso (no cambia la politica de ejecucion del equipo).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
