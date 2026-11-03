[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$BaseUrl = "http://localhost:3000",

    [Parameter()]
    [string]$ApiKey = $env:OPEN_WEBUI_API_KEY,

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$FunctionId = "open_webui_guide",

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$FunctionName = "Open WebUI Guide",

    [Parameter()]
    [string]$SourcePath = (
        Join-Path $PSScriptRoot "..\openwebui\functions\howto_pipe.py"
    ),

    [Parameter()]
    [switch]$Update,

    [Parameter()]
    [switch]$NoEnable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "An administrator API key is required. Set OPEN_WEBUI_API_KEY or pass -ApiKey."
}

function Invoke-OpenWebUIRequest {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("GET", "POST")]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter()]
        [AllowNull()]
        [object]$Body,

        [Parameter(Mandatory = $true)]
        [hashtable]$Headers
    )

    $requestArguments = @{
        Uri                  = $Uri
        Method               = $Method
        Headers              = $Headers
        UseBasicParsing      = $true
        SkipHttpErrorCheck   = $true
    }
    if ($null -ne $Body) {
        $requestArguments.ContentType = "application/json"
        $requestArguments.Body = $Body | ConvertTo-Json -Depth 20 -Compress
    }

    $response = Invoke-WebRequest @requestArguments
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        $detail = $response.Content
        if ([string]::IsNullOrWhiteSpace($detail)) {
            $detail = "No response body"
        }
        throw "Open WebUI request failed ($($response.StatusCode)) for $Method $Uri`: $detail"
    }
    return $response
}

function ConvertFrom-ResponseJson {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Response
    )

    if ([string]::IsNullOrWhiteSpace($Response.Content)) {
        return $null
    }
    return $Response.Content | ConvertFrom-Json
}

function Normalize-FunctionSource {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content
    )

    return (($Content -replace "`r`n?", "`n").TrimEnd("`n"))
}

$resolvedSourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
$source = Get-Content -LiteralPath $resolvedSourcePath -Raw -Encoding UTF8
$sourceHash = (Get-FileHash -LiteralPath $resolvedSourcePath -Algorithm SHA256).Hash.ToLowerInvariant()

if (-not $FunctionId.IsNormalized()) {
    throw "FunctionId must be normalized Unicode text."
}
if ($FunctionId -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    throw "FunctionId must contain only letters, digits, and underscores and cannot start with a digit."
}

$normalizedBaseUrl = $BaseUrl.TrimEnd("/")
$functionsUrl = "$normalizedBaseUrl/api/v1/functions"
$escapedFunctionId = [Uri]::EscapeDataString($FunctionId.ToLowerInvariant())
$headers = @{ Authorization = "Bearer $ApiKey" }

Write-Verbose "Checking administrator access and existing Functions."
$listResponse = Invoke-OpenWebUIRequest `
    -Method GET `
    -Uri "$functionsUrl/list" `
    -Headers $headers
$functionList = @(ConvertFrom-ResponseJson -Response $listResponse)
$existingSummary = $functionList | Where-Object { $_.id -eq $escapedFunctionId } | Select-Object -First 1

$payload = @{
    id      = $escapedFunctionId
    name    = $FunctionName
    content = $source
    meta    = @{
        description = "Grounded Open WebUI onboarding guide"
        manifest    = @{}
    }
}

$function = $null
$operation = "unchanged"

if ($null -eq $existingSummary) {
    if ($PSCmdlet.ShouldProcess($FunctionName, "Create Open WebUI Function")) {
        $createResponse = Invoke-OpenWebUIRequest `
            -Method POST `
            -Uri "$functionsUrl/create" `
            -Body $payload `
            -Headers $headers
        $function = ConvertFrom-ResponseJson -Response $createResponse
        $operation = "created"
    }
} else {
    $getResponse = Invoke-OpenWebUIRequest `
        -Method GET `
        -Uri "$functionsUrl/id/$escapedFunctionId" `
        -Headers $headers
    $function = ConvertFrom-ResponseJson -Response $getResponse

    $storedSource = Normalize-FunctionSource -Content ([string]$function.content)
    $localSource = Normalize-FunctionSource -Content $source
    $definitionDiffers = (
        $storedSource -ne $localSource -or
        [string]$function.name -ne $FunctionName
    )
    if ($definitionDiffers) {
        if (-not $Update) {
            throw "Function '$escapedFunctionId' exists with a different name or source. Re-run with -Update to replace it explicitly."
        }
        if ($PSCmdlet.ShouldProcess($FunctionName, "Update Open WebUI Function")) {
            $updateResponse = Invoke-OpenWebUIRequest `
                -Method POST `
                -Uri "$functionsUrl/id/$escapedFunctionId/update" `
                -Body $payload `
                -Headers $headers
            $function = ConvertFrom-ResponseJson -Response $updateResponse
            $operation = "updated"
        }
    }
}

if ($null -ne $function -and -not $NoEnable -and -not [bool]$function.is_active) {
    if ($PSCmdlet.ShouldProcess($FunctionName, "Enable Open WebUI Function")) {
        $toggleResponse = Invoke-OpenWebUIRequest `
            -Method POST `
            -Uri "$functionsUrl/id/$escapedFunctionId/toggle" `
            -Headers $headers
        $function = ConvertFrom-ResponseJson -Response $toggleResponse
        if ($operation -eq "unchanged") {
            $operation = "enabled"
        }
    }
}

if ($null -ne $function) {
    if ([string]$function.type -ne "pipe") {
        throw "Function '$escapedFunctionId' was installed with unexpected type '$($function.type)'."
    }
    [PSCustomObject]@{
        id          = $function.id
        name        = $function.name
        type        = $function.type
        is_active   = [bool]$function.is_active
        operation   = $operation
        source_hash = $sourceHash
    }
}
