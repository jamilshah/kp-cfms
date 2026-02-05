"""
Test the exact Trial Balance query to see what it returns
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
print("Testing Trial Balance Query")
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

print(f"\nTotal BudgetHeads returned: {budget_heads.count()}")

# Check for G01204 entries
print(f"\nChecking G01204 entries:")
for bh in budget_heads:
    if bh.global_head.code == 'G01204':
        print(f"\n  {bh.get_full_code()}")
        print(f"    Active: {bh.is_active}")
        print(f"    total_debit: {bh.total_debit} (type: {type(bh.total_debit)})")
        print(f"    total_credit: {bh.total_credit} (type: {type(bh.total_credit)})")
        print(f"    Passes filter? {bh.total_debit > 0 or bh.total_credit > 0}")

print("\n" + "=" * 80)
