import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import BudgetHead, AccountType
from django.db.models import Q

admin = Department.objects.get(code='ADM')
print(f'Administration department: {admin}')
print(f'Related functions: {admin.related_functions.count()}')

if admin.related_functions.count() > 0:
    print('\nFunctions assigned to Administration:')
    for f in admin.related_functions.all()[:10]:
        print(f'  {f.code} - {f.name}')
    
    # Test the new filter
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
    ).select_related('global_head', 'function')
    
    print(f'\nTotal budget heads with function filter: {budget_heads.count()}')
    print('\nSample:')
    for bh in budget_heads[:5]:
        print(f'  {bh}')
else:
    print('\nNO FUNCTIONS ASSIGNED! This will show 0 budget heads.')
    print('You need to assign functions to departments first.')
