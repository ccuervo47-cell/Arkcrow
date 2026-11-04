# =====================================================================================
#  ARKCROW OBRA - Instalador para Windows (nivel de usuario, SIN permisos de administrador)
#  - Detecta el hardware y elige el modelo local automaticamente.
#  - Pide confirmacion antes de cada instalacion o descarga grande.
#  - No cambia antivirus, firewall ni politicas del sistema.
#  - Todo queda dentro de esta carpeta (recomendado: C:\ArkcrowObra).
#  Ejecutar con doble clic en INSTALAR.bat
# =====================================================================================
# "Continue": en PowerShell 5.1, "Stop" aborta cuando un programa (pip, python, ollama) escribe en stderr.
# Los pasos criticos revisan $LASTEXITCODE o el resultado explicitamente.
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
$Raiz = $PSScriptRoot
Set-Location $Raiz
$Log = Join-Path $Raiz "instalacion.log"
Start-Transcript -Path $Log -Append | Out-Null

function Titulo($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "  [OK] $t" -ForegroundColor Green }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }
function Falla($t)  { Write-Host "  [X] $t" -ForegroundColor Red }
function Confirmar($pregunta) {
    $r = Read-Host "  $pregunta (S/N)"
    return ($r -match '^[sSyY]')
}
function Descargar($url, $destino) {
    Write-Host "  Descargando $url ..."
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $destino -UseBasicParsing
}

Write-Host "ARKCROW OBRA - Instalacion" -ForegroundColor Cyan
Write-Host "Carpeta: $Raiz"
if ($Raiz -match ' ') { Aviso "La ruta tiene espacios. Se recomienda C:\ArkcrowObra para evitar problemas." }

# ------------------------------------------------------------------ 1. Hardware
Titulo "1. Revisando el equipo"
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$vram = 0
$nvsmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvsmi) {
    try {
        $mb = (& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | Select-Object -First 1).Trim()
        $vram = [math]::Round([double]$mb / 1024, 1)
    } catch { $vram = 0 }
}
$unidad = (Get-Item $Raiz).PSDrive.Name
$disco = [math]::Round((Get-PSDrive $unidad).Free / 1GB, 1)
$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name
Ok "Windows: $((Get-CimInstance Win32_OperatingSystem).Caption)"
Ok "CPU: $cpu"
Ok "RAM: $ram GB   GPU NVIDIA: $(if ($vram) { "$vram GB" } else { 'no' })   Libre en ${unidad}: $disco GB"
if ($esAdmin) { Aviso "Esta sesion tiene permisos de administrador; no se necesitan. Todo se instala para el usuario." }

# Proxy corporativo: se usa solo durante esta instalacion (no se cambia la configuracion del sistema)
try {
    $ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    if ($ie.ProxyEnable -eq 1 -and $ie.ProxyServer) {
        $p = $ie.ProxyServer; if ($p -notmatch '://') { $p = "http://$p" }
        $env:HTTPS_PROXY = $p; $env:HTTP_PROXY = $p
        [System.Net.WebRequest]::DefaultWebProxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials
        Ok "Proxy corporativo detectado: $p (solo para esta instalacion)"
    }
} catch { }

# ------------------------------------------------------------------ 2. Python
Titulo "2. Python (motor de los calculos)"
function Probar-Python($exe, $args0) {
    try {
        $v = & $exe @args0 -c "import sys;print('%d.%d' % sys.version_info[:2]) if sys.version_info>=(3,10) else print('viejo')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^3\.\d+$') { return $v }
    } catch { }
    return $null
}
$PyExe = $null; $PyArgs = @()
$propio = Join-Path $Raiz "python\python.exe"
foreach ($c in @(@($propio, @()), @('py', @('-3.12')), @('py', @('-3.11')), @('py', @('-3')), @('python', @()))) {
    $cmd = Get-Command $c[0] -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch 'WindowsApps') {
        $v = Probar-Python $c[0] $c[1]
        if ($v) { $PyExe = $c[0]; $PyArgs = $c[1]; Ok "Python $v encontrado ($($cmd.Source))"; break }
    }
}
if (-not $PyExe) {
    Aviso "No hay Python 3.10 o superior."
    if (Confirmar "Instalar Python 3.12 SOLO para su usuario dentro de $Raiz\python (≈ 25 MB, sin administrador)?") {
        $inst = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
        Descargar "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" $inst
        $proc = Start-Process $inst -PassThru -ArgumentList @("/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0",
            "Include_test=0", "Shortcuts=0", "AssociateFiles=0", "TargetDir=$Raiz\python")
        $proc.WaitForExit()
        $PyExe = $propio; $PyArgs = @()
        if (-not (Probar-Python $PyExe $PyArgs)) { Falla "No se pudo instalar Python. Pida a TI 'Python 3.12 para usuario'."; Stop-Transcript; exit 1 }
        Ok "Python instalado en $Raiz\python"
    } else { Falla "Sin Python no se puede continuar."; Stop-Transcript; exit 1 }
}

