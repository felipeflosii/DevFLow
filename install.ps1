# Instala DevFlow da branch principal publicada no GitHub (Windows/PowerShell).
$ErrorActionPreference = 'Stop'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git for Windows é necessário.' }
if (Get-Command py -ErrorAction SilentlyContinue) { $py='py'; $pyArgs=@('-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py='python'; $pyArgs=@() }
else { throw 'Python 3.10+ é necessário.' }
& $py @pyArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ é necessário.' }
if (Get-Command pipx -ErrorAction SilentlyContinue) { $pipx='pipx'; $pipxArgs=@() }
else { $pipx=$py; $pipxArgs=@($pyArgs) + @('-m','pipx') }
& $pipx @pipxArgs install --force 'git+https://github.com/felipeflosii/devflow-cli.git'
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar DevFlow via pipx.' }
& $pipx @pipxArgs ensurepath
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível configurar o PATH.' }
Write-Host 'DevFlow instalado. Abra um novo terminal e execute: dev --version'
