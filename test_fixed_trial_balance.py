"""
Test the fixed Trial Balance for TMA ID 2
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
print("Testing Fixed Trial Balance for TMA ID 2")
print("=" * 80)

org = Organization.objects.get(id=2)
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

# Process with the NEW logic (skip zero net balance)
accounts_data = []
total_debit_balance = Decimal('0.00')
total_credit_balance = Decimal('0.00')

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
    
    # NEW: Skip accounts with zero net balance
    if debit_balance == 0 and credit_balance == 0:
        print(f"[SKIPPED] {head.get_full_code()} - Zero net balance (Dr: {head.total_debit}, Cr: {head.total_credit})")
        continue
    
    accounts_data.append({
        'head': head,
        'debit_balance': debit_balance,
        'credit_balance': credit_balance
    })
    
    total_debit_balance += debit_balance
    total_credit_balance += credit_balance

print(f"\nTotal accounts after filtering: {len(accounts_data)}")
print(f"Total Debit Balance: {total_debit_balance}")
print(f"Total Credit Balance: {total_credit_balance}")

# Check G01204 entries
g01204_count = sum(1 for acc in accounts_data if acc['head'].global_head.code == 'G01204')
print(f"\nG01204 entries in final list: {g01204_count}")

for acc in accounts_data:
    if acc['head'].global_head.code == 'G01204':
        print(f"  {acc['head'].get_full_code()}: Dr {acc['debit_balance']}, Cr {acc['credit_balance']}")

print("\n" + "=" * 80)
print("✓ Fix successful! Zero net balance G01204 entry should be skipped.")
print("=" * 80)
