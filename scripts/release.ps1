# Build and upload to PyPI. Run scripts/check.ps1 first.
# The version must not already exist on PyPI; the token is read from a secret store, never git.
$ErrorActionPreference = "Stop"

# Refuse to upload a version PyPI already has. Works on Windows PowerShell 5.1 and pwsh 7.
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
$released = $false
try {
    Invoke-WebRequest -UseBasicParsing "https://pypi.org/pypi/tdmread/$version/json" | Out-Null
    $released = $true
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
}
if ($released) { throw "tdmread $version is already on PyPI. Bump the version first." }

$token = $env:PYPI_TOKEN
if (-not $token -and (Test-Path "C:\secrets\pypi-token.txt")) {
    $token = (Get-Content "C:\secrets\pypi-token.txt" -Raw).Trim()
}
if (-not $token) {
    throw "No PyPI token. Set `$env:PYPI_TOKEN or save it to C:\secrets\pypi-token.txt (never commit it)."
}

Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
python -m build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m twine check --strict dist/*
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = $token
try { python -m twine upload dist/* } finally { Remove-Item Env:\TWINE_PASSWORD -ErrorAction SilentlyContinue }
