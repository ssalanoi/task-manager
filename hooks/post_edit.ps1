# PostToolUse hook: format + lint + run affected tests after Edit/Write/MultiEdit.
# Reads the hook payload (JSON) from stdin and acts only on .py files.

$ErrorActionPreference = 'Stop'
$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }

try {
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$tool = $payload.tool_name
if ($tool -notin @('Edit', 'Write', 'MultiEdit')) { exit 0 }

$file = $payload.tool_input.file_path
if (-not $file) { exit 0 }
if (-not ($file -match '\.py$')) { exit 0 }
if (-not (Test-Path $file)) { exit 0 }

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Best-effort tool dispatch — skip silently if a tool isn't installed locally.
$failed = $false

if (Get-Command ruff -ErrorAction SilentlyContinue) {
    & ruff check --fix $file
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if (Get-Command black -ErrorAction SilentlyContinue) {
    & black -q $file
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if (Get-Command pytest -ErrorAction SilentlyContinue) {
    # Pick the right test root based on which package was edited.
    $testRoot = $null
    if     ($file -match 'backend[\\/]')    { $testRoot = 'backend/tests' }
    elseif ($file -match 'mcp-server[\\/]') { $testRoot = 'mcp-server/tests' }

    if ($testRoot -and (Test-Path $testRoot)) {
        & pytest -q $testRoot
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    }
}

if ($failed) { exit 2 } else { exit 0 }
