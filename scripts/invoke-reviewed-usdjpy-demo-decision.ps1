param(
    [Parameter(Mandatory = $true)]
    [string]$Mt5DataPath,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedCommit,

    [Parameter(Mandatory = $true)]
    [string]$PreviousClose,

    [Parameter(Mandatory = $true)]
    [string]$Balance,

    [Parameter(Mandatory = $true)]
    [string]$Equity,

    [Parameter(Mandatory = $true)]
    [string]$DailyRealizedPnl,

    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 0)]
    [int]$OpenPositionCount,

    [ValidateRange(1, 30)]
    [int]$MetadataMaxAgeSeconds = 15
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SubmissionStarted = $false
$RequestId = $null

function Convert-InvariantDecimal {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    [decimal]$Parsed = 0
    if (-not [decimal]::TryParse(
        $Value,
        [System.Globalization.NumberStyles]::Number,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$Parsed
    )) {
        throw "Invalid decimal for $Name."
    }
    return $Parsed
}

function Assert-FreshObservation {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Symbol,
        [Parameter(Mandatory = $true)]
        [int]$MaximumAgeSeconds
    )

    $ObservedAt = [DateTimeOffset]::Parse(
        [string]$Symbol.observed_at,
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $AgeSeconds = ([DateTimeOffset]::UtcNow - $ObservedAt.ToUniversalTime()).TotalSeconds
    if ($AgeSeconds -lt -2 -or $AgeSeconds -gt $MaximumAgeSeconds) {
        throw "Fresh USDJPY metadata is required; no decision was submitted."
    }
    return $AgeSeconds
}

