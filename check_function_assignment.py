#!/usr/bin/env python
"""
Script to check and manage BudgetHead function assignments.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, FunctionCode
from apps.budgeting.models import Department

def main():
    print("=" * 80)
    print("BUDGETHEAD FUNCTION ASSIGNMENT ANALYSIS")
    print("=" * 80)
    
    # 1. Show current BudgetHeads by function
    print("\n1. CURRENT BUDGETHEADS BY FUNCTION:")
    print("-" * 80)
    functions_with_heads = FunctionCode.objects.filter(budget_heads__isnull=False).distinct()
    for func in functions_with_heads:
        count = BudgetHead.objects.filter(function=func).count()
        subhead_count = BudgetHead.objects.filter(function=func, head_type='SUB_HEAD').count()
        print(f"  {func.code} - {func.name[:50]}")
        print(f"    Total Heads: {count} (Regular: {count - subhead_count}, Sub-heads: {subhead_count})")
    
    # 2. Show departments and their functions
    print("\n2. DEPARTMENTS AND THEIR FUNCTIONS:")
    print("-" * 80)
    departments = Department.objects.prefetch_related('related_functions').all()
    for dept in departments[:10]:
        funcs = dept.related_functions.all()
        print(f"  {dept.name}")
        for func in funcs[:3]:
            print(f"    - {func.code}: {func.name[:60]}")
        if funcs.count() > 3:
            print(f"    ... and {funcs.count() - 3} more functions")
    
    # 3. Show import options
    print("\n3. HOW TO IMPORT FOR DIFFERENT DEPARTMENTS/FUNCTIONS:")
    print("-" * 80)
    print("\nOPTION A: Import for a specific function")
    print("  python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --function=<FUNC_CODE>")
    print("\n  Example:")
    if FunctionCode.objects.exists():
        other_func = FunctionCode.objects.exclude(code='011103').first()
        if other_func:
            print(f"    python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --function={other_func.code}")
    
    print("\nOPTION B: Import for all functions in a department")
    print("  python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --department_id=<DEPT_ID>")
    print("\n  Example:")
    if Department.objects.exists():
        dept = Department.objects.first()
        print(f"    python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --department_id={dept.id}")
        print(f"    # This will import for {dept.related_functions.count()} functions in '{dept.name}'")
    
    print("\nOPTION C: Import for multiple departments (run command multiple times)")
    print("  for dept_id in 1 2 3; do")
    print("    python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --department_id=$dept_id")
    print("  done")
    
    # 4. Explain the design
    print("\n4. WHY BUDGETHEADS ARE FUNCTION-SPECIFIC:")
    print("-" * 80)
    print("  • Each BudgetHead represents: Fund + Function + Object + Sub-Code")
    print("  • Functions allow proper cost allocation across departments")
    print("  • Same object code (e.g., A03303-Electricity) can have different budgets")
    print("    for different functions (Admin vs Water Supply vs Sanitation)")
    print("  • This enables:")
    print("    - Functional cost analysis")
    print("    - Department-wise budget tracking")
    print("    - Multi-dimensional reporting")
    
    # 5. Show what happens when you import again
    print("\n5. IMPORTING FOR ADDITIONAL FUNCTIONS:")
    print("-" * 80)
    print("  When you import with a different function code:")
    print("  • Creates NEW BudgetHeads for that function")
    print("  • Does NOT modify existing BudgetHeads")
    print("  • Each function gets its own complete Chart of Accounts")
    print("  • Sub-heads are created for each function independently")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    print("Import the CoA for each department/function that will use the system.")
    print("Each department needs its own BudgetHeads to track budgets separately.")
    print("\nTo import for all departments at once, create a shell script:")
    print("  import_all_departments.sh")
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
