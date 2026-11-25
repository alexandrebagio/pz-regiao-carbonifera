param(
    [switch]$Offline,
    [switch]$AtualizarOsm,
    [switch]$AbrirPrevia
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
if ($Offline -and $AtualizarOsm) { throw 'Use -Offline ou -AtualizarOsm, não ambos.' }
$pythonProjeto = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjeto)) { & (Join-Path $PSScriptRoot 'preparar.ps1') }
$argumentosGerador = @((Join-Path $PSScriptRoot 'scripts\gerar_centro.py'))
if ($Offline) { $argumentosGerador += '--offline' }
if ($AtualizarOsm) { $argumentosGerador += '--atualizar-osm' }
& $pythonProjeto @argumentosGerador
if ($LASTEXITCODE -ne 0) { throw 'Geração interrompida. Consulte a mensagem acima.' }
& $pythonProjeto (Join-Path $PSScriptRoot 'scripts\validar_saida.py')
if ($LASTEXITCODE -ne 0) { throw 'A validação dos arquivos falhou.' }
if ($AbrirPrevia) { Invoke-Item -LiteralPath (Join-Path $PSScriptRoot 'output\centro\previa.png') }
