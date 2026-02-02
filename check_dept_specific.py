import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import BudgetHead, AccountType, GlobalHead
from django.db.models import Q

admin = Department.objects.get(code='ADM')

# Check department-specific GlobalHeads
print('Department-specific GlobalHeads for Administration:')
dept_heads = GlobalHead.objects.filter(
    scope='DEPARTMENTAL',
    applicable_departments=admin
)
print(f'Total: {dept_heads.count()}')
for gh in dept_heads[:10]:
    print(f'  {gh.code} - {gh.name}')

# Check what we're currently showing
print('\n\nCurrent filter (with A01 exclusion):')
budget_heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True
).exclude(
    global_head__code__startswith='A01'
).filter(
    Q(global_head__scope='UNIVERSAL') |
    Q(global_head__applicable_departments=admin)
).filter(
    function__in=admin.related_functions.all()
)
print(f'Budget heads shown: {budget_heads.count()}')

# Check how many department-specific heads we're excluding
excluded = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True,
    global_head__code__startswith='A01',
    global_head__scope='DEPARTMENTAL',
    global_head__applicable_departments=admin
).filter(
    function__in=admin.related_functions.all()
)
print(f'\nDepartmental A01* heads excluded: {excluded.count()}')
if excluded.exists():
    print('Sample:')
    for bh in excluded[:5]:
        print(f'  {bh}')

# Check universal vs departmental breakdown
universal = budget_heads.filter(global_head__scope='UNIVERSAL').count()
departmental = budget_heads.filter(global_head__scope='DEPARTMENTAL').count()
print(f'\nBreakdown of shown heads:')
print(f'  Universal: {universal}')
print(f'  Departmental: {departmental}')
