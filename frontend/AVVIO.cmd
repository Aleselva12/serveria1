@echo off
setlocal
cd /d "%~dp0"
title AVVIO Cora Frontend

rem Use the full backend launcher when a sibling checkout (or configured path) exists.
if defined CORA_BACKEND_PATH goto :backend
if exist "%~dp0..\serveria1\AVVIO.ps1" (
  set "CORA_BACKEND_PATH=%~dp0..\serveria1"
  goto :backend
)
echo Avvio solo l'interfaccia. FastAPI deve essere gia' attivo sul PC o sul server.
echo Per avviare tutto, usa AVVIO.cmd nella repository serveria1 aggiornata.

where node.exe >nul 2>nul
if errorlevel 1 (
  echo Node.js non trovato. Installa Node.js, poi riapri AVVIO.cmd.
  goto :error
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo npm non trovato. Reinstalla Node.js con npm, poi riapri AVVIO.cmd.
  goto :error
)
where curl.exe >nul 2>nul
if errorlevel 1 (
  echo curl.exe non trovato. Per questa versione usa npm run dev da PowerShell.
  goto :error
)

call :is_cora_ready
if not errorlevel 1 goto :open

if not exist "node_modules\.bin\vite.cmd" (
  echo Prima installazione delle dipendenze del frontend...
  call npm.cmd ci --include=dev
  if errorlevel 1 (
    echo Installazione non riuscita. Controlla la connessione Internet e riprova.
    goto :error
  )
)

echo Avvio Cora Frontend in una nuova finestra...
start "Cora Frontend - server locale" /D "%~dp0" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

for /L %%N in (1,1,30) do (
  timeout /t 1 /nobreak >nul
  call :is_cora_ready
  if not errorlevel 1 goto :open
)
echo Impossibile aprire Cora. Controlla la finestra del server locale.
echo Se la porta 5173 e' occupata da un altro programma, chiudilo e riprova.
goto :error

:open
echo Apertura di http://127.0.0.1:5173/
start "" "http://127.0.0.1:5173/"
exit /b 0

:is_cora_ready
curl.exe --silent --show-error --fail --max-time 2 "http://127.0.0.1:5173/" 2>nul | findstr /C:"cora-ui" >nul
exit /b %errorlevel%

:backend
if not exist "%CORA_BACKEND_PATH%\AVVIO.ps1" (
  echo CORA_BACKEND_PATH non contiene il launcher del backend.
  goto :error
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%CORA_BACKEND_PATH%\AVVIO.ps1" -FrontendPath "%~dp0."
exit /b %errorlevel%

:error
echo.
pause
exit /b 1
