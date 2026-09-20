@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0AVVIO.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==============================================
    echo AVVIO fallito. Guarda i messaggi sopra per il motivo.
    echo ==============================================
    pause
)
