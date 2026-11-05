# DevFlow installer for Windows PowerShell 5.1+ / PowerShell 7+.
# Review this script before running it. No admin privileges or permanent policy changes.
$ErrorActionPreference = 'Stop'
$source = 'git+https://github.com/felipeflosii/devflow-cli.git'

function Assert-Tool([string] $name, [string] $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name nao encontrado. $hint"
    }
}

Assert-Tool 'git' 'Instale Git for Windows: https://git-scm.com/downloads/win'

# Python Launcher (python.org) or python.exe (Store/winget).
if (Get-Command 'py' -ErrorAction SilentlyContinue) {
    $pythonCommand = 'py'
    $pythonPrefix = @('-3')
} elseif (Get-Command 'python' -ErrorAction SilentlyContinue) {
    $pythonCommand = 'python'
    $pythonPrefix = @()
} else {
    throw 'Python nao encontrado. Instale Python 3.11+ e reabra o PowerShell.'
}

& $pythonCommand @pythonPrefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10+ e necessario. Recomendamos Python 3.11+.'
}

# Prefer pipx.exe, also supports "py -3 -m pipx" if exe is not on PATH.
if (Get-Command 'pipx' -ErrorAction SilentlyContinue) {
    $pipxCommand = 'pipx'
    $pipxPrefix = @()
} else {
    & $pythonCommand @pythonPrefix -m pipx --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'pipx nao encontrado. Execute: py -m pip install --user pipx; py -m pipx ensurepath (ou instale com scoop install pipx).'
    }
    $pipxCommand = $pythonCommand
    $pipxPrefix = @($pythonPrefix) + @('-m', 'pipx')
}

Write-Host 'Instalando DevFlow no Windows (sem permissao de administrador)...'
& $pipxCommand @pipxPrefix install --force $source
if ($LASTEXITCODE -ne 0) { throw 'A instalacao via pipx falhou.' }
& $pipxCommand @pipxPrefix ensurepath
if ($LASTEXITCODE -ne 0) { throw 'O pipx nao conseguiu configurar o PATH.' }

Write-Host ''
Write-Host 'DevFlow instalado. Abra um NOVO PowerShell e execute: dev --version'
Write-Host 'Depois, dentro do clone Azure Repos: dev init; dev doctor'
