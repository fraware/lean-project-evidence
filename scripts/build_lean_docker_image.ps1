# Build the local Lean-capable sandbox image for LPE (Windows Docker Desktop).
# Usage: .\scripts\build_lean_docker_image.ps1 [-Tag lpe-lean:4.14] [-Toolchain leanprover/lean4:v4.14.0]

param(
    [string]$Tag = "lpe-lean:4.14",
    [string]$Toolchain = "leanprover/lean4:v4.14.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DockerfileDir = Join-Path $RepoRoot "docker\lpe-lean"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker not found on PATH. Install Docker Desktop and retry."
}

Write-Host "Building $Tag (toolchain=$Toolchain) from $DockerfileDir"
Write-Host "This downloads elan + Lean; expect several minutes on first run."

docker build `
    --build-arg "LEAN_TOOLCHAIN=$Toolchain" `
    -t $Tag `
    $DockerfileDir

if ($LASTEXITCODE -ne 0) {
    Write-Error "docker build failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Built $Tag. Verify:"
Write-Host "  docker run --rm $Tag lean --version"
Write-Host "  docker run --rm $Tag lake --version"
Write-Host ""
Write-Host "Use with LPE:"
Write-Host "  `$env:LPE_DOCKER_IMAGE = '$Tag'"
