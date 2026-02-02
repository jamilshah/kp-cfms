"""
Debug script to check Department-Function mapping and budget head filtering
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import BudgetHead, FunctionCode, AccountType
from apps.core.models import Organization
from apps.budgeting.models import BudgetAllocation, FiscalYear
from django.db.models import Exists, OuterRef

print("=" * 80)
print("Department-Function Mapping & Budget Head Filtering Diagnostics")
print("=" * 80)

# 1. Check Department-Function mappings
print("\n[1] DEPARTMENT-FUNCTION MAPPINGS")
print("-" * 80)
departments = Department.objects.filter(is_active=True)
for dept in departments[:10]:
    funcs = dept.related_functions.filter(is_active=True)
    print(f"\n{dept.name} (ID: {dept.id})")
    if funcs.count() == 0:
        print("  ⚠️  NO FUNCTIONS MAPPED! This is why filtering doesn't work.")
    else:
        print(f"  Functions ({funcs.count()}):")
        for func in funcs[:5]:
            print(f"    - {func.code}: {func.name}")
        if funcs.count() > 5:
            print(f"    ... and {funcs.count() - 5} more")

# 2. Check C03880 and its sub-heads
print("\n[2] C03880 AND SUB-HEADS")
print("-" * 80)
c03880 = BudgetHead.objects.filter(global_head__code='C03880').first()
if c03880:
    print(f"Parent: {c03880.code} - {c03880.name}")
    print(f"  posting_allowed: {c03880.posting_allowed}")
    print(f"  is_active: {c03880.is_active}")
    print(f"  Function: {c03880.function}")
    
    # Find sub-heads
    subheads = BudgetHead.objects.filter(
        global_head__code__startswith='C03880',
        posting_allowed=True,
        is_active=True
    ).exclude(global_head__code='C03880')
    
    print(f"\nSub-heads (posting_allowed=True, is_active=True): {subheads.count()}")
    for sh in subheads:
        print(f"  - {sh.code}: {sh.name} | Function: {sh.function}")
        
    # Check if they have allocations
    org = Organization.objects.first()
    if org:
        fy = FiscalYear.get_current_operating_year(org)
        if fy:
            print(f"\nSub-heads with allocations in FY {fy.year_name}:")
            for sh in subheads:
                has_alloc = BudgetAllocation.objects.filter(
                    organization=org,
                    fiscal_year=fy,
                    budget_head=sh
                ).exists()
                status = "✓ Has allocation" if has_alloc else "✗ No allocation"
                print(f"  - {sh.code}: {status}")
else:
    print("C03880 not found in database")

# 3. Simulate the filtering logic
print("\n[3] SIMULATING BILL ITEM FILTERING")
print("-" * 80)

# Pick a sample department
sample_dept = departments.first()
if sample_dept and sample_dept.related_functions.exists():
    sample_func = sample_dept.related_functions.first()
    
    print(f"Selected Department: {sample_dept.name} (ID: {sample_dept.id})")
    print(f"Selected Function: {sample_func.code} - {sample_func.name} (ID: {sample_func.id})")
    
    # Simulate what the view does
    budget_heads = BudgetHead.objects.filter(
        posting_allowed=True,
        is_active=True,
        global_head__account_type=AccountType.EXPENDITURE
    ).select_related('global_head', 'function')
    
    print(f"\nBefore filtering: {budget_heads.count()} budget heads")
    
    # Filter by allocation
    org = Organization.objects.first()
    fy = FiscalYear.get_current_operating_year(org)
    if fy:
        has_allocation = BudgetAllocation.objects.filter(
            organization=org,
            fiscal_year=fy,
            budget_head=OuterRef('pk')
        )
        budget_heads = budget_heads.annotate(
            has_allocation=Exists(has_allocation)
        ).filter(has_allocation=True)
        
        print(f"After allocation filter: {budget_heads.count()} budget heads")
    
    # Filter by function
    budget_heads_by_func = budget_heads.filter(function_id=sample_func.id)
    print(f"After function filter: {budget_heads_by_func.count()} budget heads")
    
    # Filter by department (function list)
    dept_functions = sample_dept.related_functions.all()
    budget_heads_by_dept = budget_heads.filter(function__in=dept_functions)
    print(f"After department filter: {budget_heads_by_dept.count()} budget heads")
    
    # Show sample
    print(f"\nSample budget heads for this department/function:")
    for bh in budget_heads_by_func[:5]:
        print(f"  - {bh.code}: {bh.name}")
else:
    print("No department with functions found")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print("""
Issue 1: All budget heads showing (not filtered)
  → Cause: Department has NO related_functions mapped
  → Fix: Map functions to departments in Django admin
  
Issue 2: C03880 sub-heads not showing
  → Possible causes:
    a) Sub-heads have posting_allowed=False
    b) Sub-heads have is_active=False
    c) Sub-heads have no budget allocations
    d) Sub-heads not assigned to the selected function
  → Fix: Check sub-head settings and allocations above
""")
print("=" * 80)
