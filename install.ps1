# Instalador DevFlow v1.0.0 para PowerShell 5.1+ / 7+.
# A porcentagem representa ETAPAS concluídas, não bytes baixados.
$ErrorActionPreference = 'Stop'
$package = 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git for Windows não encontrado.' }
if (Get-Command py -ErrorAction SilentlyContinue) { $python = 'py'; $pythonArgs = @('-3') }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = 'python'; $pythonArgs = @() }
else { throw 'Python 3.10+ não encontrado.' }
& $python @pythonArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ é necessário.' }
if (Get-Command pipx -ErrorAction SilentlyContinue) { $pipx = 'pipx'; $pipxArgs = @() }
else {
    & $python @pythonArgs -m pipx --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'pipx não encontrado. Instale com py -m pip install --user pipx.' }
    $pipx = $python
    $pipxArgs = @($pythonArgs) + @('-m','pipx')
}
$log = [IO.Path]::GetTempFileName()
$err = [IO.Path]::GetTempFileName()
try {
    Write-Host 'DevFlow v1.0.0 — instalação/atualização'
    Write-Progress -Activity 'DevFlow v1.0.0' -Status 'Pré-requisitos validados (etapa 1/3)' -PercentComplete 33
    $arguments = @($pipxArgs) + @('install', '--force', $package)
    $proc = Start-Process -FilePath $pipx -ArgumentList $arguments -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError $err
    $tick = 0
    while (-not $proc.HasExited) {
        $symbol = @('|','/','-','\')[$tick % 4]
        Write-Progress -Activity 'DevFlow v1.0.0' -Status "Baixando e instalando... $symbol (etapa 2/3)" -PercentComplete 33
        Start-Sleep -Milliseconds 150
        $proc.Refresh()
        $tick++
    }
    if ($proc.ExitCode -ne 0) {
        Get-Content $log -Tail 25 | Write-Host
        Get-Content $err -Tail 25 | Write-Host
        throw "Falha do pipx (código $($proc.ExitCode))."
    }
    Write-Progress -Activity 'DevFlow v1.0.0' -Status 'Pacote instalado (etapa 2/3)' -PercentComplete 66
    & $pipx @pipxArgs ensurepath
    if ($LASTEXITCODE -ne 0) { throw 'pipx ensurepath falhou. Execute o comando manualmente.' }
    Write-Progress -Activity 'DevFlow v1.0.0' -Status 'PATH configurado (3/3)' -PercentComplete 100
    Write-Host 'Instalado! Abra outro terminal e execute: dev --version'
}
finally {
    Write-Progress -Activity 'DevFlow v1.0.0' -Completed
    Remove-Item $log, $err -ErrorAction SilentlyContinue
}
