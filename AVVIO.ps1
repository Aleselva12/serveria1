$ErrorActionPreference = "Stop"

trap {
    Write-Host ""
    Write-Host "ERRORE: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    Read-Host "Premi INVIO per chiudere questa finestra"
    exit 1
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend = Join-Path $Root "frontend"
$UiUrl = "http://127.0.0.1:5173"
$ApiHealthUrl = "http://127.0.0.1:8000/health"
$OllamaUrl = "http://127.0.0.1:11435"

function Test-Url($Url, $TimeoutSec = 2) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-Url($Url, $Seconds) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-HashText($Path) {
    if (-not (Test-Path $Path)) {
        return ""
    }
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Fail($Message) {
    Write-Host $Message -ForegroundColor Red
    Read-Host "Premi INVIO per chiudere questa finestra"
    exit 1
}

function Clear-StalePort($Port) {
    $Deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $Deadline) {
        $Connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $Connections) {
            return
        }
        foreach ($Connection in $Connections) {
            Write-Host "Trovato un processo sulla porta $Port (PID $($Connection.OwningProcess)), lo chiudo..." -ForegroundColor Yellow
            Stop-Process -Id $Connection.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }
}

function Stop-KnownProcess($PidFile) {
    if (Test-Path $PidFile) {
        $SavedPid = (Get-Content $PidFile -Raw).Trim()
        if ($SavedPid) {
            Stop-Process -Id $SavedPid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-TaggedWindows($Title) {
    Get-Process powershell -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -eq $Title } |
        ForEach-Object {
            Write-Host "Chiudo una vecchia finestra rimasta aperta ($Title)..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
}

$BackendWindowTitle = "CORA_BACKEND"
$FrontendWindowTitle = "CORA_FRONTEND"
$BackendPidFile = Join-Path $Root ".cora_backend.pid"
$FrontendPidFile = Join-Path $Root ".cora_frontend.pid"
$LockFile = Join-Path $Root ".avvio.lock"

Write-Host ""
Write-Host "=== AVVIO CORA ===" -ForegroundColor Cyan

if ((Test-Url $UiUrl) -and (Test-Url $ApiHealthUrl)) {
    Write-Host "Cora e' gia attiva. Apro l'interfaccia..." -ForegroundColor Green
    Start-Process $UiUrl
    exit 0
}

if (Test-Path $LockFile) {
    $LockPid = (Get-Content $LockFile -Raw).Trim()
    if ($LockPid -and (Get-Process -Id $LockPid -ErrorAction SilentlyContinue)) {
        Fail "AVVIO e' gia in corso in un'altra finestra. Aspetta che finisca prima di premere di nuovo il pulsante."
    }
}
Set-Content -Path $LockFile -Value $PID

try {

Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".env")) -and (Test-Path (Join-Path $Root ".env.example"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Creato .env da .env.example. Potrai personalizzarlo in seguito." -ForegroundColor Yellow
}

if (-not (Test-Url $OllamaUrl)) {
    Write-Host "Ollama non risponde. Controllo Docker..."

    $DockerReady = $false

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            docker info *> $null
            if ($LASTEXITCODE -eq 0) {
                $DockerReady = $true
            }
        } catch {
            $DockerReady = $false
        }
    }

    if (-not $DockerReady) {
        $DockerCandidates = @(
            (Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
            (Join-Path $Env:LOCALAPPDATA "Docker\Docker Desktop.exe")
        )

        $DockerDesktop = $DockerCandidates |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1

        if ($DockerDesktop) {
            Write-Host "Avvio Docker Desktop..."
            Start-Process $DockerDesktop

            for ($i = 0; $i -lt 45; $i++) {
                Start-Sleep -Seconds 1
                try {
                    docker info *> $null
                    if ($LASTEXITCODE -eq 0) {
                        $DockerReady = $true
                        break
                    }
                } catch {
                    $DockerReady = $false
                }
            }
        }
    }

    if ($DockerReady) {
        Write-Host "Avvio il container ia-ollama..."
        try {
            docker start ia-ollama | Out-Null
        } catch {
            Write-Host "Non riesco ad avviare ia-ollama automaticamente." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Docker non e' disponibile. Cora puo' aprirsi, ma il modello locale potrebbe restare offline." -ForegroundColor Yellow
    }

    if (-not (Wait-Url $OllamaUrl 25)) {
        Write-Host "Attenzione: Ollama non e' ancora raggiungibile su $OllamaUrl" -ForegroundColor Yellow
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$RequirementsStamp = Join-Path $Root ".cora_requirements.sha256"

if (-not (Test-Path $VenvPython)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Fail "Python non risulta installato o non e' nel PATH."
    }

    Write-Host "Creo l'ambiente Python .venv..."
    python -m venv .venv
}

$CurrentRequirementsHash = Get-HashText $Requirements
$SavedRequirementsHash = if (Test-Path $RequirementsStamp) {
    (Get-Content $RequirementsStamp -Raw).Trim()
} else {
    ""
}

if ($CurrentRequirementsHash -ne $SavedRequirementsHash) {
    Write-Host "Installo/aggiorno le dipendenze Python..."
    & $VenvPython -m pip install -r $Requirements --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) {
        Fail "Installazione dipendenze Python fallita."
    }
    Set-Content -Path $RequirementsStamp -Value $CurrentRequirementsHash
}

function Start-Backend {
    Stop-KnownProcess $BackendPidFile
    Stop-TaggedWindows $BackendWindowTitle
    Clear-StalePort 8000
    Write-Host "Avvio backend FastAPI..."
    $Process = Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "`$host.UI.RawUI.WindowTitle = '$BackendWindowTitle'; Set-Location '$Root'; & '$VenvPython' -m uvicorn api:app --host 127.0.0.1 --port 8000"
    ) -WindowStyle Minimized -PassThru
    Set-Content -Path $BackendPidFile -Value $Process.Id
}

if (-not (Test-Url $ApiHealthUrl)) {
    Start-Backend
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail "Node.js/npm non risulta installato. Serve per l'interfaccia React."
}

$PackageJson = Join-Path $Frontend "package.json"
$FrontendStamp = Join-Path $Root ".cora_frontend.sha256"
$CurrentFrontendHash = Get-HashText $PackageJson
$SavedFrontendHash = if (Test-Path $FrontendStamp) {
    (Get-Content $FrontendStamp -Raw).Trim()
} else {
    ""
}

if (
    -not (Test-Path (Join-Path $Frontend "node_modules")) -or
    $CurrentFrontendHash -ne $SavedFrontendHash
) {
    Write-Host "Installo/aggiorno l'interfaccia React..."
    Push-Location $Frontend
    npm install
    $NpmExitCode = $LASTEXITCODE
    Pop-Location

    if ($NpmExitCode -ne 0) {
        Fail "Installazione frontend fallita."
    }

    Set-Content -Path $FrontendStamp -Value $CurrentFrontendHash
}

if (-not (Test-Url $UiUrl)) {
    Stop-KnownProcess $FrontendPidFile
    Stop-TaggedWindows $FrontendWindowTitle
    Clear-StalePort 5173
    Write-Host "Avvio interfaccia React..."
    $FrontendProcess = Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "`$host.UI.RawUI.WindowTitle = '$FrontendWindowTitle'; Set-Location '$Frontend'; npm run dev"
    ) -WindowStyle Minimized -PassThru
    Set-Content -Path $FrontendPidFile -Value $FrontendProcess.Id
}

if (-not (Wait-Url $UiUrl 40)) {
    Fail "L'interfaccia non ha risposto entro il tempo previsto. Apri la finestra minimizzata $FrontendWindowTitle per vedere l'errore."
}

Write-Host "Interfaccia pronta, la apro. Il backend potrebbe metterci ancora qualche istante al primo avvio..." -ForegroundColor Green
Start-Process $UiUrl

Write-Host "Attendo che il backend FastAPI sia pronto (puo' volerci fino a 2 minuti al primo avvio a freddo)..."
if (Wait-Url $ApiHealthUrl 120) {
    Write-Host "Cora e' pronta." -ForegroundColor Green
} else {
    Write-Host "Il backend non risponde ancora. Apri la finestra minimizzata $BackendWindowTitle per vedere lo stato." -ForegroundColor Yellow
}

exit 0


} finally {
    Remove-Item -Path $LockFile -Force -ErrorAction SilentlyContinue
}
