"""
Diagnostic script to check bill creation issues for Dealing Assistant
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department, FiscalYear, BudgetAllocation
from apps.finance.models import FunctionCode, BudgetHead, AccountType
from apps.users.models import CustomUser, Role

print("=" * 80)
print("Diagnostic: Bill Creation - Bill Items Not Showing")
print("=" * 80)

# 1. Check if there are any Dealing Assistants
print("\n[1] USERS WITH DEALING ASSISTANT ROLE")
print("-" * 80)
da_role = Role.objects.filter(code='DEALING_ASSISTANT').first()
if da_role:
    das = CustomUser.objects.filter(roles=da_role)
    print(f"Found {das.count()} Dealing Assistants")
    for da in das[:3]:
        org = getattr(da, 'organization', None)
        print(f"  - {da.email} | Organization: {org} | Department: {da.department}")
else:
    print("No DEALING_ASSISTANT role found")

# 2. Check Departments and their Functions
print("\n[2] DEPARTMENTS AND RELATED FUNCTIONS")
print("-" * 80)
departments = Department.objects.filter(is_active=True)
print(f"Total Active Departments: {departments.count()}")
for dept in departments[:5]:
    funcs = dept.related_functions.filter(is_active=True).count()
    print(f"  - {dept.name}: {funcs} functions")
    if funcs == 0:
        print(f"    WARNING: No functions mapped!")

# 3. Check Budget Heads for Expenditure
print("\n[3] BUDGET HEADS (EXPENDITURE)")
print("-" * 80)
exp_heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True
)
print(f"Total Expenditure Budget Heads: {exp_heads.count()}")
if exp_heads.count() == 0:
    print("WARNING: No expenditure budget heads found!")

# 4. Check Budget Allocations for current fiscal year
print("\n[4] BUDGET ALLOCATIONS (CURRENT FISCAL YEAR)")
print("-" * 80)

# Get a sample organization
sample_org = CustomUser.objects.first()
if sample_org:
    org = getattr(sample_org, 'organization', None)
    if org:
        current_fy = FiscalYear.get_current_operating_year(org)
        if current_fy:
            allocations = BudgetAllocation.objects.filter(
                organization=org,
                fiscal_year=current_fy
            )
            print(f"Org: {org} | Fiscal Year: {current_fy.year_name}")
            print(f"Budget Allocations: {allocations.count()}")
            
            if allocations.count() == 0:
                print("WARNING: No budget allocations found for this organization/fiscal year!")
                print("        This is why bill items are not showing!")
        else:
            print(f"No current operating fiscal year for {org}")
    else:
        print("First user has no organization")
else:
    print("No users found in database")

# 5. Sample Budget Head with Allocation
print("\n[5] SAMPLE BUDGET HEAD WITH ALLOCATION")
print("-" * 80)
sample_allocation = BudgetAllocation.objects.select_related(
    'budget_head', 'organization', 'fiscal_year'
).first()
if sample_allocation:
    bh = sample_allocation.budget_head
    print(f"Budget Head: {bh.code} - {bh.name}")
    print(f"  Department: {bh.department}")
    print(f"  Function: {bh.function}")
    print(f"  Organization: {sample_allocation.organization}")
    print(f"  Fiscal Year: {sample_allocation.fiscal_year.year_name}")
    print(f"  Allocated Amount: Rs. {sample_allocation.allocated_amount:,.2f}")
else:
    print("No budget allocations found in database")

print("\n" + "=" * 80)
print("DIAGNOSIS SUMMARY")
print("=" * 80)
print("""
The 'Bill Items Not Showing' issue usually happens when:

1. NO BUDGET ALLOCATIONS EXIST
   - The system filters to only show bill items with allocations
   - If there are no allocations, no items will appear
   - Fix: Create budget allocations for the current fiscal year

2. DEPARTMENT HAS NO RELATED FUNCTIONS
   - Departments must have functions mapped
   - If no functions, department filter returns nothing
   - Fix: Map functions to departments in admin

3. NO CURRENT OPERATING FISCAL YEAR
   - The system requires an active fiscal year
   - Without it, no allocations are available
   - Fix: Set up a fiscal year as 'current operating'

4. BUDGET HEAD NOT MARKED FOR POSTING
   - Budget heads must have posting_allowed=True
   - Fix: Update budget head settings

5. ORGANIZATION NOT SET ON USER
   - Dealing Assistant must have an organization
   - Fix: Set organization on user profile
""")
print("=" * 80)
