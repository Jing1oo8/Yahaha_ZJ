$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $requiredFiles = @(
        "data/raw/MicroLens-50k_pairs.csv",
        "data/raw/MicroLens-50k_titles.csv",
        "data/raw/MicroLens-50k_likes_and_views.txt",
        "data/processed/split_manifest.json",
        "data/processed/items.csv",
        "data/processed/user_history.jsonl",
        "models/itemcf-0022f60b5e4b.json.gz"
    )

    $missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count -gt 0) {
        Write-Host "Missing required runtime files:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "  - $_" }
        Write-Host "Run the data preparation and final training commands in README.md."
        exit 2
    }

    Write-Host "[1/3] Running Python tests"
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE" }

    Write-Host "[2/3] Verifying frontend dependencies from lockfile"
    pnpm --dir frontend install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency verification failed with exit code $LASTEXITCODE" }

    Write-Host "[3/3] Building the production frontend"
    pnpm --dir frontend run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }

    Write-Host "Delivery verification passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
