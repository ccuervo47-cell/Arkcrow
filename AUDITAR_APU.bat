@echo off
chcp 65001 >nul
title ARKCROW - Auditar APU (formato UNAD F-14-3-5)
cd /d "%~dp0"
set "PYTHONPATH=%~dp0nucleo"
set "PYTHONUTF8=1"
rem Uso: arrastre el Excel de APU (y opcionalmente el plano .dxf) sobre este archivo.
if "%~1"=="" (
  echo Arrastre el archivo Excel de APU sobre AUDITAR_APU.bat
  echo ^(opcional: arrastre tambien el plano .dxf al mismo tiempo^)
  pause
  exit /b 1
)
set "XLSX="
set "DXF="
for %%F in (%*) do (
  if /I "%%~xF"==".xlsx" set "XLSX=%%~fF"
  if /I "%%~xF"==".dxf" set "DXF=%%~fF"
)
if "%XLSX%"=="" (
  echo No recibi ningun archivo .xlsx
  pause
  exit /b 1
)
if "%DXF%"=="" (
  ".venv\Scripts\python.exe" -m arkcrow.auditor_unad "%XLSX%"
) else (
  ".venv\Scripts\python.exe" -m arkcrow.auditor_unad "%XLSX%" --dxf "%DXF%"
)
echo.
echo El reporte (.md) y el Excel de hallazgos quedaron en la misma carpeta del archivo auditado.
pause
