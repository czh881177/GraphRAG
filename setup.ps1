# setup.ps1
# 环境检查脚本（组长 A 提供）— 检查 环境 / 依赖 / Neo4j / .env 四项
# 用法：powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "医药 GraphRAG · 环境检查" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
$pass = 0; $fail = 0

# 1) Python
Write-Host "[1/4] Python" -ForegroundColor Yellow
try {
    $py = python --version 2>&1
    Write-Host "  ✓ $py"
    $pass++
} catch {
    Write-Host "  ✗ Python 未安装或不在 PATH（建议 conda create -n graphragexpr python=3.12）" -ForegroundColor Red
    $fail++
}

# 2) Python 依赖
Write-Host "[2/4] Python 依赖（requirements.txt）" -ForegroundColor Yellow
try {
    python -c "import neo4j, flask, openai, dotenv, pydantic; print('  ✓ 核心依赖已安装')" 2>$null
    if ($LASTEXITCODE -eq 0) { $pass++ }
    else {
        Write-Host "  ✗ 依赖缺失，执行：python -m pip install -r requirements.txt" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "  ✗ 依赖缺失，执行：python -m pip install -r requirements.txt" -ForegroundColor Red
    $fail++
}

# 3) Neo4j
Write-Host "[3/4] Neo4j（默认 bolt://localhost:7687）" -ForegroundColor Yellow
$port = Test-NetConnection -ComputerName localhost -Port 7687 -WarningAction SilentlyContinue
if ($port.TcpTestSucceeded) {
    Write-Host "  ✓ 7687 端口可连接" -ForegroundColor Green
    $pass++
} else {
    Write-Host "  ✗ Neo4j 未运行。请先启动 Neo4j 5.x（本机服务或 Docker）" -ForegroundColor Red
    Write-Host "    Docker: docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/12345678 neo4j:5-community"
    $fail++
}

# 4) .env
Write-Host "[4/4] .env 配置" -ForegroundColor Yellow
if (Test-Path ".env") {
    $envOk = $true
    foreach ($k in @("NEO4J_URL","NEO4J_USER","NEO4J_PASSWORD","LLM_TOKEN")) {
        $v = (Select-String -Path ".env" -Pattern "^$k=" -Quiet)
        if (-not $v) { Write-Host "  ✗ 缺少 $k" -ForegroundColor Red; $envOk = $false }
    }
    if ($envOk) { Write-Host "  ✓ .env 存在且含必要字段" -ForegroundColor Green; $pass++ }
    else { $fail++ }
} else {
    Write-Host "  ✗ 未找到 .env（请执行 copy .env.example .env 并填写）" -ForegroundColor Red
    $fail++
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "结果：通过 $pass / 4，失败 $fail / 4" -ForegroundColor $(if ($fail -eq 0) {"Green"} else {"Red"})
if ($fail -gt 0) {
    Write-Host "请按上述提示修复后重跑本脚本。" -ForegroundColor Yellow
} else {
    Write-Host "环境就绪！下一步：python scripts/init_schema.py" -ForegroundColor Green
}
