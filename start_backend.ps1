# start_backend.ps1
# Script to start the backend API server

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GraphRAG Backend API" -ForegroundColor Cyan
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
Write-Host "Starting backend server..." -ForegroundColor Yellow
Write-Host "API will be available at: http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
python backend\api.py
