param([switch]$UmaCelula)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
$ferramentasProjeto = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config\ferramentas.json') -Raw | ConvertFrom-Json
$editorProjeto = Join-Path $ferramentasProjeto.tools_dir 'bin\PZWorldEd.exe'
$nomeProjeto = if ($UmaCelula) { 'teste_uma_celula.pzw' } else { 'centro_criciuma.pzw' }
$arquivoProjeto = Join-Path $PSScriptRoot (Join-Path 'mapping' $nomeProjeto)
if (-not (Test-Path -LiteralPath $editorProjeto)) { throw 'PZWorldEd.exe ausente. Confira config/ferramentas.json.' }
if (-not (Test-Path -LiteralPath $arquivoProjeto)) { throw 'Execute scripts/preparar_worlded.py para criar o projeto.' }
& $editorProjeto $arquivoProjeto
