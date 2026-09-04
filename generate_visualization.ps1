# generate_visualization.ps1
# Script to generate standalone visualization

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Generate Standalone Visualization" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if conda environment is active
if ($env:CONDA_DEFAULT_ENV -ne "graphragexpr") {
    Write-Host "Error: Please activate the graphragexpr conda environment first:" -ForegroundColor Red
    Write-Host "  conda activate graphragexpr" -ForegroundColor Yellow
    exit 1
}

Write-Host "Generating visualization..." -ForegroundColor Yellow
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
python graphragexpr\vis\visualize_standalone.py

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Visualization generated" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Open graphragexpr\vis\output\graph.html in your browser" -ForegroundColor Green
