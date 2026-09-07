# run_tests.ps1
# Script to run all tests with proper environment setup

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GraphRAG Test Suite" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Python 环境解析：优先 .venv，其次 conda graphragexpr
$py = $null
if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") {
    $py = "$PSScriptRoot\.venv\Scripts\python.exe"
    Write-Host "✓ 使用 .venv Python 环境" -ForegroundColor Green
} elseif ($env:CONDA_DEFAULT_ENV -eq "graphragexpr") {
    $py = "python"
    Write-Host "✓ 使用 conda graphragexpr 环境" -ForegroundColor Green
} else {
    Write-Host "Error: 未找到 Python 环境，请先执行: .venv\Scripts\activate 或 conda activate graphragexpr" -ForegroundColor Red
    exit 1
}

# Check if Neo4j is running
Write-Host "Checking Neo4j connection..." -ForegroundColor Yellow
try {
    $result = & $py -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678')); driver.verify_connectivity(); print('OK')"
    if ($result -eq "OK") {
        Write-Host "✓ Neo4j connected" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Neo4j connection failed" -ForegroundColor Red
    Write-Host "Please start Neo4j first" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Running tests..." -ForegroundColor Yellow
Write-Host ""

# Run pytest with venv/conda Python
$env:PYTHONIOENCODING = "utf-8"
& $py -m pytest -v --tb=short

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test run completed" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
