import os
import django
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import BankAccount
from apps.finance.models import BudgetHead

accounts = BankAccount.objects.all()
print('--- BANK ACCOUNTS ---')
for a in accounts:
    print(f'Account: {a.title} | GL Code: {a.gl_code.code} - {a.gl_code.name}')
