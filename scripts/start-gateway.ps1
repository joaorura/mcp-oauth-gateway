#Requires -Version 7
<#
    Inicia o mcp-oauth-gateway, e opcionalmente um processo de backend antes dele.

    Casos de uso:
      - Backend stdio: o proprio gateway spawna o processo (StdioTransport
        do FastMCP). Este script so precisa gerenciar o gateway.
      - Backend HTTP ja rodando em outro lugar: idem, so o gateway.
      - Backend HTTP que voce quer subir junto (ex.: um MCP local seu):
        defina BACKEND_START_COMMAND / BACKEND_START_ARGS no .env, e este
        script sobe os dois na ordem certa, com health-check entre eles.

    Sem caminho de maquina hardcoded: tudo vem do .env na raiz do projeto.
    Rode a partir da raiz, ou diretamente por caminho — o script resolve a
    raiz a partir da propria localizacao (scripts/..).

    Roda a cada logon (via install-scheduled-task.ps1) e, se voce configurar
    o gatilho diario, tambem funciona como mecanismo de ROTACAO: qualquer
    coisa sensivel a reinicio (ex.: um BACKEND_BEARER_TOKEN que voce troca a
    cada deploy) se renova nesse ciclo. Ver README, secao "Rotacionando
    credenciais".
#>

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Get-DotEnvValue([string]$Key) {
    $envFile = Join-Path $ProjectRoot '.env'
    if (-not (Test-Path $envFile)) { return $null }
    $line = Select-String -Path $envFile -Pattern "^$Key=(.*)$" | Select-Object -First 1
    if ($line) { return $line.Matches[0].Groups[1].Value.Trim() }
    return $null
}

$LogDir = Get-DotEnvValue 'LOG_DIR'
if (-not $LogDir) { $LogDir = Join-Path $ProjectRoot 'logs' }
if (-not [System.IO.Path]::IsPathRooted($LogDir)) { $LogDir = Join-Path $ProjectRoot $LogDir }
New-Item -ItemType Directory -Force $LogDir | Out-Null

function Write-Log([string]$Message) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $LogDir 'stack.log') -Value "[$stamp] $Message"
}

# --- Retencao dos logs de PROCESSO (stdout/err por execucao, nomeados com
# timestamp unico -- ver mais abaixo). O access.log da aplicacao (log de
# auditoria) ja rotaciona por tamanho — ver src/audit.py. Estes nao, porque
# cada execucao cria um par novo; sem limpeza, um reinicio diario acumularia
# 2-4 arquivos por dia para sempre.
$RetentionDays = 14
Get-ChildItem -Path $LogDir -Filter '*.log' -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(backend|gateway)\.\d{8}-\d{6}\.(out|err)\.log$' -and
        $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays)
    } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$RunStamp = Get-Date -Format 'yyyyMMdd-HHmmss'

