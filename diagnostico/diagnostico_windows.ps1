# ARKCROW OBRA - Diagnostico del equipo (SOLO LECTURA: no instala ni cambia nada)
# Uso: clic derecho > "Ejecutar con PowerShell". Copie el resultado y peguelo en el chat.
$ErrorActionPreference = "SilentlyContinue"
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
"=== SISTEMA ===";  "$($os.Caption) $($os.Version) ($($os.OSArchitecture))"
"=== CPU ===";      "$($cpu.Name) - $($cpu.NumberOfCores) nucleos / $($cpu.NumberOfLogicalProcessors) hilos"
"=== RAM ===";      "$ram GB"
"=== GPU ==="
Get-CimInstance Win32_VideoController | ForEach-Object { "$($_.Name) - VRAM reportada: $([math]::Round($_.AdapterRAM/1GB,1)) GB" }
if (Get-Command nvidia-smi) { nvidia-smi --query-gpu=name,memory.total --format=csv,noheader }
"=== DISCO ==="
Get-PSDrive -PSProvider FileSystem | ForEach-Object { "$($_.Name): libre $([math]::Round($_.Free/1GB,1)) GB" }
"=== PERMISOS ==="
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"Sesion con administrador: $admin"
"Politica de scripts: $(Get-ExecutionPolicy)"
"=== PROGRAMAS ==="
foreach ($c in "python","py","node","git","ollama","winget") { $p = Get-Command $c; if ($p) { "$c : $($p.Source)" } else { "$c : NO" } }
$office = Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*, HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Where-Object { $_.DisplayName -match "Microsoft (365|Office)|Revit" } | Select-Object -ExpandProperty DisplayName -Unique
"Office/Revit: $($office -join '; ')"
"=== RED ==="
"Proxy WinHTTP: $(netsh winhttp show proxy | Select-String 'Proxy|Direct')"
"Proxy usuario: $((Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings').ProxyServer)"
"Acceso a ollama.com: $((Test-NetConnection ollama.com -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded)"
"Acceso a huggingface.co: $((Test-NetConnection huggingface.co -Port 443 -WarningAction SilentlyContinue).TcpTestSucceeded)"
Read-Host "Listo. Presione Enter para cerrar"
