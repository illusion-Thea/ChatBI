param(
    [int]$Port = 8013
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$mysqlRoot = 'D:\MySQL\MySQL Server 8.0'
$mysqlExe = Join-Path $mysqlRoot 'bin\mysqld.exe'
$mysqlData = Join-Path $runtimeRoot 'local-mysql\data'
$mysqlLog = Join-Path $runtimeRoot 'local-mysql\mysql.log'
$mysqlPid = Join-Path $runtimeRoot 'local-mysql\mysql.pid'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$distIndex = Join-Path $projectRoot 'frontend-vben\apps\web-business\dist\index.html'

function Test-TcpPort([int]$TargetPort) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect('127.0.0.1', $TargetPort, $null, $null)
        return $pending.AsyncWaitHandle.WaitOne(500) -and $client.Connected
    } finally {
        $client.Dispose()
    }
}

if (!(Test-Path (Join-Path $projectRoot '.env'))) {
    throw 'Missing .env. Complete the local database configuration first.'
}
if (!(Test-Path $pythonExe)) {
    throw 'Missing .venv. Install Python dependencies first.'
}
if (!(Test-Path $distIndex)) {
    throw 'Missing business frontend build. Run npm run build:business first.'
}

if (!(Test-TcpPort 3307)) {
    if (!(Test-Path $mysqlExe) -or !(Test-Path $mysqlData)) {
        throw 'Local MySQL runtime is not initialized. Run scripts/init_local_database.py or use docker compose.'
    }
    $mysqlArguments = @(
        '--no-defaults',
        "--basedir=`"$mysqlRoot`"",
        "--datadir=`"$mysqlData`"",
        '--port=3307',
        '--bind-address=127.0.0.1',
        '--mysqlx=0',
        '--server-id=3307',
        '--character-set-server=utf8mb4',
        '--collation-server=utf8mb4_unicode_ci',
        "--pid-file=`"$mysqlPid`"",
        "--log-error=`"$mysqlLog`""
    ) -join ' '
    Start-Process -FilePath $mysqlExe -WindowStyle Hidden -ArgumentList $mysqlArguments
    for ($attempt = 0; $attempt -lt 30 -and !(Test-TcpPort 3307); $attempt++) {
        Start-Sleep -Milliseconds 500
    }
    if (!(Test-TcpPort 3307)) {
        throw "MySQL did not start. Inspect $mysqlLog"
    }
}

Write-Host "MySQL:  http://127.0.0.1:3307 (TCP)"
Write-Host "Web app: http://127.0.0.1:$Port"
& $pythonExe (Join-Path $projectRoot 'start_business.py') --port $Port
