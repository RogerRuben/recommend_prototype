param(
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) "deliverables\source_no_wheels"),
    [string]$PackageName = "IndustrialProtocolDemo_V19_6_V11_Source_NoWheels_20260813_R11_RelaxedHttpV10Workbench"
)

$ErrorActionPreference = "Stop"
$root = (Split-Path -Parent $PSScriptRoot)
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
$stage = Join-Path $output $PackageName
$zipPath = Join-Path $output ($PackageName + ".zip")
$hashPath = $zipPath + ".sha256"

New-Item -ItemType Directory -Force -Path $output | Out-Null
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
if (Test-Path -LiteralPath $hashPath) { Remove-Item -LiteralPath $hashPath -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "runtime") | Out-Null
Set-Content -LiteralPath (Join-Path $stage "runtime\.keep") -Value "Runtime workspace; no virtual environment is included." -Encoding ASCII

$directories = @(
    "app", "config", "data", "data_master", "deliveries", "deploy", "docs", "examples", "models",
    "outputs", "services", "tests", "tools"
)
foreach ($relative in $directories) {
    $source = Join-Path $root $relative
    if (Test-Path -LiteralPath $source) {
        $destination = Join-Path $stage $relative
        New-Item -ItemType Directory -Force -Path $destination | Out-Null
        & robocopy $source $destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS `
            /XD node_modules wheelhouse_win7 runtime_state __pycache__ .pytest_cache venv .venv frozen_effect_v11_v2_inspection frozen_v11_v2_installed_smoke `
            /XF *.whl *.pyc *.pyo *.log *.rar | Out-Null
        if ($LASTEXITCODE -gt 7) {
            throw "Failed to copy source directory $relative (robocopy exit code $LASTEXITCODE)."
        }
    }
}

$rootExtensions = @(".bat", ".json", ".md", ".py", ".txt", ".ipynb", ".sh")
Get-ChildItem -LiteralPath $root -File | Where-Object {
    $rootExtensions -contains $_.Extension.ToLowerInvariant()
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stage $_.Name) -Force
}

# Keep the source archive independently demonstrable: include the verified
# product delivery and the raw-table/two-model fixture used by the operator guide.
$deliveryDirectory = Join-Path $stage "deliveries"
New-Item -ItemType Directory -Force -Path $deliveryDirectory | Out-Null
$deliveryArchive = Get-ChildItem -LiteralPath (Join-Path $root "outputs") -File -Filter "*.zip" | Where-Object {
    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq "2C4585F899A9C8E2991F5D3FAFFB8D455E42081DFE315BA997916B4F85DD190C"
} | Select-Object -First 1
if ($deliveryArchive) {
    Copy-Item -LiteralPath $deliveryArchive.FullName -Destination (Join-Path $deliveryDirectory $deliveryArchive.Name) -Force
    $deliveryHash = $deliveryArchive.FullName + ".sha256"
    if (Test-Path -LiteralPath $deliveryHash) {
        Copy-Item -LiteralPath $deliveryHash -Destination (Join-Path $deliveryDirectory ([System.IO.Path]::GetFileName($deliveryHash))) -Force
    }
}
$fixtureSource = Join-Path $root "outputs\019fb26c_basic_aircraft_door_lock_models_20260812"
$fixtureDestination = Join-Path $stage "examples\basic_aircraft_door_lock"
if (Test-Path -LiteralPath $fixtureSource) {
    New-Item -ItemType Directory -Force -Path $fixtureDestination | Out-Null
    & robocopy $fixtureSource $fixtureDestination /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS `
        /XD node_modules wheelhouse_win7 runtime_state __pycache__ .pytest_cache venv .venv `
        /XF *.whl *.pyc *.pyo *.log *.rar | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy the aircraft door lock example fixture (robocopy exit code $LASTEXITCODE)."
    }
}

$excludedDirectoryNames = @("wheelhouse_win7", "runtime_state", "__pycache__", ".pytest_cache", "node_modules", "venv", ".venv", "frozen_effect_v11_v2_inspection", "frozen_v11_v2_installed_smoke")
Get-ChildItem -LiteralPath $stage -Directory -Recurse | Where-Object {
    $excludedDirectoryNames -contains $_.Name
} | Sort-Object FullName -Descending | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

$excludedExtensions = @(".whl", ".pyc", ".pyo", ".log", ".rar")
Get-ChildItem -LiteralPath $stage -File -Recurse | Where-Object {
    $excludedExtensions -contains $_.Extension.ToLowerInvariant()
} | Remove-Item -Force

