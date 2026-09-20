$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $Root "AVVIO.cmd"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "AVVIO.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Avvia o apre Cora"
$Shortcut.Save()

Write-Host "Creato collegamento sul desktop: AVVIO" -ForegroundColor Green
