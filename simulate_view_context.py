"""
Final diagnostic: Print exactly what the view is passing to the template
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
print("Simulating Trial Balance View Context")
print("=" * 80)

org = Organization.objects.first()
as_of_date = date.today()

# Exact query from the view
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
).order_by('fund', 'function__code', 'global_head__code')

# Process like the view does
accounts_data = []
total_debit_balance = Decimal('0.00')
total_credit_balance = Decimal('0.00')

for head in budget_heads:
    # Calculate net balance based on account type
    if head.global_head.account_type in ['AST', 'EXP']:
        # Debit balance accounts
        balance = head.total_debit - head.total_credit
        if balance > 0:
            debit_balance = balance
            credit_balance = Decimal('0.00')
        else:
            debit_balance = Decimal('0.00')
            credit_balance = abs(balance)
    else:  # LIABILITY, EQUITY, REVENUE
        # Credit balance accounts
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
    
    total_debit_balance += debit_balance
    total_credit_balance += credit_balance

print(f"\nTotal accounts in context: {len(accounts_data)}")
print(f"Total Debit Balance: {total_debit_balance}")
print(f"Total Credit Balance: {total_credit_balance}")
print(f"Balanced: {total_debit_balance == total_credit_balance}")

print(f"\nAll accounts that would be rendered:")
for i, account in enumerate(accounts_data, 1):
    code = account['head'].global_head.code
    name = account['head'].global_head.name
    print(f"{i}. {code} - {name}")
    print(f"   Dr: {account['debit_balance']}, Cr: {account['credit_balance']}")

print("\n" + "=" * 80)
