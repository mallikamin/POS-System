param(
    [string]$BaseUrl = "https://pos-demo.duckdns.org",
    [string]$Email = "admin@demo.com",
    [string]$Password = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [hashtable]$Headers,
        $Body
    )

    $params = @{
        Method = $Method
        Uri = $Url
        TimeoutSec = 30
    }
    if ($Headers) { $params.Headers = $Headers }
    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 10)
    }
    return Invoke-RestMethod @params
}

Write-Host "Kitchen backfill flow"
Write-Host "  Base URL: $BaseUrl"

# 1) Login
$loginUrl = "$BaseUrl/api/v1/auth/login"
$loginBody = @{
    email = $Email
    password = $Password
}

$auth = Invoke-Json -Method "POST" -Url $loginUrl -Body $loginBody
$token = $auth.tokens.access_token
if (-not $token) {
    throw "Login succeeded but access token was empty."
}

$headers = @{
    Authorization = "Bearer $token"
}

Write-Host "  Login: OK"

# 2) Verify active stations first
$stationsUrl = "$BaseUrl/api/v1/kitchen/stations?active_only=true"
$stations = Invoke-Json -Method "GET" -Url $stationsUrl -Headers $headers
$activeStationCount = if ($stations -is [System.Array]) { $stations.Count } elseif ($stations) { 1 } else { 0 }

if ($activeStationCount -eq 0) {
    Write-Host "  Active stations: 0"
    Write-Host ""
    Write-Host "Backfill skipped: no active kitchen stations."
    exit 0
}

# 3) Backfill
$backfillUrl = "$BaseUrl/api/v1/kitchen/backfill-tickets"
$createdCount = 0
try {
    $createdTickets = Invoke-Json -Method "POST" -Url $backfillUrl -Headers $headers
    if ($null -eq $createdTickets) {
        $createdCount = 0
    } elseif ($createdTickets -is [System.Array]) {
        $createdCount = $createdTickets.Count
    } else {
        $createdCount = 1
    }
    Write-Host "  Backfill created tickets: $createdCount"
} catch {
    Write-Host "Backfill request failed: $($_.Exception.Message)"
    throw
}

# 4) Quick verification snapshot
$ordersUrl = "$BaseUrl/api/v1/orders?status=in_kitchen&page=1&page_size=200"
$ordersResp = Invoke-Json -Method "GET" -Url $ordersUrl -Headers $headers
$inKitchenCount = [int]$ordersResp.total

$queueCount = 0

if ($activeStationCount -gt 0) {
    $stationId = if ($stations -is [System.Array]) { $stations[0].id } else { $stations.id }
    $queueUrl = "$BaseUrl/api/v1/kitchen/stations/$stationId/queue?active_only=true"
    $queue = Invoke-Json -Method "GET" -Url $queueUrl -Headers $headers
    $queueCount = if ($queue -is [System.Array]) { $queue.Count } elseif ($queue) { 1 } else { 0 }
}

Write-Host ""
Write-Host "Verification"
Write-Host "  Orders in_kitchen: $inKitchenCount"
Write-Host "  Active stations:   $activeStationCount"
Write-Host "  Queue (station 1): $queueCount"

if ($createdCount -eq 0) {
    Write-Host ""
    Write-Host "No new tickets were created. This is expected if:"
    Write-Host "  - all in_kitchen orders already had tickets, or"
    Write-Host "  - there are no in_kitchen orders."
}
