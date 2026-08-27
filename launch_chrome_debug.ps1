$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$debugPort = 9222
$userDataDir = "$env:LOCALAPPDATA\Google\Chrome\User Data"
$url = "https://www.iwencai.com"

# Check if port is available
$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $tcp.Connect("localhost", $debugPort)
    Write-Host "Port $debugPort is already in use - Chrome may already be running with debug"
    $tcp.Close()
} catch {
    Write-Host "Port $debugPort is free - launching Chrome with debug"
    $proc = Start-Process $chromePath -ArgumentList "--remote-debugging-port=$debugPort","--user-data-dir=$userDataDir",$url -PassThru -WindowStyle Normal
    Write-Host "Chrome started with PID $($proc.Id)"
}

# Wait for page load
Start-Sleep -Seconds 5

# Get CDP info
try {
    $response = Invoke-RestMethod "http://localhost:$debugPort/json" -TimeoutSec 3
    Write-Host "CDP available - pages:"
    $response | ForEach-Object { Write-Host "  $($_.url)" }
} catch {
    Write-Host "CDP not available: $_"
}
