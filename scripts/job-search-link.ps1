# Optional public link for JOB search users.
# Leave this stopped and the site still works at http://127.0.0.1:8000
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root ".tools"
$exe = Join-Path $tools "cloudflared.exe"
New-Item -ItemType Directory -Force -Path $tools | Out-Null
if (-not (Test-Path $exe)) {
    Write-Host "Downloading Cloudflare tunnel client..."
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $exe
}
Write-Host "Public link for http://127.0.0.1:8000 (keep runserver running). Ctrl+C stops the link."
& $exe tunnel --url http://127.0.0.1:8000 --no-autoupdate
