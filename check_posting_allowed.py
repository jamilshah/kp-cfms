"""
Check if budget heads have posting_allowed=True
"""
from apps.finance.models import BudgetHead, AccountType

# Check total budget heads
total_heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    is_active=True
).exclude(
    global_head__code__startswith='A01'
).count()

# Check with posting_allowed
posting_allowed_heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True
).exclude(
    global_head__code__startswith='A01'
).count()

print(f"Total active expenditure heads (excluding A01*): {total_heads}")
print(f"With posting_allowed=True: {posting_allowed_heads}")

# Show sample of heads without posting_allowed
without_posting = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=False,
    is_active=True
).exclude(
    global_head__code__startswith='A01'
)[:5]

print(f"\nSample heads with posting_allowed=False:")
for head in without_posting:
    print(f"  {head.code} - {head.name}")

# Check a specific function
from apps.budgeting.models import Department
dept = Department.objects.first()
if dept:
    print(f"\nDepartment: {dept.name}")
    func = dept.related_functions.first()
    if func:
        print(f"Function: {func.code} - {func.name}")
        
        heads_for_function = BudgetHead.objects.filter(
            global_head__account_type=AccountType.EXPENDITURE,
            posting_allowed=True,
            is_active=True,
            function=func
        ).exclude(
            global_head__code__startswith='A01'
        ).count()
        
        print(f"Budget heads for this function with posting_allowed=True: {heads_for_function}")
