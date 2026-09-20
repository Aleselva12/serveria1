$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend = Join-Path $Root "frontend"
$UiUrl = "http://127.0.0.1:5173"
$ApiHealthUrl = "http://127.0.0.1:8000/health"
$OllamaUrl = "http://127.0.0.1:11435"

function Test-Url($Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1 | Out-Null
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

Write-Host ""
Write-Host "=== AVVIO CORA ===" -ForegroundColor Cyan

if (Test-Url $UiUrl) {
    Write-Host "Cora e' gia attiva. Apro l'interfaccia..." -ForegroundColor Green
    Start-Process $UiUrl
    exit 0
}

Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".env")) -and (Test-Path (Join-Path $Root ".env.example"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Creato .env da .env.example. Potrai personalizzarlo in seguito." -ForegroundColor Yellow
}

if (-not (Test-Url $OllamaUrl)) {
    Write-Host "Ollama non risponde. Provo ad avviare il container ia-ollama..."
    try {
        docker start ia-ollama | Out-Null
    } catch {
        Write-Host "Non riesco ad avviare ia-ollama automaticamente." -ForegroundColor Yellow
    }

    if (-not (Wait-Url $OllamaUrl 20)) {
        Write-Host "Attenzione: Ollama non e' ancora raggiungibile su $OllamaUrl" -ForegroundColor Yellow
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$RequirementsStamp = Join-Path $Root ".cora_requirements.sha256"

if (-not (Test-Path $VenvPython)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Python non risulta installato o non e' nel PATH." -ForegroundColor Red
        exit 1
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
        Write-Host "Installazione dipendenze Python fallita." -ForegroundColor Red
        exit 1
    }
    Set-Content -Path $RequirementsStamp -Value $CurrentRequirementsHash
}

if (-not (Test-Url $ApiHealthUrl)) {
    Write-Host "Avvio backend FastAPI..."
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$Root'; & '$VenvPython' -m uvicorn api:app --host 127.0.0.1 --port 8000"
    ) -WindowStyle Minimized
}

if (-not (Wait-Url $ApiHealthUrl 30)) {
    Write-Host "Il backend non si e' avviato correttamente." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js/npm non risulta installato. Serve per l'interfaccia React." -ForegroundColor Red
    exit 1
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
        Write-Host "Installazione frontend fallita." -ForegroundColor Red
        exit 1
    }

    Set-Content -Path $FrontendStamp -Value $CurrentFrontendHash
}

Write-Host "Avvio interfaccia React..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Frontend'; npm run dev"
) -WindowStyle Minimized

if (Wait-Url $UiUrl 30) {
    Write-Host "Cora e' pronta." -ForegroundColor Green
    Start-Process $UiUrl
    exit 0
}

Write-Host "L'interfaccia non ha risposto entro il tempo previsto." -ForegroundColor Red
exit 1
