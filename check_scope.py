import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, AccountType, GlobalHead
from apps.budgeting.models import Department
from django.db.models import Q

admin = Department.objects.get(id=1)

heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True
).exclude(
    global_head__code__startswith='A01'
).select_related('global_head', 'function').filter(
    Q(global_head__scope='UNIVERSAL') | 
    Q(global_head__applicable_departments=admin)
)

print(f'Total heads for Administration: {heads.count()}')

universal = heads.filter(global_head__scope='UNIVERSAL').count()
dept_specific = heads.filter(global_head__applicable_departments=admin).count()

print(f'Universal: {universal}')
print(f'Dept-specific: {dept_specific}')

print('\nScope distribution in GlobalHeads:')
print(f'  UNIVERSAL: {GlobalHead.objects.filter(scope="UNIVERSAL").count()}')
print(f'  DEPARTMENTAL: {GlobalHead.objects.filter(scope="DEPARTMENTAL").count()}')

print('\nSample DEPARTMENTAL heads assigned to Administration:')
dept_heads = GlobalHead.objects.filter(scope='DEPARTMENTAL', applicable_departments=admin)[:5]
for gh in dept_heads:
    print(f'  {gh.code} - {gh.name}')

print('\nChecking if we see heads from other departments:')
# Check if there are heads with Infrastructure or other departments
infra = Department.objects.filter(code='IS').first()
if infra:
    infra_only = GlobalHead.objects.filter(scope='DEPARTMENTAL', applicable_departments=infra).exclude(applicable_departments=admin)
    print(f'Infrastructure-only GlobalHeads: {infra_only.count()}')
    if infra_only.exists():
        print('Sample:')
        for gh in infra_only[:3]:
            print(f'  {gh.code} - {gh.name}')
            # Check if this appears in our filtered list
            matching = heads.filter(global_head=gh)
            print(f'    Appears in Administration filter: {matching.exists()} ({matching.count()} BudgetHeads)')
