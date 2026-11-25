param()
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
$pythonProjeto = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjeto)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.12 de 64 bits com o Python Launcher (py).' }
}
& $pythonProjeto -m pip install -r (Join-Path $PSScriptRoot 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências.' }
Write-Host 'Ambiente pronto. Execute .\iniciar.ps1 para gerar o centro de Criciúma.'