try {
    if ($env:OS -ne "Windows_NT") {
        throw "Controlled DEMO submission is supported only on the Windows trading node."
    }

    Set-Location (Resolve-Path "$PSScriptRoot\..")

    if (-not (Test-Path ".env" -PathType Leaf)) {
        throw ".env is required."
    }
    if (-not (Test-Path $Mt5DataPath -PathType Container)) {
        throw "The supplied MT5 data path does not exist."
    }

    $GitStatus = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw "Git repository state could not be verified."
    }
    if ($GitStatus.Count -ne 0) {
        throw "Controlled submission requires a clean worktree."
    }

    $ActualCommit = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $ActualCommit -ne $ExpectedCommit) {
        throw "Git HEAD does not match the explicitly reviewed commit."
    }

    $PreviousCloseValue = Convert-InvariantDecimal -Value $PreviousClose -Name "PreviousClose"
    $BalanceValue = Convert-InvariantDecimal -Value $Balance -Name "Balance"
    $EquityValue = Convert-InvariantDecimal -Value $Equity -Name "Equity"
    $DailyPnlValue = Convert-InvariantDecimal -Value $DailyRealizedPnl -Name "DailyRealizedPnl"

    if ($PreviousCloseValue -le 0 -or $BalanceValue -le 0 -or $EquityValue -lt 0) {
        throw "Account/market numeric preconditions failed."
    }

    $MetadataPath = Join-Path $Mt5DataPath "MQL5\Files\arsam_mt5_metadata_1_0.json"
    if (-not (Test-Path $MetadataPath -PathType Leaf)) {
        throw "ReadOnlyMetadataProbe output was not found at the reviewed MT5 data path."
    }

    $Meta = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
    if ($Meta.schema_version -ne "1.0" -or
        $Meta.mode -ne "read_only_metadata_probe" -or
        $Meta.source_type -ne "mql5_metadata_probe") {
        throw "Unexpected metadata contract."
    }
    if ($Meta.broker.company -ne "FIBO Group, Ltd" -or
        $Meta.broker.server -ne "FIBOGroup-MT5 Server") {
        throw "Broker/server mismatch."
    }
    if (-not $Meta.terminal.connected) {
        throw "Terminal is disconnected."
    }
    if ($Meta.account.currency -ne "USD" -or
        [int]$Meta.account.trade_mode_code -ne 0 -or
        [int]$Meta.account.margin_mode_code -ne 2 -or
        [int]$Meta.account.leverage -ne 100) {
        throw "Reviewed DEMO account identity/mode mismatch."
    }
    if (-not $Meta.account.trade_allowed -or -not $Meta.account.automated_trading_allowed) {
        throw "Trading permission is unavailable."
    }

    $UsdJpyMatches = @($Meta.symbols | Where-Object { $_.name -eq "USDJPY" })
    if ($UsdJpyMatches.Count -ne 1) {
        throw "USDJPY metadata is missing or ambiguous."
    }
    $UsdJpy = $UsdJpyMatches[0]

    if ($UsdJpy.base_currency -ne "USD" -or $UsdJpy.quote_currency -ne "JPY" -or
        [int]$UsdJpy.trade_mode_code -ne 4) {
        throw "USDJPY identity or trade mode mismatch."
    }
    $VolumeMin = Convert-InvariantDecimal -Value ([string]$UsdJpy.volume_min) -Name "USDJPY volume_min"
    $VolumeStep = Convert-InvariantDecimal -Value ([string]$UsdJpy.volume_step) -Name "USDJPY volume_step"
    if ($VolumeMin -ne [decimal]"0.01" -or $VolumeStep -ne [decimal]"0.01") {
        throw "USDJPY volume grid differs from the reviewed contract."
    }
    if ([int]$UsdJpy.reported_spread_points -gt 50) {
        throw "USDJPY spread exceeds the reviewed maximum."
    }

    $InitialAge = Assert-FreshObservation -Symbol $UsdJpy -MaximumAgeSeconds $MetadataMaxAgeSeconds
    Write-Host "USDJPY Bid:" $UsdJpy.bid
    Write-Host "USDJPY Ask:" $UsdJpy.ask
    Write-Host "Spread points:" $UsdJpy.reported_spread_points
    Write-Host "Quote age seconds:" ([math]::Round($InitialAge, 2))

    $SecretLine = Get-Content .env |
        Where-Object { $_ -match '^FX_DEMO_EXECUTION_SECRET=' } |
        Select-Object -First 1
    if (-not $SecretLine) {
        throw "FX_DEMO_EXECUTION_SECRET is missing."
    }
    $ExecutionToken = ($SecretLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if ($ExecutionToken.Length -lt 32) {
        throw "Execution token is invalid."
    }

    $ExecutionStatus = Invoke-RestMethod -Method Get `
        -Uri "http://127.0.0.1:8000/v1/demo-execution/status" `
        -Headers @{ "X-FX-Execution-Token" = $ExecutionToken } `
        -TimeoutSec 5

    if ($ExecutionStatus.trading_mode -ne "demo" -or
        -not $ExecutionStatus.execution_enabled -or
        $ExecutionStatus.live_mode -ne "forbidden" -or
        $ExecutionStatus.node_id -ne "local-demo-node") {
        throw "Local execution API is not in the reviewed DEMO state."
    }

    $Unresolved = @(
        $ExecutionStatus.counts.PSObject.Properties |
        Where-Object {
            $_.Name -notin @("position_confirmed", "rejected") -and [int]$_.Value -gt 0
        }
    )
    if ($Unresolved.Count -gt 0) {
        throw "Durable execution state is unresolved; manual reconciliation is required."
    }

    $Now = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $RequestId = [guid]::NewGuid().ToString()
    $Payload = [ordered]@{
        schema_version = "1.0"
        request_id = $RequestId
        timestamp = $Now
        nonce = "usdjpy-demo-" + [guid]::NewGuid().ToString("N")
        node_id = "local-demo-node"
        market = [ordered]@{
            snapshot_id = [guid]::NewGuid().ToString()
            symbol = "USDJPY"
            observed_at = [string]$UsdJpy.observed_at
            bid = [string]$UsdJpy.bid
            ask = [string]$UsdJpy.ask
            previous_close = $PreviousCloseValue.ToString(
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        }
        account = [ordered]@{
            account_id = "fibo-demo-usd-local"
            observed_at = $Now
            balance = $BalanceValue.ToString([System.Globalization.CultureInfo]::InvariantCulture)
            equity = $EquityValue.ToString([System.Globalization.CultureInfo]::InvariantCulture)
            daily_realized_pnl = $DailyPnlValue.ToString(
                [System.Globalization.CultureInfo]::InvariantCulture
            )
            open_position_count = $OpenPositionCount
            currency = "USD"
        }
        conversion_rates = @()
        inverse_conversion_quotes = @(
            [ordered]@{
                source_currency = "JPY"
                target_currency = "USD"
                source_symbol = "USDJPY"
                pair_base_currency = "USD"
                pair_quote_currency = "JPY"
                bid = [string]$UsdJpy.bid
                ask = [string]$UsdJpy.ask
                observed_at = [string]$UsdJpy.observed_at
            }
        )
    }

    $Body = $Payload | ConvertTo-Json -Depth 10 -Compress
    $BodyBytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
    $Headers = @{}

    $HmacLine = Get-Content .env |
        Where-Object { $_ -match '^FX_HMAC_SECRET=' } |
        Select-Object -First 1
    if ($HmacLine) {
        $HmacSecret = ($HmacLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
        if ($HmacSecret) {
            $Hmac = New-Object System.Security.Cryptography.HMACSHA256
            try {
                $Hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($HmacSecret)
                $Digest = $Hmac.ComputeHash($BodyBytes)
                $Hex = -join ($Digest | ForEach-Object { $_.ToString("x2") })
                $Headers["X-FX-Signature"] = "sha256=$Hex"
            }
            finally {
                $Hmac.Dispose()
            }
        }
    }

    $FinalAge = Assert-FreshObservation -Symbol $UsdJpy -MaximumAgeSeconds $MetadataMaxAgeSeconds
    Write-Host "Final quote age seconds:" ([math]::Round($FinalAge, 2))
    Write-Host "Submitting exactly ONE USDJPY DEMO decision."
    Write-Host "Request ID:" $RequestId
    Write-Host "No automatic retry is permitted."

    $SubmissionStarted = $true
    $Response = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:8000/v1/decision" `
        -Headers $Headers `
        -ContentType "application/json; charset=utf-8" `
        -Body $BodyBytes `
        -TimeoutSec 5

    $Response | ConvertTo-Json -Depth 10
}
catch {
    if ($SubmissionStarted) {
        Write-Error (
            "Submission outcome may be ambiguous for request_id=$RequestId. " +
            "DO NOT rerun. Disable the EA if broker state is uncertain and reconcile manually. " +
            $_.Exception.Message
        )
    }
    else {
        Write-Error ("BLOCKED before submission: " + $_.Exception.Message)
    }
    exit 1
}
finally {
    Remove-Variable ExecutionToken -ErrorAction SilentlyContinue
    Remove-Variable HmacSecret -ErrorAction SilentlyContinue
    Remove-Variable BodyBytes -ErrorAction SilentlyContinue
}
