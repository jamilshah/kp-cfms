"""
Script to diagnose Trial Balance query results
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
print("Trial Balance Query Diagnostic")
print("=" * 80)

org = Organization.objects.first()
as_of_date = date.today()

print(f"\nOrganization: {org}")
print(f"As of Date: {as_of_date}")

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
    # Exclude inactive accounts with zero balance
    Q(is_active=False) & Q(total_debit=0) & Q(total_credit=0)
).order_by('fund', 'function__code', 'global_head__code')

print(f"\nTotal BudgetHeads returned: {budget_heads.count()}")

# Check specifically for G01204 entries
g01204_heads = [h for h in budget_heads if h.global_head.code == 'G01204']

print(f"\nG01204 BudgetHeads in results: {len(g01204_heads)}")

for head in g01204_heads:
    print(f"\n  {head.get_full_code()}")
    print(f"    Active: {head.is_active}")
    print(f"    Total Debit: {head.total_debit}")
    print(f"    Total Credit: {head.total_credit}")
    print(f"    Balance: {head.total_credit - head.total_debit}")

# Check if the inactive one exists in database
print(f"\n{'='*80}")
print("Checking FGEN-015101-G01204 directly:")
try:
    inactive_head = BudgetHead.objects.get(id=4640)
    print(f"  Found: {inactive_head.get_full_code()}")
    print(f"  Active: {inactive_head.is_active}")
    
    # Check if it has any entries
    entry_count = inactive_head.journal_entries.filter(
        voucher__is_posted=True,
        voucher__organization=org
    ).count()
    print(f"  Posted Entries: {entry_count}")
    
except BudgetHead.DoesNotExist:
    print("  Not found!")

print("\n" + "=" * 80)
