param(
    [string]$Python = "python",
    [string]$ServerHost = "0.0.0.0",
    [int]$ApiPort = 8000,
    [int]$UiPort = 7860,
    [switch]$Force
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:UPLOAD_DIR = Join-Path $root "uploads"
$env:OUTPUT_DIR = Join-Path $root "outputs"
$env:NEXT_PUBLIC_API_BASE = "http://127.0.0.1:$ApiPort/api"

if ($Force) {
    $ports = @($ApiPort, $UiPort)
    foreach ($port in $ports) {
        $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($listener in $listeners) {
            try {
                Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            } catch {
            }
        }
    }
}

$apiOut = Join-Path $root "api.out.log"
$apiErr = Join-Path $root "api.err.log"
$uiOut = Join-Path $root "frontend.out.log"
$uiErr = Join-Path $root "frontend.err.log"

Start-Process -FilePath $Python `
    -ArgumentList "-m uvicorn app.main:app --reload --host $ServerHost --port $ApiPort" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr

Start-Process -FilePath "npm" `
    -ArgumentList @("--prefix", "frontend", "run", "dev", "--", "--hostname", $ServerHost, "--port", $UiPort) `
    -WorkingDirectory $root `
    -RedirectStandardOutput $uiOut `
    -RedirectStandardError $uiErr

Write-Host "Started."
Write-Host "API: http://127.0.0.1:$ApiPort/docs"
Write-Host "UI:  http://127.0.0.1:$UiPort"
