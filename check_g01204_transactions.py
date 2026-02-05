"""
Check which G01204 BudgetHead has transactions
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead
from apps.core.models import Organization
from django.db.models import Sum
from django.db.models.functions import Coalesce
from decimal import Decimal

print("=" * 80)
print("G01204 BudgetHead Transaction Analysis")
print("=" * 80)

org = Organization.objects.first()
print(f"\nOrganization: {org}")

# Check both BudgetHeads
for bh_id in [4633, 4640]:
    bh = BudgetHead.objects.get(id=bh_id)
    print(f"\n{'='*60}")
    print(f"BudgetHead: {bh.get_full_code()}")
    print(f"  Fund: {bh.fund.code}")
    print(f"  Function: {bh.function.code}")
    print(f"  Active: {bh.is_active}")
    
    # Count entries
    entries = bh.journal_entries.filter(
        voucher__is_posted=True,
        voucher__organization=org
    )
    
    print(f"  Posted Entries: {entries.count()}")
    
    if entries.exists():
        totals = entries.aggregate(
            total_dr=Coalesce(Sum('debit'), Decimal('0.00')),
            total_cr=Coalesce(Sum('credit'), Decimal('0.00'))
        )
        print(f"  Total Debit: {totals['total_dr']}")
        print(f"  Total Credit: {totals['total_cr']}")
        print(f"  Balance: {totals['total_cr'] - totals['total_dr']}")
        
        # Show recent entries
        print(f"\n  Recent Entries:")
        for entry in entries.order_by('-id')[:5]:
            print(f"    {entry.voucher.voucher_no}: Dr {entry.debit}, Cr {entry.credit}")
            print(f"      {entry.description}")

print("\n" + "=" * 80)
