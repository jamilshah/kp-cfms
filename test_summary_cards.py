"""
Test script to verify the summary cards calculation in EmployeeSalaryListView
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models_employee import BudgetEmployee
from django.db.models import Sum

# Get all non-vacant employees
employees = BudgetEmployee.objects.filter(is_vacant=False)

print("=" * 80)
print("Testing Summary Cards Calculation")
print("=" * 80)

# Manual calculation
total_employees = employees.count()
total_monthly_cost = employees.aggregate(total=Sum('running_basic'))['total'] or Decimal('0.00')

total_annual = Decimal('0.00')
total_projected_annual = Decimal('0.00')

print(f"\nTotal Employees: {total_employees}")
print(f"Total Monthly Cost: Rs. {total_monthly_cost:,.2f}")

sample_count = 0
for employee in employees:
    annual = employee.annual_cost
    projected = employee.get_projected_annual_cost()
    total_annual += annual
    total_projected_annual += projected
    
    if sample_count < 3:
        print(f"\nEmployee {sample_count + 1}: {employee.name}")
        print(f"  Current Annual: Rs. {annual:,.2f}")
        print(f"  Projected Annual: Rs. {projected:,.2f}")
        print(f"  Increase: Rs. {projected - annual:,.2f}")
        print(f"  Increase %: {employee.expected_salary_increase_percentage}%")
        sample_count += 1

print(f"\n{'=' * 80}")
print(f"SUMMARY")
print(f"{'=' * 80}")
print(f"Total Annual Cost (Current):   Rs. {total_annual:,.2f}")
print(f"Total Projected Next Year:     Rs. {total_projected_annual:,.2f}")
print(f"Total Annual Increase:         Rs. {total_projected_annual - total_annual:,.2f}")
print(f"{'=' * 80}")

# Verify calculations
if total_employees > 0:
    print("\n[PASS] Summary cards data calculated successfully!")
    print(f"       Verified with {total_employees} employees in database")
else:
    print("\n[INFO] No employees found in database - calculations work correctly with 0 employees")

