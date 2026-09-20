$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend = Join-Path $Root "frontend"
$UiUrl = "http://127.0.0.1:5173"
$ApiUrl = "http://127.0.0.1:8000"
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
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creo l'ambiente Python .venv..."
    python -m venv .venv
}

Write-Host "Aggiorno/verifico le dipendenze Python..."
& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt") --disable-pip-version-check | Out-Host

if (-not (Test-Url $ApiUrl)) {
    Write-Host "Avvio backend FastAPI..."
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$Root'; & '$VenvPython' -m uvicorn api:app --host 127.0.0.1 --port 8000"
    ) -WindowStyle Minimized
}

if (-not (Wait-Url "$ApiUrl/health" 30)) {
    Write-Host "Il backend non si e' avviato correttamente." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js/npm non risulta installato. Serve per l'interfaccia React." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "Prima installazione interfaccia: npm install..."
    Push-Location $Frontend
    npm install
    Pop-Location
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
