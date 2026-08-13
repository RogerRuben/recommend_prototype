[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),

    [Parameter(Mandatory = $false)]
    [string]$OutputDir = (Join-Path (Split-Path -Parent $PSScriptRoot) "deliverables\offline_delivery")
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$MaxArchiveBytes = 80MB
$BuildTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project root does not exist: $ProjectRoot"
}
if (Test-Path -LiteralPath $OutputDir) {
    $existing = @(Get-ChildItem -LiteralPath $OutputDir -Force -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        throw "Output directory is not empty. Use a new directory: $OutputDir"
    }
} else {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$StageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ipd_stage_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $StageRoot | Out-Null

function Copy-RelativeFile {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )
    $target = Join-Path $DestinationRoot $RelativePath
    $targetDir = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $target -Force
}

function Get-RelativeProjectPath {
    param([Parameter(Mandatory = $true)][string]$FullName)
    return $FullName.Substring($ProjectRoot.Length).TrimStart('\', '/')
}

function Test-CommonExcludedFile {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $normal = $RelativePath.Replace('/', '\')
    if ($normal -match '(^|\\)__pycache__(\\|$)') { return $true }
    if ($normal -match '\.py[co]$') { return $true }
    if ($normal -match '(^|\\)\.pytest_cache(\\|$)') { return $true }
    return $false
}

function Copy-CoreProject {
    param([Parameter(Mandatory = $true)][string]$DestinationRoot)

    $excludedTopDirectories = @(
        '.git', '.agents', '.codex', 'runtime', 'outputs', 'backups',
        'logs', 'deploy', 'deliverables', 'exports', 'uploads', '__pycache__'
    )

    foreach ($item in Get-ChildItem -LiteralPath $ProjectRoot -Force) {
        if ($item.PSIsContainer) {
            if ($excludedTopDirectories -contains $item.Name) { continue }
            foreach ($file in Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force) {
                $relative = Get-RelativeProjectPath -FullName $file.FullName
                if (Test-CommonExcludedFile -RelativePath $relative) { continue }
                if ($relative.Replace('/', '\') -match '^services\\[^\\]+\\wheelhouse_win7\\') { continue }
                Copy-RelativeFile -Source $file.FullName -RelativePath $relative -DestinationRoot $DestinationRoot
            }
        } else {
            if (Test-CommonExcludedFile -RelativePath $item.Name) { continue }
            Copy-RelativeFile -Source $item.FullName -RelativePath $item.Name -DestinationRoot $DestinationRoot
        }
    }
}

function Copy-CuratedOutputTree {
    param(
        [Parameter(Mandatory = $true)][string]$OutputName,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )
    $sourceRoot = Join-Path $ProjectRoot ("outputs\" + $OutputName)
    if (-not (Test-Path -LiteralPath $sourceRoot)) { return }

    foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
        $relativeWithin = $file.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
        $normal = $relativeWithin.Replace('/', '\')
        if (Test-CommonExcludedFile -RelativePath $normal) { continue }
        if ($normal -match '(^|\\)workbook_previews(\\|$)') { continue }
        if ($normal -match '\.inspect\.ndjson$') { continue }
        if ($normal -match '\.formula_errors\.ndjson$') { continue }
        if ($normal -match '(^|\\)(finalize|workbook_inspection)\.') { continue }
        $relative = Join-Path ("outputs\" + $OutputName) $relativeWithin
        Copy-RelativeFile -Source $file.FullName -RelativePath $relative -DestinationRoot $DestinationRoot
    }
}

function Copy-Wheels {
    param(
        [Parameter(Mandatory = $true)][string]$WheelhouseRelative,
        [Parameter(Mandatory = $true)][scriptblock]$Selector,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )
    $wheelhouse = Join-Path $ProjectRoot $WheelhouseRelative
    foreach ($file in Get-ChildItem -LiteralPath $wheelhouse -File) {
        if (& $Selector $file) {
            $relative = Join-Path $WheelhouseRelative $file.Name
            Copy-RelativeFile -Source $file.FullName -RelativePath $relative -DestinationRoot $DestinationRoot
        }
    }
}

function New-ZipPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Purpose,
        [Parameter(Mandatory = $true)][bool]$RequiredForRuntime,
        [Parameter(Mandatory = $true)][scriptblock]$Populate
    )

    $stage = Join-Path $StageRoot $Name
    New-Item -ItemType Directory -Path $stage | Out-Null
    & $Populate $stage

    $fileCount = @(Get-ChildItem -LiteralPath $stage -Recurse -File).Count
    if ($fileCount -eq 0) { throw "Package is empty: $Name" }

    $zipPath = Join-Path $OutputDir ($Name + '.zip')
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal
    $zip = Get-Item -LiteralPath $zipPath
    if ($zip.Length -gt $MaxArchiveBytes) {
        throw ("Archive {0} is {1:N2} MiB, exceeding 80 MiB." -f $zip.Name, ($zip.Length / 1MB))
    }
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    return [ordered]@{
        file = $zip.Name
        purpose = $Purpose
        required_for_runtime = $RequiredForRuntime
        bytes = $zip.Length
        size_mib = [math]::Round($zip.Length / 1MB, 2)
        file_count = $fileCount
        sha256 = $hash
        archive_type = 'independent_zip_not_multivolume'
    }
}

$priceWheelhouse = 'services\price_service\wheelhouse_win7'
$effectWheelhouse = 'services\effectiveness_service\wheelhouse_win7'
$baseWheelNames = @('numpy-', 'scipy-', 'scikit_learn-', 'joblib-', 'threadpoolctl-')

$packages = @()
try {
    $packages += New-ZipPackage -Name '01_Core_And_Price_Base' `
        -Purpose 'Application, current models, database, documentation, demo products, and base price runtime wheels' `
        -RequiredForRuntime $true `
        -Populate {
            param($stage)
            Copy-CoreProject -DestinationRoot $stage
            Copy-CuratedOutputTree -OutputName 'aircraft_door_lock_data_staff_20260801' -DestinationRoot $stage
            Copy-CuratedOutputTree -OutputName 'virtual_formal_baseline' -DestinationRoot $stage
            Copy-Wheels -WheelhouseRelative $priceWheelhouse -DestinationRoot $stage -Selector {
                param($file)
                if ($file.Name -in @('README.txt', 'WHEELHOUSE_MANIFEST.json')) { return $true }
                foreach ($prefix in $baseWheelNames) {
                    if ($file.Name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
                }
                return $false
            }
        }

    $packages += New-ZipPackage -Name '02_Price_XGBoost_Runtime' `
        -Purpose 'XGBoost 1.7.6 offline wheel for the price runtime on 64-bit Windows' `
        -RequiredForRuntime $true `
        -Populate {
            param($stage)
            Copy-Wheels -WheelhouseRelative $priceWheelhouse -DestinationRoot $stage -Selector {
                param($file)
                return $file.Name.StartsWith('xgboost-', [System.StringComparison]::OrdinalIgnoreCase)
            }
        }

    $packages += New-ZipPackage -Name '03_Effectiveness_Runtime_Wheels' `
        -Purpose 'Offline wheels for the original effectiveness runtime on Windows/Python 3.8' `
        -RequiredForRuntime $true `
        -Populate {
            param($stage)
            Copy-Wheels -WheelhouseRelative $effectWheelhouse -DestinationRoot $stage -Selector { param($file) return $true }
        }

    $packages += New-ZipPackage -Name '04_Price_Training_Extra_Wheels' `
        -Purpose 'Optional offline wheels for price Notebook training, Excel, plotting, and Jupyter' `
        -RequiredForRuntime $false `
        -Populate {
            param($stage)
            Copy-Wheels -WheelhouseRelative $priceWheelhouse -DestinationRoot $stage -Selector {
                param($file)
                if ($file.Name -in @('README.txt', 'WHEELHOUSE_MANIFEST.json')) { return $false }
                if ($file.Name.StartsWith('xgboost-', [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
                foreach ($prefix in $baseWheelNames) {
                    if ($file.Name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
                }
                return $true
            }
        }

    $manifest = [ordered]@{
        format_version = 'industrial-protocol-offline-archives-1.0'
        product = 'IndustrialProtocolDemo V19.6.5'
        built_at = $BuildTime
        source_root = $ProjectRoot
        archive_policy = [ordered]@{
            maximum_bytes = $MaxArchiveBytes
            maximum_mib = 80
            multivolume = $false
            extraction = 'Extract each required ZIP completely into the same empty directory. These are independent ZIP files, not multivolume parts.'
        }
        prerequisites_not_included = @(
            '64-bit CPython 3.8 installer',
            'Microsoft Visual C++ runtime and required Windows 7 updates'
        )
        runtime_required_packages = @(
            '01_Core_And_Price_Base.zip',
            '02_Price_XGBoost_Runtime.zip',
            '03_Effectiveness_Runtime_Wheels.zip'
        )
        optional_training_package = '04_Price_Training_Extra_Wheels.zip'
        packages = $packages
    }

    $manifestPath = Join-Path $OutputDir 'DELIVERY_MANIFEST.json'
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    $checksumLines = foreach ($package in $packages) {
        '{0}  {1}' -f $package.sha256, $package.file
    }
    $checksumLines | Set-Content -LiteralPath (Join-Path $OutputDir 'SHA256SUMS.txt') -Encoding UTF8

    Copy-Item -LiteralPath (Join-Path $ProjectRoot 'docs\OFFLINE_DELIVERY_ARCHIVES.md') `
        -Destination (Join-Path $OutputDir '00_DEPLOYMENT_GUIDE.md') -Force

    $packages | ForEach-Object {
        Write-Host ("[OK] {0}  {1:N2} MiB  SHA256={2}" -f $_.file, $_.size_mib, $_.sha256)
    }
    Write-Host ("[OK] Manifest: {0}" -f $manifestPath)
}
finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    $resolvedStage = [System.IO.Path]::GetFullPath($StageRoot)
    if ($resolvedStage.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedStage).StartsWith('ipd_stage_')) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force -ErrorAction SilentlyContinue
    }
}
