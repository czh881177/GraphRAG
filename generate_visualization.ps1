# generate_visualization.ps1
# Script to generate standalone visualization

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Generate Standalone Visualization" -ForegroundColor Cyan
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

Write-Host "Generating visualization..." -ForegroundColor Yellow
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
& $py graphragexpr\vis\visualize_standalone.py

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Visualization generated" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Open graphragexpr\vis\output\graph.html in your browser" -ForegroundColor Green