# ------------------------------------------------------------------ 3. Modelo segun el hardware
Titulo "3. Eligiendo el modelo local"
$planJson = & $PyExe @PyArgs (Join-Path $Raiz "herramientas\elegir_modelo.py") --ram $ram --vram $vram --disco $disco --json
$plan = ($planJson -join "") | ConvertFrom-Json
if (-not $plan.principal) { Falla "No se pudo elegir el modelo: $planJson"; Stop-Transcript; exit 1 }
Ok $plan.razon
foreach ($a in $plan.avisos) { Aviso $a }
Write-Host "  Modelos: principal $($plan.principal), respaldo $($plan.respaldo), embeddings $($plan.embed), voz whisper-small"
Write-Host "  Descarga total aproximada: $($plan.descarga_gb) GB (una sola vez; despues funciona sin internet)"

# ------------------------------------------------------------------ 4. Entorno de Python y librerias
Titulo "4. Librerias de Python (entorno aislado .venv)"
$Venv = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $Venv)) {
    & $PyExe @PyArgs -m venv (Join-Path $Raiz ".venv")
    if (-not (Test-Path $Venv)) { Falla "No se pudo crear el entorno .venv"; Stop-Transcript; exit 1 }
}
& $Venv -m pip install --upgrade pip --quiet --disable-pip-version-check
Write-Host "  Descargando librerias (≈ 300 MB). Puede tardar 5 a 15 minutos; no cierre la ventana..." -ForegroundColor Yellow
& $Venv -m pip install -r (Join-Path $Raiz "requirements.txt") --disable-pip-version-check --progress-bar on
if ($LASTEXITCODE -ne 0) { Falla "pip no pudo instalar las librerias (revise proxy/firewall con TI)."; Stop-Transcript; exit 1 }
Ok "Librerias instaladas (≈ 300 MB)"
$env:PYTHONPATH = Join-Path $Raiz "nucleo"

