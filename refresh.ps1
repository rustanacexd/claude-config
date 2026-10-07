$ErrorActionPreference = 'Stop'
try {
    $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 (Join-Path $PSScriptRoot 'manage.py') refresh @args
    } else {
        $python = Get-Command python, python3 -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $python) {
            throw 'Python 3.11 or newer is required. Install Python and add it to PATH.'
        }
        & $python.Source (Join-Path $PSScriptRoot 'manage.py') refresh @args
    }
    exit $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
