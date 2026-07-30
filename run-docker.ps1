param(
    [switch]$NoBuild,
    [int]$WaitSeconds = 120
)

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

Write-Host "Starting bichart with Docker Compose..." -ForegroundColor Cyan

function Test-DockerReady {
    docker info | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-DockerReady)) {
    try {
        $svc = Get-Service -Name "com.docker.service" -ErrorAction Stop
        if ($svc.Status -ne "Running") {
            Write-Host "Starting Windows service: com.docker.service" -ForegroundColor Yellow
            Start-Service -Name "com.docker.service" -ErrorAction Stop
        }
    } catch {
        Write-Host "Could not start com.docker.service automatically (may require Administrator)." -ForegroundColor DarkYellow
    }

    Write-Host "Docker daemon is not reachable. Trying to start Docker Desktop..." -ForegroundColor Yellow
    docker desktop start | Out-Null

    $started = $false
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        if (Test-DockerReady) {
            $started = $true
            break
        }
        Write-Host "Waiting for Docker engine..." -ForegroundColor DarkYellow
    }

    if (-not $started) {
        Write-Host "Docker daemon is still not running." -ForegroundColor Red
        Write-Host "Open Docker Desktop manually, wait for 'Engine running', then rerun this script." -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Test-Path ".env")) {
    Write-Host ".env not found. Creating a template .env file..." -ForegroundColor Yellow
    @"
AVALAI_API_KEY=your-avalai-key
SESSION_SECRET=replace-with-a-long-random-secret
"@ | Out-File -FilePath ".env" -Encoding UTF8 -Force

    Write-Host "Template created at .env" -ForegroundColor Green
    Write-Host "Update AVALAI_API_KEY in .env, then run this script again." -ForegroundColor Yellow
    exit 1
}

if ($NoBuild) {
    docker compose up -d
} else {
    docker compose up --build -d
}
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Docker Compose failed. Container was not started." -ForegroundColor Red
    Write-Host "Fix the error above and run the script again." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Container is up." -ForegroundColor Green
Write-Host "Open: http://localhost:8000" -ForegroundColor Green
Write-Host "Logs: docker compose logs -f" -ForegroundColor DarkCyan
