# Record local lpe-lean image digest and print publish-by-digest recipe.
# Does NOT require registry login. Push steps are documented only.
#
# Usage:
#   .\scripts\record_lean_docker_digest.ps1
#   .\scripts\record_lean_docker_digest.ps1 -Tag lpe-lean:4.14 -OutDir artifacts\sbom

param(
    [string]$Tag = "lpe-lean:4.14",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path $RepoRoot "artifacts\sbom"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker not found on PATH. Install Docker and retry."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$inspect = docker image inspect $Tag 2>$null
if ($LASTEXITCODE -ne 0) {
    $readme = Join-Path $OutDir "lpe-lean.digest.README.txt"
    @"
Image $Tag is not present locally.
Build first:
  .\scripts\build_lean_docker_image.ps1
Then re-run:
  .\scripts\record_lean_docker_digest.ps1 -Tag $Tag -OutDir $OutDir
"@ | Set-Content -Path $readme -Encoding utf8
    Write-Error "Image $Tag missing; wrote $readme"
}

$ImageId = (docker image inspect --format '{{.Id}}' $Tag).Trim()
$RepoDigest = (docker image inspect --format '{{index .RepoDigests 0}}' $Tag 2>$null)
if (-not $RepoDigest -or $RepoDigest -eq "<no value>") {
    $RepoDigest = "none_until_pushed"
}
$Created = (docker image inspect --format '{{.Created}}' $Tag).Trim()
$RecordedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$DigestFile = Join-Path $OutDir "lpe-lean.digest.txt"
@"
tag=$Tag
image_id=$ImageId
repo_digest=$RepoDigest
created=$Created
recorded_at=$RecordedAt
"@ | Set-Content -Path $DigestFile -Encoding utf8

$Recipe = Join-Path $OutDir "lpe-lean.publish-by-digest.md"
@"
# Publish ``lpe-lean`` by digest (operator recipe)

Local image identity recorded in ``lpe-lean.digest.txt``.

## Pin for local use (no registry)

``````powershell
`$env:LPE_DOCKER_IMAGE = "$Tag"
# Prefer content address when available:
# `$env:LPE_DOCKER_IMAGE = "$ImageId"
``````

``RepoDigests`` is empty until the image is pushed to a registry.

## Publish and pin by digest (requires registry login)

``````powershell
`$REGISTRY = "ghcr.io/example"   # replace with your org registry
`$NAME = "lpe-lean"
`$VERSION = "4.14"

docker tag $Tag "`$REGISTRY/`$NAME:`$VERSION"
docker push "`$REGISTRY/`$NAME:`$VERSION"

# Resolve immutable digest after push:
`$DIGEST = docker image inspect --format '{{index .RepoDigests 0}}' "`$REGISTRY/`$NAME:`$VERSION"
Write-Host "Pin CI / runtime to: `$DIGEST"
``````

## SBOM

``````powershell
python scripts/generate_sbom.py --image $Tag --out-dir $OutDir
``````

Do not promote a floating tag to automatic acceptance without a digest pin.
"@ | Set-Content -Path $Recipe -Encoding utf8

Write-Host "Wrote $DigestFile"
Write-Host "Wrote $Recipe"
if ($RepoDigest -eq "none_until_pushed") {
    Write-Host "Note: repo digest unavailable until the image is pushed to a registry."
}
