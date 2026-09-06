# build_kg_dyn.ps1
# 医药 GraphRAG · 建图管线（B 数据/图谱 入口）
# 前置：.venv（Python 3.12）+ Neo4j 已启动 + scripts/init_schema.py 已初始化索引

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Building Knowledge Graph (医药版)" -ForegroundColor Cyan
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

$env:PYTHONIOENCODING = "utf-8"

# 1) Neo4j 连通性
Write-Host "1/4 检查 Neo4j 连接..." -ForegroundColor Yellow
try {
    $result = & $py -c "from dotenv import load_dotenv; load_dotenv(); import os; from neo4j import GraphDatabase; driver = GraphDatabase.driver(os.getenv('NEO4J_URL'), auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))); driver.verify_connectivity(); print('OK')"
    if ($result -eq "OK") { Write-Host "✓ Neo4j connected" -ForegroundColor Green }
} catch {
    Write-Host "✗ Neo4j connection failed，请先启动 Neo4j" -ForegroundColor Red
    exit 1
}

# 2) 语料分块
Write-Host "2/4 清洗并分块语料 -> data/processed/chunks.json ..." -ForegroundColor Yellow
& $py "$PSScriptRoot\scripts\prepare_corpus.py"

# 3) 离线抽取结果
Write-Host "3/4 生成离线抽取结果 -> data/processed/extracted.json ..." -ForegroundColor Yellow
& $py "$PSScriptRoot\scripts\generate_extracted.py"

# 4) 初始化 Schema（幂等）+ 建图入库
Write-Host "4/4 初始化 Schema 并建图入库 ..." -ForegroundColor Yellow
& $py "$PSScriptRoot\scripts\init_schema.py"
& $py "$PSScriptRoot\graphragexpr\extract\build_kg_dyn.py"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Knowledge graph build completed" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
