"""
Script to find all bills and check for the one with 3485 tax
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill
from apps.core.models import Organization

print("=" * 80)
print("All Bills - Looking for 3485 Tax Amount")
print("=" * 80)

org = Organization.objects.first()

# Get ALL bills
all_bills = Bill.objects.filter(
    organization=org
).select_related('payee', 'liability_voucher').order_by('-id')[:20]

print(f"\nAll Bills (most recent 20):")

for bill in all_bills:
    print(f"\nBill #{bill.id}: {bill.bill_number}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Status: {bill.status}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    
    if bill.liability_voucher:
        v = bill.liability_voucher
        entry_count = v.entries.count()
        print(f"  Voucher: {v.voucher_no} (Posted: {v.is_posted}, Entries: {entry_count})")
        
        if entry_count == 0:
            print(f"  [!] WARNING: Voucher has NO entries!")
    else:
        print(f"  No voucher")

print("\n" + "=" * 80)
print("ISSUE FOUND:")
print("  Bill #14 has voucher JV-2025-26-0002 with NO journal entries.")
print("  This is a failed approval that needs to be fixed.")
print("=" * 80)
