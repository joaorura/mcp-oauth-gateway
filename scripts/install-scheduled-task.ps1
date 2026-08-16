#Requires -Version 7
<#
    Registra uma Tarefa Agendada do Windows para subir o gateway no logon, e
    opcionalmente reinicia-lo diariamente. O gatilho diario nao e so
    resiliencia -- se voce troca BACKEND_BEARER_TOKEN periodicamente (ou
    qualquer outra credencial sensivel a reinicio), ele funciona como
    mecanismo de ROTACAO: um segredo que nao tem TTL proprio ganha um TTL
    operacional de ateh 24h. Veja o README, secao "Rotacionando credenciais".

    Rode a partir da raiz do projeto, ou o script resolve sozinho a partir
    de scripts/..
#>

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TaskName    = 'McpOAuthGateway'
$Script      = Join-Path $ProjectRoot 'scripts\start-gateway.ps1'

# Defina como $null para desativar o reinicio diario e manter so o gatilho
# de logon.
$DailyRestartTime = '04:00'

# Resolucao robusta do pwsh.exe: NAO usar o nome curto 'pwsh.exe' (so
# resolve via PATH de USUARIO nesta maquina, ausente no PATH de MAQUINA que
# o Task Scheduler usa por padrao -- falha muda, nem o log chega a ser
# criado) e NAO hardcodar o caminho versionado de
# 'Program Files\WindowsApps\Microsoft.PowerShell_<versao>_x64__...\pwsh.exe',
# que muda a cada atualizacao do PowerShell 7 via Store.
# O alias em %LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe e o App Execution
# Alias da Store: caminho ESTAVEL que o Windows resolve internamente para a
# instalacao versionada atual. Com fallback para uma instalacao tradicional
# em Program Files\PowerShell\7, caso exista.
function Resolve-PwshPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\pwsh.exe'),
        'C:\Program Files\PowerShell\7\pwsh.exe'
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    $joined = $candidates -join ', '
    throw "pwsh.exe nao encontrado em nenhum local conhecido ($joined). Instale o PowerShell 7 ou atualize esta lista."
}
$PwshPath = Resolve-PwshPath

$action = New-ScheduledTaskAction -Execute $PwshPath `
    -Argument "-NoProfile -WindowStyle Hidden -File `"$Script`""

$triggers = @(New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME)
if ($DailyRestartTime) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $DailyRestartTime
}

# NOTA: RestartCount/RestartInterval abaixo cobrem SOMENTE falha da TAREFA
# (a acao 'pwsh -File start-gateway.ps1' retornar exit code != 0 durante a
# propria execucao). NAO cobrem a morte de um processo filho horas depois:
# start-gateway.ps1 destaca os processos com Start-Process e o proprio
# script termina com exit 0 assim que eles ficam saudaveis -- para o Task
# Scheduler, "a tarefa deu certo" e nao ha mais nada rodando sob supervisao
# dele. Se o gateway cair no meio da tarde, nada o reinicia ate o gatilho
# diario ou o proximo logon (o que vier primeiro). Para supervisao real de
# processo, considere um servico dedicado (NSSM, systemd, etc.) em vez de
# Tarefa Agendada.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings `
    -Description 'Sobe o mcp-oauth-gateway no logon (e opcionalmente reinicia diariamente)' `
    -Force

Get-ScheduledTask -TaskName $TaskName
