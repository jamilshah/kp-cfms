import os
import django
import sys
from decimal import Decimal

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import BankAccount
from apps.finance.models import BudgetHead

print('--- ASSET GL CODES (CASH AT BANK) ---')
# A01 is typical for Assets/Cash in PIFRA
heads = BudgetHead.objects.filter(
    global_head__code__startswith='A0',
    posting_allowed=True
).select_related('global_head')

for h in heads:
    print(f'Code: {h.code} | Name: {h.name}')