$manifest = [ordered]@{
    package_name = $PackageName
    generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    package_type = "installable-source-with-model-artifacts"
    wheels_included = $false
    virtual_environment_included = $false
    effectiveness_runtime = "services/effectiveness_service/model/current/effectiveness_runtime_manifest.json"
    price_runtime = "services/price_service/model/price_native_bundle.pkl"
    production_candidate_generator = "V19.6.8 hybrid coupling-aware fast/deep beam search"
    effectiveness_model_install = "INSTALL_FROZEN_EFFECTIVENESS_MODEL_WIN7.bat (recommended frozen ZIP) or PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat (legacy compatible)"
    effectiveness_workbench = "http://127.0.0.1:17891/effectiveness"
    experimental_candidate_generator = "app/gflownet_generator.py (isolated; not enabled by the recommendation UI)"
    install_script = "INSTALL_SOURCE_DEPENDENCIES_WIN7.bat"
    start_script = "START_ALL_SERVICES_WIN7.bat"
    experiment_script = "RUN_GFLOWNET_CANDIDATE_EXPERIMENT.bat"
    excluded = @("wheelhouse_win7", "runtime/venvs", "backups", "logs", "*.whl", "*.pyc", "*.log", "handoff archives")
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage "SOURCE_PACKAGE_MANIFEST.json") -Encoding UTF8

$guideLines = @(
    "# Source deployment package without wheels",
    "",
    "This package includes the recommendation system, model services, current model artifacts, test data, documentation and tests. It does not include wheels or a virtual environment.",
    "",
    "1. Install 64-bit Python 3.8.",
    "2. With Internet or an internal pip mirror, run INSTALL_SOURCE_DEPENDENCIES_WIN7.bat.",
    "3. For an offline target, provide dependency wheels separately or copy an accepted runtime\venvs\model_runtime38. Wheels are intentionally absent here.",
    "4. Run VERIFY_MODEL_ENVIRONMENTS.bat.",
    "5. Run START_ALL_SERVICES_WIN7.bat. Readiness requires matching product_code plus one real numeric price/effectiveness response; Schema differences are warnings rather than deployment blockers.",
    "6. Open http://127.0.0.1:17891/; use /admin for data maintenance and /effectiveness for operator effectiveness evaluation.",
    "7. In Product Data Workspace, ordinary historical CSV/XLSX data can be analyzed, edited and switched independently of the currently running HTTP model product.",
    "8. A business/model mismatch pauses model calculations only; it does not block data maintenance, switching, or historical-product recommendation.",
    "9. Train and export a price service bundle from one history table with TRAIN_PRICE_SERVICE_MODEL_WIN7.bat. No model-dir, fixed model count or Notebook is required.",
    "10. The data center model page reads HTTP health/schema and produces example JSON. It does not load local model files in service mode.",
    "11. GFlowNet is an isolated experiment and is not called by the normal recommendation UI. Run RUN_GFLOWNET_CANDIDATE_EXPERIMENT.bat only when you want the benchmark.",
    "",
    "Online effectiveness learning is external. Prefer INSTALL_FROZEN_EFFECTIVENESS_MODEL_WIN7.bat for effectiveness_model_*.zip exported by the final V11 expert software.",
    "The legacy source + Workbook + State path remains available through PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat."
)
$guideLines | Set-Content -LiteralPath (Join-Path $stage "DEPLOYMENT_README_NO_WHEELS.md") -Encoding UTF8

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stage, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
("{0}  {1}" -f $hash, [System.IO.Path]::GetFileName($zipPath)) | Set-Content -LiteralPath $hashPath -Encoding ASCII

$wheelCount = @(Get-ChildItem -LiteralPath $stage -File -Recurse -Filter "*.whl").Count
$pycCount = @(
    Get-ChildItem -LiteralPath $stage -File -Recurse | Where-Object {
        $_.Extension.ToLowerInvariant() -in @(".pyc", ".pyo")
    }
).Count
if ($wheelCount -ne 0 -or $pycCount -ne 0) {
    throw "Excluded binary dependency/cache files remain in the staged package."
}
if (-not (Test-Path -LiteralPath (Join-Path $stage "services\effectiveness_service\model\current\effectiveness_runtime_manifest.json"))) {
    throw "Current effectiveness artifact is missing from the staged package."
}
if (-not (Test-Path -LiteralPath (Join-Path $stage "services\price_service\model\price_native_bundle.pkl"))) {
    throw "Current price artifact is missing from the staged package."
}

[pscustomobject]@{
    Package = $zipPath
    Sha256 = $hash
    SizeMB = [Math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
    Wheels = $wheelCount
} | Format-List
