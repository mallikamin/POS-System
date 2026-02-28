param(
    [string]$BaseUrl = "https://pos-demo.duckdns.org",
    [string]$Email = "admin@demo.com",
    [string]$Password = "admin123",
    [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
    [string]$Method = "GET",
    [string]$Path = "/api/v1/health",
    [string]$BodyJson = "",
    [switch]$SkipAuth
)

$ErrorActionPreference = "Stop"

function Invoke-ApiJson {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Url,
        [hashtable]$Headers,
        $Body
    )

    $params = @{
        Method     = $Method
        Uri        = $Url
        TimeoutSec = 45
    }

    if ($Headers) {
        $params.Headers = $Headers
    }

    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 20 -Compress)
    }

    return Invoke-RestMethod @params
}

$normalizedPath = if ($Path.StartsWith("/")) { $Path } else { "/$Path" }
$url = "$BaseUrl$normalizedPath"

$commonHeaders = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UAT-Tester"
    "Accept"     = "application/json"
}

$authHeader = @{}
if (-not $SkipAuth) {
    $loginUrl = "$BaseUrl/api/v1/auth/login"
    $loginBody = @{
        email    = $Email
        password = $Password
    }

    $auth = Invoke-ApiJson -Method "POST" -Url $loginUrl -Headers $commonHeaders -Body $loginBody
    $token = $auth.tokens.access_token
    if (-not $token) {
        throw "Login succeeded but access token was empty."
    }

    $authHeader = @{ Authorization = "Bearer $token" }
}

$headers = @{}
$commonHeaders.GetEnumerator() | ForEach-Object { $headers[$_.Key] = $_.Value }
$authHeader.GetEnumerator() | ForEach-Object { $headers[$_.Key] = $_.Value }

$bodyObj = $null
if ($BodyJson -and $BodyJson.Trim().Length -gt 0) {
    try {
        $bodyObj = $BodyJson | ConvertFrom-Json
    } catch {
        throw "BodyJson must be valid JSON. Parse error: $($_.Exception.Message)"
    }
}

$response = Invoke-ApiJson -Method $Method -Url $url -Headers $headers -Body $bodyObj
$response | ConvertTo-Json -Depth 20