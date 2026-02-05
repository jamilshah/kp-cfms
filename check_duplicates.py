"""
Script to check for duplicate GlobalHead codes in Trial Balance data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead
from apps.core.models import Organization
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date

print("=" * 80)
print("Checking for Duplicate GlobalHead Codes")
print("=" * 80)

org = Organization.objects.first()
as_of_date = date.today()

# Run the exact query from Trial Balance view
budget_heads = BudgetHead.objects.select_related(
    'global_head', 'fund', 'function'
).annotate(
    total_debit=Coalesce(
        Sum('journal_entries__debit',
            filter=Q(journal_entries__voucher__is_posted=True,
                    journal_entries__voucher__organization=org,
                    journal_entries__voucher__date__lte=as_of_date)),
        Decimal('0.00')
    ),
    total_credit=Coalesce(
        Sum('journal_entries__credit',
            filter=Q(journal_entries__voucher__is_posted=True,
                    journal_entries__voucher__organization=org,
                    journal_entries__voucher__date__lte=as_of_date)),
        Decimal('0.00')
    )
).filter(
    Q(total_debit__gt=0) | Q(total_credit__gt=0)
).exclude(
    Q(is_active=False) & Q(total_debit=0) & Q(total_credit=0)
).order_by('fund', 'function__code', 'global_head__code')

# Process like the view does
accounts_data = []
for head in budget_heads:
    if head.global_head.account_type in ['AST', 'EXP']:
        balance = head.total_debit - head.total_credit
        if balance > 0:
            debit_balance = balance
            credit_balance = Decimal('0.00')
        else:
            debit_balance = Decimal('0.00')
            credit_balance = abs(balance)
    else:
        balance = head.total_credit - head.total_debit
        if balance > 0:
            credit_balance = balance
            debit_balance = Decimal('0.00')
        else:
            credit_balance = Decimal('0.00')
            debit_balance = abs(balance)
    
    accounts_data.append({
        'head': head,
        'debit_balance': debit_balance,
        'credit_balance': credit_balance
    })

print(f"\nTotal accounts: {len(accounts_data)}")

# Group by GlobalHead code
from collections import defaultdict
by_code = defaultdict(list)

for account in accounts_data:
    code = account['head'].global_head.code
    by_code[code].append(account)

# Find duplicates
print(f"\nGlobalHead codes with multiple BudgetHeads:")
for code, accounts in by_code.items():
    if len(accounts) > 1:
        print(f"\n{code}: {len(accounts)} entries")
        for acc in accounts:
            print(f"  - {acc['head'].get_full_code()}: Dr {acc['debit_balance']}, Cr {acc['credit_balance']}")

print("\n" + "=" * 80)
