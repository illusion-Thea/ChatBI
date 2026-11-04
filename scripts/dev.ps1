$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host 'Start QueryX in two terminals:'
Write-Host "  Backend:  cd '$projectRoot'; uv run uvicorn commercial.main:app --host 127.0.0.1 --port 8013 --reload"
Write-Host "  QueryX:   cd '$projectRoot'; npm run dev"
Write-Host '  Open:     http://127.0.0.1:5181'
