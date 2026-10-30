param(
    [Parameter(Mandatory = $true)][string]$Mt5DataPath,
    [Parameter(Mandatory = $true)][string]$ExpectedCommit,
    [Parameter(Mandatory = $true)][string]$Balance,
    [Parameter(Mandatory = $true)][string]$Equity,
    [Parameter(Mandatory = $true)][string]$DailyRealizedPnl,
    [Parameter(Mandatory = $true)][ValidateRange(0, 0)][int]$OpenPositionCount,
    [ValidateRange(1, 15)][int]$MetadataMaxAgeSeconds = 15
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$SubmissionStarted = $false
$RequestId = $null
$ExecutionId = $null
$ReviewedDeviationPoints = [decimal]"10"
$RequiredSecondaryMarginPoints = [decimal]"10000"

function D([object]$Value) {
    return [decimal]::Parse([string]$Value, [System.Globalization.CultureInfo]::InvariantCulture)
}

function S([decimal]$Value) {
    return $Value.ToString([System.Globalization.CultureInfo]::InvariantCulture)
}

function Fresh([object]$Symbol) {
    $Observed = [DateTimeOffset]::Parse(
        [string]$Symbol.observed_at,
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $Age = ([DateTimeOffset]::UtcNow - $Observed.ToUniversalTime()).TotalSeconds
    if ($Age -lt -2 -or $Age -gt $MetadataMaxAgeSeconds) {
        throw "Fresh USDJPY metadata is required; no decision was submitted."
    }
    return $Age
}

function Count([object]$Counts, [string]$Name) {
    $Property = $Counts.PSObject.Properties[$Name]
    if ($null -eq $Property) { return 0 }
    return [int]$Property.Value
}

try {
    if ($env:OS -ne "Windows_NT") { throw "Windows trading node required." }
    Set-Location (Resolve-Path "$PSScriptRoot\..")
    if (-not (Test-Path ".env" -PathType Leaf)) { throw ".env is required." }
    if (-not (Test-Path $Mt5DataPath -PathType Container)) { throw "MT5 data path missing." }
    if (@(git status --porcelain).Count -ne 0) { throw "Clean worktree required." }
    $ActualCommit = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $ActualCommit -ne $ExpectedCommit) {
        throw "Git HEAD does not match the reviewed commit."
    }

    $BalanceValue = D $Balance
    $EquityValue = D $Equity
    $DailyPnlValue = D $DailyRealizedPnl
    if ($BalanceValue -le 0 -or $EquityValue -lt 0) { throw "Account values invalid." }

    $MetadataPath = Join-Path $Mt5DataPath "MQL5\Files\arsam_mt5_metadata_1_0.json"
    $Meta = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
    if ($Meta.schema_version -ne "1.0" -or
        $Meta.mode -ne "read_only_metadata_probe" -or
        $Meta.source_type -ne "mql5_metadata_probe" -or
        $Meta.broker.company -ne "FIBO Group, Ltd" -or
        $Meta.broker.server -ne "FIBOGroup-MT5 Server" -or
        -not $Meta.terminal.connected) {
        throw "Metadata identity/transport mismatch."
    }
    if ($Meta.account.currency -ne "USD" -or
        [int]$Meta.account.trade_mode_code -ne 0 -or
        [int]$Meta.account.margin_mode_code -ne 2 -or
        [int]$Meta.account.leverage -ne 100 -or
        -not $Meta.account.trade_allowed -or
        -not $Meta.account.automated_trading_allowed) {
        throw "Reviewed DEMO account mismatch."
    }

    $Matches = @($Meta.symbols | Where-Object { $_.name -eq "USDJPY" })
    if ($Matches.Count -ne 1) { throw "USDJPY metadata missing or ambiguous." }
    $UsdJpy = $Matches[0]
    if ($UsdJpy.base_currency -ne "USD" -or
        $UsdJpy.quote_currency -ne "JPY" -or
        [int]$UsdJpy.trade_mode_code -ne 4 -or
        (D $UsdJpy.volume_min) -ne [decimal]"0.01" -or
        (D $UsdJpy.volume_step) -ne [decimal]"0.01" -or
        [int]$UsdJpy.reported_spread_points -gt 50) {
        throw "USDJPY reviewed contract mismatch."
    }

    $InitialAge = Fresh $UsdJpy
    $ActualBid = D $UsdJpy.bid
    $ActualAsk = D $UsdJpy.ask
    $Point = D $UsdJpy.point
    $TickSize = D $UsdJpy.tick_size
    if ($ActualBid -le 0 -or $ActualAsk -lt $ActualBid -or $Point -le 0 -or $TickSize -le 0) {
        throw "USDJPY price metadata invalid."
    }

    $Spread = $ActualAsk - $ActualBid
    $SyntheticBid = [decimal]::Floor(($ActualBid / [decimal]"2") / $TickSize) * $TickSize
    $SyntheticAsk = $SyntheticBid + $Spread
    $ExpectedStopLoss = $SyntheticBid + ([decimal]"100" * $TickSize)
    $ExpectedTakeProfit = $SyntheticBid - ([decimal]"200" * $TickSize)
    $SyntheticPreviousClose = $SyntheticAsk + ([decimal]"1000" * $Point)
    $DriftPoints = ($ActualBid - $SyntheticBid) / $Point
    $SecondaryMarginPoints = ($ActualBid - $ExpectedStopLoss) / $Point

    if ($SyntheticBid -le 0 -or $ExpectedTakeProfit -le 0 -or
        $SyntheticAsk -ge $SyntheticPreviousClose) {
        throw "Synthetic SELL setup invalid."
    }
    if ($DriftPoints -le $ReviewedDeviationPoints) {
        throw "Synthetic intent does not exceed the drift threshold."
    }
    if ($ExpectedStopLoss -ge $ActualAsk) {
        throw "Secondary SELL stop-direction guard is not independently invalid."
    }
    if ($SecondaryMarginPoints -lt $RequiredSecondaryMarginPoints) {
        throw "Secondary stop-direction safety margin is too small."
    }

    $SecretLine = Get-Content .env | Where-Object { $_ -match '^FX_DEMO_EXECUTION_SECRET=' } | Select-Object -First 1
    if (-not $SecretLine) { throw "FX_DEMO_EXECUTION_SECRET missing." }
    $ExecutionToken = ($SecretLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if ($ExecutionToken.Length -lt 32) { throw "Execution token invalid." }

    $StatusArgs = @{
        Method = "Get"
        Uri = "http://127.0.0.1:8000/v1/demo-execution/status"
        Headers = @{ "X-FX-Execution-Token" = $ExecutionToken }
        TimeoutSec = 5
    }
    $Before = Invoke-RestMethod @StatusArgs
    if ($Before.trading_mode -ne "demo" -or
        -not $Before.execution_enabled -or
        $Before.live_mode -ne "forbidden" -or
        $Before.node_id -ne "local-demo-node") {
        throw "Execution API is not in reviewed DEMO state."
    }
    $Unresolved = @(
        $Before.counts.PSObject.Properties |
        Where-Object {
            $_.Name -notin @("position_confirmed", "rejected") -and [int]$_.Value -gt 0
        }
    )
    if ($Unresolved.Count -gt 0) { throw "Durable execution state unresolved." }
    $BaselineConfirmed = Count $Before.counts "position_confirmed"
    $BaselineRejected = Count $Before.counts "rejected"

    $Now = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $RequestId = [guid]::NewGuid().ToString()
    $Payload = [ordered]@{
        schema_version = "1.0"
        request_id = $RequestId
        timestamp = $Now
        nonce = "usdjpy-drift-negative-" + [guid]::NewGuid().ToString("N")
        node_id = "local-demo-node"
        market = [ordered]@{
            snapshot_id = [guid]::NewGuid().ToString()
            symbol = "USDJPY"
            observed_at = [string]$UsdJpy.observed_at
            bid = S $SyntheticBid
            ask = S $SyntheticAsk
            previous_close = S $SyntheticPreviousClose
        }
        account = [ordered]@{
            account_id = "fibo-demo-usd-local"
            observed_at = $Now
            balance = S $BalanceValue
            equity = S $EquityValue
            daily_realized_pnl = S $DailyPnlValue
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
                bid = S $SyntheticBid
                ask = S $SyntheticAsk
                observed_at = [string]$UsdJpy.observed_at
            }
        )
    }

    $Body = $Payload | ConvertTo-Json -Depth 10 -Compress
    $BodyBytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
    $Headers = @{}
    $HmacLine = Get-Content .env | Where-Object { $_ -match '^FX_HMAC_SECRET=' } | Select-Object -First 1
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
            finally { $Hmac.Dispose() }
        }
    }

    $FinalAge = Fresh $UsdJpy
    Write-Host "NEGATIVE DRIFT TEST ONLY - no broker order is expected."
    Write-Host "Actual Bid:" (S $ActualBid)
    Write-Host "Synthetic SELL requested price:" (S $SyntheticBid)
    Write-Host "Expected SL:" (S $ExpectedStopLoss)
    Write-Host "Expected TP:" (S $ExpectedTakeProfit)
    Write-Host "Intent drift points:" ([math]::Round([double]$DriftPoints, 2))
    Write-Host "Secondary stop-direction margin points:" ([math]::Round([double]$SecondaryMarginPoints, 2))
    Write-Host "Quote age initial/final:" ([math]::Round($InitialAge, 2)) "/" ([math]::Round($FinalAge, 2))
    Write-Host "Submitting exactly ONE synthetic USDJPY DEMO decision."
    Write-Host "Request ID:" $RequestId
    Write-Host "No automatic retry is permitted."

    $SubmissionStarted = $true
    $PostArgs = @{
        Method = "Post"
        Uri = "http://127.0.0.1:8000/v1/decision"
        Headers = $Headers
        ContentType = "application/json; charset=utf-8"
        Body = $BodyBytes
        TimeoutSec = 5
    }
    $Response = Invoke-RestMethod @PostArgs
    $Response | ConvertTo-Json -Depth 10
    if ($Response.status -ne "demo_queued" -or
        $Response.execution_status -ne "pending" -or
        $null -eq $Response.execution_id) {
        throw "Negative-test decision was not queued as expected."
    }
    $ExecutionId = [string]$Response.execution_id

    for ($Attempt = 0; $Attempt -lt 8; $Attempt++) {
        Start-Sleep -Milliseconds 750
        $After = Invoke-RestMethod @StatusArgs
        $Confirmed = Count $After.counts "position_confirmed"
        $Rejected = Count $After.counts "rejected"
        if ($Confirmed -ne $BaselineConfirmed) {
            throw "FAIL CLOSED: position_confirmed changed during the negative drift test."
        }
        $Unexpected = @(
            $After.counts.PSObject.Properties |
            Where-Object {
                $_.Name -notin @("position_confirmed", "rejected") -and [int]$_.Value -gt 0
            }
        )
        if ($Rejected -eq ($BaselineRejected + 1) -and $Unexpected.Count -eq 0) {
            Write-Host "NEGATIVE DRIFT TEST DURABLE REJECTION OBSERVED."
            Write-Host "Execution ID:" $ExecutionId
            Write-Host "position_confirmed unchanged at:" $Confirmed
            Write-Host "rejected incremented to:" $Rejected
            Write-Host "Verify Experts reason is intent_price_drift_exceeded, then disable the EA."
            exit 0
        }
    }
    throw "No clean rejected state observed. Disable EA and reconcile manually."
}
catch {
    if ($SubmissionStarted) {
        Write-Error (
            "Negative-test submission outcome requires reconciliation for request_id=$RequestId " +
            "execution_id=$ExecutionId. DO NOT rerun. Disable the EA and reconcile manually. " +
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