# ------------------------------------------------------------------ 5. Ollama (motor de IA local)
Titulo "5. Ollama (motor de IA local)"
$OllamaExe = $null
foreach ($c in @((Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"), "ollama")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $OllamaExe = $cmd.Source; break }
}
if (-not $OllamaExe) {
    if (Confirmar "Instalar Ollama para su usuario (≈ 1 GB, sin administrador)?") {
        $inst = Join-Path $env:TEMP "OllamaSetup.exe"
        Write-Host "  (≈ 1 GB, sin barra de avance: puede tardar varios minutos)" -ForegroundColor Yellow
        Descargar "https://ollama.com/download/OllamaSetup.exe" $inst
        # OJO: no usar -Wait: en PowerShell espera tambien a la app de Ollama que el instalador deja abierta (se cuelga).
        $proc = Start-Process $inst -PassThru -ArgumentList @("/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES")
        $proc.WaitForExit()
        $OllamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (-not (Test-Path $OllamaExe)) { Falla "Ollama no quedo instalado. Si TI bloquea instaladores, pida 'Ollama para usuario'."; Stop-Transcript; exit 1 }
        Ok "Ollama instalado"
    } else { Aviso "Sin Ollama el asistente funciona en modo 'solo busqueda' (sin redactar respuestas)." }
}
if ($OllamaExe) {
    # Los modelos se guardan DENTRO de ArkcrowObra (respaldables). Variable de usuario, no del sistema.
    $Modelos = Join-Path $Raiz "modelos\ollama"
    New-Item -ItemType Directory -Force -Path $Modelos | Out-Null
    [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $Modelos, "User")
    $env:OLLAMA_MODELS = $Modelos
    Get-Process "ollama app", "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Process $OllamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
    Ok "Ollama en marcha (modelos en $Modelos)"

    # -------------------------------------------------------------- 6. Descarga de modelos
    Titulo "6. Modelos de IA"
    $pedidos = @($plan.principal, $plan.respaldo, $plan.embed) | Select-Object -Unique
    if (Confirmar "Descargar $($pedidos -join ', ') (≈ $([math]::Round($plan.descarga_gb - 0.5, 1)) GB)? Hagalo con buena conexion") {
        foreach ($m in $pedidos) {
            Write-Host "  ollama pull $m"
            & $OllamaExe pull $m
            if ($LASTEXITCODE -eq 0) { Ok "$m listo" } else { Falla "No se pudo descargar $m" }
        }
    } else { Aviso "Puede descargarlos despues ejecutando de nuevo INSTALAR.bat" }
}

# ------------------------------------------------------------------ 7. Voz (Whisper local)
Titulo "7. Dictado de voz sin internet (Whisper)"
if (-not (Test-Path (Join-Path $Raiz "modelos\whisper-small"))) {
    if (Confirmar "Descargar el modelo de voz whisper-small (≈ 0,5 GB)?") {
        & $Venv -c "from arkcrow.voz import descargar_modelo; print(descargar_modelo())"
        if ($LASTEXITCODE -eq 0) { Ok "Modelo de voz listo" } else { Aviso "No se pudo descargar; la bitacora funciona igual por texto." }
    }
} else { Ok "Modelo de voz ya instalado" }

# ------------------------------------------------------------------ 8. Configuracion
Titulo "8. Configuracion (.env)"
& $Venv (Join-Path $Raiz "herramientas\configurar_env.py") "ARKCROW_MODELO=$($plan.principal)" `
    "ARKCROW_MODELO_RESP=$($plan.respaldo)" "ARKCROW_EMBED=$($plan.embed)" "ARKCROW_WHISPER=$Raiz\modelos\whisper-small"
Ok "Costo cero: la nube de pago queda apagada (ARKCROW_NUBE_DE_PAGO=no)."

# Motor para recalcular Excel (revisor de calidad)
$excel = $false
try { $x = New-Object -ComObject Excel.Application; $x.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($x); $excel = $true } catch { }
if ($excel) { Ok "Excel disponible: el revisor de calidad recalcula con Excel." }
elseif (Get-Command soffice -ErrorAction SilentlyContinue) { Ok "LibreOffice disponible para recalcular." }
else { Aviso "No hay Excel ni LibreOffice: el revisor de calidad no podra recalcular. Instale LibreOffice (portable sirve)." }

# ------------------------------------------------------------------ 9. Base de conocimiento y pruebas
Titulo "9. Indexando documentos y probando"
& $Venv -m arkcrow.db
& $Venv -m arkcrow.conocimiento indexar
Set-Location $Raiz
$res = & $Venv -m unittest discover tests 2>&1 | ForEach-Object { "$_" }
$res | Select-Object -Last 3 | ForEach-Object { Write-Host "  $_" }
& $Venv -m arkcrow.respaldo hacer

# ------------------------------------------------------------------ 10. Acceso directo
Titulo "10. Acceso directo"
try {
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "ARKCROW OBRA.lnk"))
    $lnk.TargetPath = Join-Path $Raiz "iniciar.bat"
    $lnk.WorkingDirectory = $Raiz
    $lnk.Save()
    Ok "Acceso directo 'ARKCROW OBRA' en el escritorio"
} catch { Aviso "No se pudo crear el acceso directo; use iniciar.bat" }

Titulo "LISTO"
Write-Host "  1. Doble clic en 'ARKCROW OBRA' (escritorio) o en iniciar.bat: se abre el chat en el navegador."
Write-Host "  2. PRUEBA SIN INTERNET: desconecte el Wi-Fi, abra ARKCROW OBRA y pregunte '¿Que AIU usa la empresa?'."
Write-Host "     Debe responder en menos de 30 s con la etiqueta [OFFLINE ...]."
Write-Host "  3. Registro de esta instalacion: $Log"
Stop-Transcript | Out-Null
