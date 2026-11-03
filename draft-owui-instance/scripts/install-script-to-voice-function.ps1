[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$BaseUrl = 'http://localhost:3000',
    [string]$ApiKey = $env:OPEN_WEBUI_API_KEY,
    [switch]$Update,
    [switch]$NoEnable
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$arguments = @{
    BaseUrl = $BaseUrl
    ApiKey = $ApiKey
    FunctionId = 'script_to_voice'
    FunctionName = 'Script to Voice'
    SourcePath = (Join-Path $PSScriptRoot '../openwebui/functions/script_to_voice_pipe.py')
    Update = $Update
    NoEnable = $NoEnable
    WhatIf = $WhatIfPreference
}
& (Join-Path $PSScriptRoot 'install-howto-function.ps1') @arguments
