# build_kg.ps1
# Script to build knowledge graph from sample data (legacy, uses build_kg_simple)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building Knowledge Graph" -ForegroundColor Cyan
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
Write-Host "Running knowledge graph builder..." -ForegroundColor Yellow
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py graphragexpr\extract\build_kg_simple.py

Write-Host ""
Write-Host "Creating vector index..." -ForegroundColor Yellow
& $py graphragexpr\extract\create_index.py

Write-Host ""
Write-Host "Creating fulltext index..." -ForegroundColor Yellow
& $py -c "
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
