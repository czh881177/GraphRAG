# start_neo4j.ps1
# 一键启动 Neo4j 容器（组长 A 提供）— 幂等：已在运行则跳过
# 用法：powershell -ExecutionPolicy Bypass -File start_neo4j.ps1
# 说明：本机 Docker 若为 containerd image store，镜像源配置不生效，
#       镜像已用前缀方式拉到本地并 tag 为 neo4j:5-community，直接复用即可。

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "启动 Neo4j（Docker）" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1) Docker daemon 检查
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Docker daemon 未运行，请先打开 Docker Desktop" -ForegroundColor Red
    exit 1
}

# 2) 镜像检查（缺失则提示拉取命令）
$img = docker images --format "{{.Repository}}:{{.Tag}}" 2>$null | Select-String "^neo4j:5-community$"
if (-not $img) {
    Write-Host "✗ 未找到 neo4j:5-community 镜像" -ForegroundColor Red
    Write-Host "  请先执行：docker pull docker.m.daocloud.io/library/neo4j:5-community" -ForegroundColor Yellow
    Write-Host "  再执行：docker tag docker.m.daocloud.io/library/neo4j:5-community neo4j:5-community" -ForegroundColor Yellow
    exit 1
}

# 3) 容器状态：不存在→创建并启动；已停止→启动；运行中→跳过
$exists = docker ps -a --format "{{.Names}}" 2>$null | Select-String "^neo4j$"
$running = docker ps --format "{{.Names}}" 2>$null | Select-String "^neo4j$"

if ($running) {
    Write-Host "✓ Neo4j 容器已在运行" -ForegroundColor Green
} elseif ($exists) {
    Write-Host "启动已有容器 neo4j ..." -ForegroundColor Yellow
    docker start neo4j | Out-Null
    Write-Host "✓ 已启动" -ForegroundColor Green
} else {
    Write-Host "创建并启动 neo4j 容器 ..." -ForegroundColor Yellow
    docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/12345678 neo4j:5-community | Out-Null
    Write-Host "✓ 已创建并启动" -ForegroundColor Green
}

# 4) 等待 bolt 端口就绪
Write-Host "等待 Neo4j 就绪（bolt://localhost:7687）..." -ForegroundColor Yellow
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    $t = Test-NetConnection -ComputerName localhost -Port 7687 -WarningAction SilentlyContinue
    if ($t.TcpTestSucceeded) { $ok = $true; break }
    Start-Sleep 6
}
if ($ok) {
    Write-Host "✓ Neo4j 就绪：Browser http://localhost:7474 | Bolt localhost:7687（neo4j / 12345678）" -ForegroundColor Green
} else {
    Write-Host "✗ Neo4j 端口未就绪，请检查：docker logs neo4j" -ForegroundColor Red
    exit 1
}
