$ErrorActionPreference = "Stop"

$serverDoc = "SERVER.md"
$expectedHost = "pos-demo.duckdns.org"
$expectedPath = "~/pos-system"

if (-not (Test-Path $serverDoc)) {
    throw "SERVER.md not found. Cannot validate server details."
}

$ipLine = Select-String -Path $serverDoc -Pattern "^\| IP \|" | Select-Object -First 1
if (-not $ipLine) {
    throw "Could not parse IP from SERVER.md."
}

$docIp = ($ipLine.Line -replace "^\| IP \|\s*([^|]+)\s*\|.*$", '$1').Trim()
if (-not $docIp) {
    throw "Parsed IP from SERVER.md is empty."
}

$dnsIps = @()
try {
    $dnsIps = (Resolve-DnsName -Name $expectedHost -Type A | Select-Object -ExpandProperty IPAddress)
} catch {
    Write-Host "DNS check unavailable (Resolve-DnsName failed): $($_.Exception.Message)"
}

Write-Host "Server preflight"
Write-Host "  Host (canonical): $expectedHost"
Write-Host "  IP (SERVER.md):   $docIp"
Write-Host "  Project path:     $expectedPath"

if ($dnsIps.Count -gt 0) {
    Write-Host "  DNS resolves to:  $($dnsIps -join ' ')"
    if ($dnsIps -notcontains $docIp) {
        throw "DNS does not include SERVER.md IP ($docIp). Stop and verify droplet/IP first."
    }
} else {
    Write-Host "  DNS check:        skipped (no A record resolved)"
}

Write-Host ""
Write-Host "Use only this SSH target:"
Write-Host "  ssh root@$docIp"
Write-Host ""
Write-Host "Then confirm server path:"
Write-Host "  cd $expectedPath && pwd"
Write-Host ""
Write-Host "Preflight passed."
