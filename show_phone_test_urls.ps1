Set-Location $PSScriptRoot
Write-Host "AfriSync phone testing URLs"
Write-Host "Make sure your phone and PC are on the same Wi-Fi network."
Write-Host ""

$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254*" -and
    $_.IPAddress -notlike "172.17.*" -and
    $_.AddressState -eq "Preferred"
} | Select-Object -ExpandProperty IPAddress -Unique

if (!$ips) {
    Write-Host "No local Wi-Fi/LAN IPv4 address found. Run ipconfig and look for IPv4 Address."
    exit 0
}

foreach ($ip in $ips) {
    Write-Host "Device A: http://$ip`:8001"
    Write-Host "Device B: http://$ip`:8002"
    Write-Host "Remote health: http://$ip`:8000/health"
    Write-Host ""
}
