# run_tests.ps1
# Script to run all tests with proper environment setup

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GraphRAG Test Suite" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if conda environment is active
if ($env:CONDA_DEFAULT_ENV -ne "graphragexpr") {
    Write-Host "Error: Please activate the graphragexpr conda environment first:" -ForegroundColor Red
    Write-Host "  conda activate graphragexpr" -ForegroundColor Yellow
    exit 1
}

# Check if Neo4j is running
Write-Host "Checking Neo4j connection..." -ForegroundColor Yellow
try {
    $result = python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678')); driver.verify_connectivity(); print('OK')"
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

# Run pytest with conda's Python
$env:PYTHONIOENCODING = "utf-8"
python -m pytest -v --tb=short

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test run completed" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
