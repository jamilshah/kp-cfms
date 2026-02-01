#!/usr/bin/env python
"""
Analyze the BudgetHead import results - explain the 2816 total.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, FunctionCode
from apps.budgeting.models import Department

def main():
    print("=" * 80)
    print("BUDGETHEAD IMPORT ANALYSIS - EXPLAINING THE 2816 TOTAL")
    print("=" * 80)
    
    total = BudgetHead.objects.count()
    regular = BudgetHead.objects.filter(head_type='REGULAR').count()
    subheads = BudgetHead.objects.filter(head_type='SUB_HEAD').count()
    
    print(f"\n📊 OVERALL TOTALS:")
    print(f"   Total BudgetHeads: {total}")
    print(f"   - Regular Heads: {regular}")
    print(f"   - Sub-Heads: {subheads}")
    
    print("\n" + "=" * 80)
    print("📋 BREAKDOWN BY DEPARTMENT")
    print("=" * 80)
    
    grand_total = 0
    dept_count = 0
    
    departments = Department.objects.prefetch_related('related_functions').filter(is_active=True)
    
    for dept in departments:
        functions = dept.related_functions.all()
        if functions.count() == 0:
            continue
        
        dept_count += 1
        dept_total = 0
        
        print(f"\n{dept_count}. {dept.name}")
        print(f"   {'─' * 70}")
        
        for func in functions:
            func_total = BudgetHead.objects.filter(function=func).count()
            func_regular = BudgetHead.objects.filter(function=func, head_type='REGULAR').count()
            func_subheads = BudgetHead.objects.filter(function=func, head_type='SUB_HEAD').count()
            
            if func_total > 0:
                print(f"   {func.code} - {func.name[:45]}")
                print(f"      Regular: {func_regular:3d} + Sub-heads: {func_subheads:2d} = Total: {func_total:3d}")
                dept_total += func_total
        
        print(f"   {'─' * 70}")
        print(f"   Department Total: {dept_total} BudgetHeads")
        grand_total += dept_total
    
    print("\n" + "=" * 80)
    print("💡 THE MATH BEHIND 2816")
    print("=" * 80)
    
    print("\nEach Function gets the complete Chart of Accounts:")
    print("  • 108 Regular Heads (A01101, A01102, ... C03849)")
    print("  • 20 Sub-Heads (C03880-10, C03880-16, ... C03849-01)")
    print("  • Total per function = 128 BudgetHeads")
    
    print("\nYou have 22 Functions across all departments:")
    
    functions_with_heads = FunctionCode.objects.filter(budget_heads__isnull=False).distinct().order_by('code')
    for i, func in enumerate(functions_with_heads, 1):
        count = BudgetHead.objects.filter(function=func).count()
        print(f"  {i:2d}. {func.code} = {count} heads")
    
    print("\n" + "─" * 80)
    print(f"Formula: 22 functions × 128 heads/function = {22 * 128}")
    print(f"Result:  {total} BudgetHeads ✓")
    
    print("\n" + "=" * 80)
    print("🔍 WHY THIS DESIGN?")
    print("=" * 80)
    
    print("""
Each function needs its own BudgetHeads because:

1. INDEPENDENT BUDGETS
   • Each function has separate budget allocation
   • Example: Admin electricity ≠ Water Supply electricity
   • Prevents budget conflicts between departments

2. COST ALLOCATION
   • Track expenses by function (mandatory for NAM reporting)
   • Example: How much does "Fire Protection" cost vs "Water Supply"?

3. BUDGET CONTROL
   • Each function head enforces its own spending limits
   • Example: Roads can't overspend even if Water has surplus

4. REPORTING
   • Function-wise expenditure analysis
   • Aggregate by department or across all functions
   • Compare actual vs budget by function

ANALOGY: Like having separate bank accounts for each department.
Same chart of accounts (same account types), but separate balances.
""")
    
    print("=" * 80)
    print("✅ VERIFICATION")
    print("=" * 80)
    
    print(f"\nExpected: 22 functions × 128 heads = 2,816")
    print(f"Actual:   {total} BudgetHeads")
    print(f"Status:   {'✓ CORRECT' if total == 2816 else '✗ MISMATCH'}")
    
    if total == 2816:
        print("\nThe import completed successfully!")
        print("All functions now have their complete Chart of Accounts.")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
