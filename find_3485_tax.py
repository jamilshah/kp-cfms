"""
Script to find the missing 3485 tax entry
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import JournalEntry, Voucher
from apps.expenditure.models import Bill
from apps.core.models import Organization
from decimal import Decimal

print("=" * 80)
print("Finding the 3485 Tax Entry")
print("=" * 80)

org = Organization.objects.first()

# Find bills with tax_amount = 3485
print("\n[1] Bills with tax_amount = 3485:")
bills_3485 = Bill.objects.filter(
    organization=org,
    tax_amount=Decimal('3485.00')
).order_by('-id')

for bill in bills_3485:
    print(f"\n  Bill #{bill.id}: {bill.bill_number}")
    print(f"    Payee: {bill.payee.name}")
    print(f"    Status: {bill.status}")
    print(f"    Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    print(f"    Approved: {bill.approved_at}")
    
    if bill.liability_voucher:
        print(f"    Liability Voucher: {bill.liability_voucher.voucher_no} (Posted: {bill.liability_voucher.is_posted})")
        
        # Show all journal entries for this voucher
        print(f"    Journal Entries:")
        for entry in bill.liability_voucher.entries.all():
            print(f"      {entry.budget_head.get_full_code()}: Dr {entry.debit}, Cr {entry.credit}")
            print(f"        Description: {entry.description}")
    else:
        print(f"    [!] No liability voucher linked!")

# Find journal entries with credit = 3485
print("\n[2] Journal Entries with Credit = 3485:")
entries_3485 = JournalEntry.objects.filter(
    voucher__organization=org,
    credit=Decimal('3485.00')
).select_related('voucher', 'budget_head').order_by('-id')[:5]

for entry in entries_3485:
    print(f"\n  Entry ID {entry.id}:")
    print(f"    Voucher: {entry.voucher.voucher_no} (Posted: {entry.voucher.is_posted})")
    print(f"    BudgetHead: {entry.budget_head.get_full_code()}")
    print(f"    Amount: Dr {entry.debit}, Cr {entry.credit}")
    print(f"    Description: {entry.description}")

# Check all recent vouchers
print("\n[3] Most Recent Vouchers:")
recent_vouchers = Voucher.objects.filter(
    organization=org
).order_by('-id')[:5]

for v in recent_vouchers:
    print(f"\n  {v.voucher_no} (Posted: {v.is_posted}):")
    print(f"    Date: {v.date}, Description: {v.description[:60]}")
    
    # Calculate totals
    from django.db.models import Sum
    totals = v.entries.aggregate(
        total_dr=Sum('debit'),
        total_cr=Sum('credit')
    )
    print(f"    Totals: Dr {totals['total_dr']}, Cr {totals['total_cr']}")
    
    # Show entries
    for entry in v.entries.all():
        print(f"      {entry.budget_head.get_full_code()}: Dr {entry.debit}, Cr {entry.credit}")

print("\n" + "=" * 80)
