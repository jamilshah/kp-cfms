import os
import sys

# Try to set DJANGO_SETTINGS_MODULE appropriately for this project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
try:
    django.setup()
except Exception as e:
    print('Django setup failed:', e)
    sys.exit(1)

from apps.finance.models import GlobalHead, BudgetHead, AccountType

print('GlobalHead counts by account_type:')
for k, label in AccountType.choices:
    try:
        cnt = GlobalHead.objects.filter(account_type=k).count()
    except Exception as e:
        cnt = f'ERROR: {e}'
    print(f'{k}: {cnt}')

print('\nBudgetHead counts (by global_head.account_type):')
for k, label in AccountType.choices:
    try:
        cnt = BudgetHead.objects.filter(global_head__account_type=k).count()
    except Exception as e:
        cnt = f'ERROR: {e}'
    print(f'{k}: {cnt}')
