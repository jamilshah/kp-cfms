# Import CoA for All Departments
# This script imports the Chart of Accounts for all active departments

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BULK COA IMPORT FOR ALL DEPARTMENTS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

$fund = "GEN"
$coaFile = "docs/tma_coa.csv"

Write-Host "`nConfiguration:" -ForegroundColor Yellow
Write-Host "  CoA File: $coaFile"
Write-Host "  Fund: $fund"

Write-Host "`n" + ("-" * 80)

# Get list of departments using Python
$deptQuery = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.budgeting.models import Department
for dept in Department.objects.filter(is_active=True):
    print(f'{dept.id}|{dept.name}|{dept.related_functions.count()}')
"@

$departments = python -c $deptQuery

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Could not fetch departments" -ForegroundColor Red
    exit 1
}

Write-Host "Departments to import:"
$deptCount = 0
foreach ($line in $departments) {
    $parts = $line -split '\|'
    if ($parts.Length -eq 3) {
        $deptCount++
        Write-Host "  $($parts[1]) - $($parts[2]) functions"
    }
}

Write-Host "`nTotal: $deptCount departments" -ForegroundColor Green

# Confirm
$confirm = Read-Host "`nProceed with import? (yes/no)"
if ($confirm -ne "yes" -and $confirm -ne "y") {
    Write-Host "Import cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n" + ("=" * 80) -ForegroundColor Cyan
Write-Host "STARTING IMPORT..." -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan

$successCount = 0
$errorCount = 0

foreach ($line in $departments) {
    $parts = $line -split '\|'
    if ($parts.Length -eq 3) {
        $deptId = $parts[0]
        $deptName = $parts[1]
        $funcCount = $parts[2]
        
        Write-Host "`n" + ("=" * 80) -ForegroundColor Yellow
        Write-Host "DEPARTMENT: $deptName (ID: $deptId)" -ForegroundColor Yellow
        Write-Host "Functions: $funcCount" -ForegroundColor Yellow
        Write-Host ("=" * 80) -ForegroundColor Yellow
        
        # Run import command
        python manage.py import_coa --file=$coaFile --fund=$fund --department_id=$deptId
        
        if ($LASTEXITCODE -eq 0) {
            $successCount++
            Write-Host "`n✓ Successfully imported for $deptName" -ForegroundColor Green
        } else {
            $errorCount++
            Write-Host "`n✗ Error importing for $deptName" -ForegroundColor Red
        }
    }
}

# Summary
Write-Host "`n" + ("=" * 80) -ForegroundColor Cyan
Write-Host "IMPORT SUMMARY" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "Departments processed: $deptCount"
Write-Host "Successful: $successCount" -ForegroundColor Green
Write-Host "Errors: $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })
Write-Host ("=" * 80) -ForegroundColor Cyan

if ($errorCount -eq 0) {
    Write-Host "`n✓ All imports completed successfully!" -ForegroundColor Green
} else {
    Write-Host "`n⚠️  $errorCount department(s) had errors. Check logs above." -ForegroundColor Yellow
}
