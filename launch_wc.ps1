$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$port = 9223
$profile = "$env:LOCALAPPDATA\Google\Chrome\User Data"
$url = "https://www.iwencai.com"
$arg = "--remote-debugging-port=$port --user-data-dir=`"$profile`" --profile-directory=Default $url"
Write-Host "Launching Chrome with debug port $port..."
$proc = Start-Process $chrome -ArgumentList $arg -PassThru -WindowStyle Normal
Start-Sleep -Seconds 6
Write-Host "Chrome PID: $($proc.Id)"
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", $port)
    Write-Host "Port $port is OPEN - CDP ready!"
    $tcp.Close()
} catch {
    Write-Host "Port $port is CLOSED"
}
