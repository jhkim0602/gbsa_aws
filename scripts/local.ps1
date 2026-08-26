# Created: 2026-08-21 09:29
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("install", "up", "down", "api", "worker", "company", "applicant", "test", "check", "doctor", "status")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Import-DotEnv {
    $envPath = Join-Path $repoRoot ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        throw ".env is missing. Copy .env.example to .env and fill in the cloud settings first."
    }

    foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        if ($trimmed -notmatch "^([^=]+)=(.*)$") { continue }

        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Invoke-Uv {
    & uv run --cache-dir .uv-cache --no-sync @args
    if ($LASTEXITCODE -ne 0) { throw "uv command failed with exit code $LASTEXITCODE" }
}

function Test-LocalConfiguration {
    Import-DotEnv
    $required = @(
        "APP_ENVIRONMENT", "DATABASE_URL", "MIGRATION_DATABASE_URL", "AWS_REGION",
        "AWS_ENDPOINT_URL", "BEDROCK_MODEL_ID",
        "GCP_DOCUMENT_AI_PROJECT_ID", "GCP_DOCUMENT_AI_PROCESSOR_ID"
    )
    $missing = @($required | Where-Object { [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, "Process")) })
    if ($missing.Count -gt 0) {
        throw "Missing required .env values: $($missing -join ', ')"
    }

    $credentialFile = [Environment]::GetEnvironmentVariable("GOOGLE_APPLICATION_CREDENTIALS", "Process")
    $adcFile = Join-Path $env:APPDATA "gcloud\application_default_credentials.json"
    if ($credentialFile) {
        if (-not (Test-Path -LiteralPath $credentialFile -PathType Leaf)) {
            throw "GOOGLE_APPLICATION_CREDENTIALS does not point to a readable file: $credentialFile"
        }
    } elseif (-not (Test-Path -LiteralPath $adcFile -PathType Leaf)) {
        throw "Google credentials are missing. Set GOOGLE_APPLICATION_CREDENTIALS in .env or run 'gcloud auth application-default login'."
    }

    Write-Host "Local configuration looks ready."
}

switch ($Action) {
    "install" {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        & uv sync --cache-dir .uv-cache --frozen
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
    }
    "up" {
        Import-DotEnv
        & docker compose up -d --wait --remove-orphans
        if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
        Invoke-Uv python -m interview_evidence.runtime.local_infra
        Invoke-Uv alembic -c backend/alembic.ini upgrade heads
        Write-Host "Local infrastructure and migrations are ready."
    }
    "down" {
        & docker compose down
        if ($LASTEXITCODE -ne 0) { throw "docker compose down failed" }
    }
    "api" {
        Import-DotEnv
        Invoke-Uv uvicorn interview_evidence.main:app --reload --host 127.0.0.1 --port 8080
    }
    "worker" {
        Test-LocalConfiguration
        Invoke-Uv python scripts/run_workers.py
    }
    "company" {
        & npm.cmd run dev:company
        if ($LASTEXITCODE -ne 0) { throw "company console failed" }
    }
    "applicant" {
        & npm.cmd run dev:applicant
        if ($LASTEXITCODE -ne 0) { throw "applicant app failed" }
    }
    "test" {
        & npm.cmd test
        if ($LASTEXITCODE -ne 0) { throw "test suite failed" }
    }
    "check" {
        foreach ($command in @("format:check", "lint", "typecheck", "build")) {
            & npm.cmd run $command
            if ($LASTEXITCODE -ne 0) { throw "$command failed" }
        }
    }
    "doctor" {
        Test-LocalConfiguration
        & docker info --format "Docker server {{.ServerVersion}}"
        if ($LASTEXITCODE -ne 0) { throw "Docker Desktop is not running" }
        & node --version
        & uv --version
    }
    "status" {
        & docker compose ps
        try {
            $ready = Invoke-RestMethod -Uri "http://127.0.0.1:8080/health/ready" -TimeoutSec 5
            $ready | ConvertTo-Json -Depth 5
        } catch {
            Write-Host "API is not reachable at http://127.0.0.1:8080"
        }
    }
}
