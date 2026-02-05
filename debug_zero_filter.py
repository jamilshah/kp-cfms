"""
Debug why the filter isn't excluding zero-balance FGEN-015101-G01204
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
print("Debugging Zero-Balance Filter")
print("=" * 80)

org = Organization.objects.get(id=2)
as_of_date = date.today()

# Get FGEN-015101-G01204 specifically
bh = BudgetHead.objects.get(id=4640)

print(f"\nBudgetHead: {bh.get_full_code()}")
print(f"Active: {bh.is_active}")

# Annotate it
annotated = BudgetHead.objects.filter(id=4640).select_related(
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
).first()

print(f"\nAnnotated values:")
print(f"  total_debit: {annotated.total_debit} (type: {type(annotated.total_debit)})")
print(f"  total_credit: {annotated.total_credit} (type: {type(annotated.total_credit)})")
print(f"  total_debit == 0: {annotated.total_debit == 0}")
print(f"  total_credit == 0: {annotated.total_credit == 0}")
print(f"  total_debit == Decimal('0.00'): {annotated.total_debit == Decimal('0.00')}")
print(f"  total_credit == Decimal('0.00'): {annotated.total_credit == Decimal('0.00')}")

# Test the filter condition
print(f"\nFilter condition test:")
print(f"  total_debit > 0: {annotated.total_debit > 0}")
print(f"  total_credit > 0: {annotated.total_credit > 0}")
print(f"  Should pass filter (total_debit > 0 OR total_credit > 0): {annotated.total_debit > 0 or annotated.total_credit > 0}")

# Now test with the actual query
print(f"\n{'='*60}")
print("Testing with actual query:")

result = BudgetHead.objects.filter(id=4640).select_related(
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
)

print(f"Query returned {result.count()} results")
if result.exists():
    print(f"[!] BUG: Zero-balance entry passed the filter!")
else:
    print(f"[OK] Zero-balance entry was correctly filtered out")

print("\n" + "=" * 80)