# --- 0) Encerra instancias anteriores deste gateway (relevante em reinicio
# programado / rotacao de credenciais). Mira pela CommandLine e pelo caminho
# do projeto, nao so pelo nome do processo -- python.exe e usado por
# incontaveis outras coisas numa maquina de desenvolvimento.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*src.gateway*' -and $_.CommandLine -like "*$ProjectRoot*" } |
    ForEach-Object {
        Write-Log "Encerrando gateway anterior (PID $($_.ProcessId))..."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

$BackendStartCommand = Get-DotEnvValue 'BACKEND_START_COMMAND'
if ($BackendStartCommand) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$BackendStartCommand*" -and $_.CommandLine -like "*$ProjectRoot*" } |
        ForEach-Object {
            Write-Log "Encerrando backend anterior (PID $($_.ProcessId))..."
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

Start-Sleep -Seconds 2   # da tempo das portas serem liberadas

# --- 1) Sobe o backend, SE BACKEND_START_COMMAND estiver definido no .env.
# Nao se aplica a backends stdio (o gateway os spawna sozinho) nem a
# backends que ja rodam em outro lugar.
if ($BackendStartCommand) {
    $BackendStartArgsRaw = Get-DotEnvValue 'BACKEND_START_ARGS'
    $backendArgsList = if ($BackendStartArgsRaw) { $BackendStartArgsRaw -split ' ' } else { @() }

    $BackendOut = Join-Path $LogDir "backend.$RunStamp.out.log"
    $BackendErr = Join-Path $LogDir "backend.$RunStamp.err.log"

    Write-Log "Iniciando backend ($BackendStartCommand)..."
    # -PassThru: guarda o processo iniciado para confirmar que ELE (nao um
    # listener antigo/obsoleto na mesma porta) continua vivo.
    $backendProc = Start-Process -FilePath $BackendStartCommand -ArgumentList $backendArgsList `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr

    $backendUrl = Get-DotEnvValue 'BACKEND_URL'
    if ($backendUrl) {
        $deadline = (Get-Date).AddSeconds(120)
        $ready = $false
        while ((Get-Date) -lt $deadline) {
            try {
                # Qualquer resposta HTTP (mesmo 401/404) ja prova que algo
                # esta escutando -- nao presumimos um /health especifico,
                # porque nem todo backend expoe um.
                Invoke-WebRequest -Uri $backendUrl -Method Head -TimeoutSec 3 -UseBasicParsing -SkipHttpErrorCheck | Out-Null
                $ready = $true
                break
            } catch {
                Start-Sleep -Seconds 2
            }
        }
        if (-not $ready) {
            Write-Log "ERRO: backend nao respondeu em 120s. Ver $BackendErr."
            exit 1
        }
    } else {
        Start-Sleep -Seconds 5   # sem URL para checar, so da um tempo pro processo subir
    }

    $backendProc.Refresh()
    if ($backendProc.HasExited) {
        Write-Log "ERRO: processo do backend (PID $($backendProc.Id)) ja morreu. Ver $BackendErr."
        exit 1
    }
    Write-Log "Backend pronto (PID $($backendProc.Id))."
}

# --- 2) Sobe o gateway
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) {
    Write-Log "ERRO: $PythonExe nao existe. Rode a instalacao (README, secao Instalacao) antes de usar este script."
    exit 1
}

$GatewayOut = Join-Path $LogDir "gateway.$RunStamp.out.log"
$GatewayErr = Join-Path $LogDir "gateway.$RunStamp.err.log"

Write-Log 'Iniciando gateway...'
$gatewayProc = Start-Process -FilePath $PythonExe `
    -ArgumentList @('-m', 'src.gateway') -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $GatewayOut -RedirectStandardError $GatewayErr

$GatewayHost = Get-DotEnvValue 'GATEWAY_HOST'
if (-not $GatewayHost) { $GatewayHost = '127.0.0.1' }
$GatewayPort = Get-DotEnvValue 'GATEWAY_PORT'
if (-not $GatewayPort) { $GatewayPort = '8000' }

# O gateway nao tem endpoint sem auth no /mcp (responde 401 por design -- e
# o comportamento correto). O metadata OAuth e publico por especificacao e
# so existe quando o servidor esta de pe: e o sinal de prontidao mais
# confiavel disponivel sem autenticar.
$deadline = (Get-Date).AddSeconds(60)
$gatewayReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://${GatewayHost}:${GatewayPort}/.well-known/oauth-authorization-server" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $gatewayReady = $true; break }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $gatewayReady) {
    Write-Log "ERRO: gateway nao respondeu o metadata OAuth em 60s. Ver $GatewayErr."
    exit 1
}

$gatewayProc.Refresh()
if ($gatewayProc.HasExited) {
    Write-Log "ERRO: metadata OAuth respondeu 200, mas o processo do gateway (PID $($gatewayProc.Id)) ja morreu. Ver $GatewayErr."
    exit 1
}
Write-Log "Gateway pronto (PID $($gatewayProc.Id))."

Write-Log 'Pilha iniciada.'
