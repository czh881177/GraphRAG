# build_kg_dyn.ps1
# Script to build knowledge graph from The Story of The Stone (红楼梦)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building Knowledge Graph - 红楼梦" -ForegroundColor Cyan
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
$env:PYTHONIOENCODING = "utf-8"
try {
    $result = python -c "from dotenv import load_dotenv; load_dotenv(); import os; from neo4j import GraphDatabase; driver = GraphDatabase.driver(os.getenv('NEO4J_URL'), auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))); driver.verify_connectivity(); print('OK')"
    if ($result -eq "OK") {
        Write-Host "✓ Neo4j connected" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Neo4j connection failed" -ForegroundColor Red
    Write-Host "Please start Neo4j first" -ForegroundColor Yellow
    exit 1
}

# Check if origdata/orig.txt exists
if (-not (Test-Path "origdata\orig.txt")) {
    Write-Host "✗ Error: origdata\orig.txt not found" -ForegroundColor Red
    Write-Host "Please ensure The Story of The Stone text file exists" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Testing data extraction..." -ForegroundColor Yellow
python graphragexpr\extract\sample_data_dyn.py

Write-Host ""
Write-Host "Building knowledge graph from 红楼梦..." -ForegroundColor Yellow
Write-Host ""

python graphragexpr\extract\build_kg_dyn.py

Write-Host ""
Write-Host "Creating vector index..." -ForegroundColor Yellow
python graphragexpr\extract\create_index.py

Write-Host ""
Write-Host "Creating fulltext index..." -ForegroundColor Yellow
python -c "
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')),
)

with driver.session() as session:
    try:
        session.run('''
            CREATE FULLTEXT INDEX text_fulltext IF NOT EXISTS
            FOR (n:Chunk)
            ON EACH [n.text]
        ''')
        print('✓ Fulltext index created: text_fulltext')
    except Exception as e:
        print(f'Error creating fulltext index: {e}')

driver.close()
"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Knowledge graph build completed" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
