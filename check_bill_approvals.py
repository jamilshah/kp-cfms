"""
Script to check recent bill approvals and their vouchers
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill, BillStatus
from apps.core.models import Organization

print("=" * 80)
print("Recent Bill Approvals")
print("=" * 80)

org = Organization.objects.first()

# Get all approved bills
approved_bills = Bill.objects.filter(
    organization=org,
    status=BillStatus.APPROVED
).select_related('payee', 'liability_voucher').order_by('-approved_at')[:10]

print(f"\nApproved Bills: {approved_bills.count()}")

for bill in approved_bills:
    print(f"\n{'='*60}")
    print(f"Bill #{bill.id}: {bill.bill_number}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    print(f"  Approved: {bill.approved_at} by {bill.approved_by}")
    
    if bill.liability_voucher:
        v = bill.liability_voucher
        print(f"  Voucher: {v.voucher_no} (Posted: {v.is_posted})")
        print(f"  Voucher Date: {v.date}")
        
        # Show entries
        print(f"  Journal Entries:")
        for entry in v.entries.all().select_related('budget_head'):
            print(f"    {entry.budget_head.get_full_code()}: Dr {entry.debit}, Cr {entry.credit}")
            print(f"      {entry.description}")
        
        # Calculate totals
        from django.db.models import Sum
        totals = v.entries.aggregate(
            total_dr=Sum('debit'),
            total_cr=Sum('credit')
        )
        print(f"  Totals: Dr {totals['total_dr']}, Cr {totals['total_cr']}")
        
        # Check if balanced
        if totals['total_dr'] == totals['total_cr']:
            print(f"  ✓ Voucher is balanced")
        else:
            print(f"  ✗ VOUCHER IS UNBALANCED!")
    else:
        print(f"  [!] NO LIABILITY VOUCHER!")

# Also check for bills in VERIFIED status (awaiting approval)
print(f"\n\n{'='*80}")
print("Bills Awaiting Approval (VERIFIED status):")
print("="*80)

verified_bills = Bill.objects.filter(
    organization=org,
    status=BillStatus.VERIFIED
).select_related('payee').order_by('-verified_at')[:5]

for bill in verified_bills:
    print(f"\nBill #{bill.id}: {bill.bill_number}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    print(f"  Verified: {bill.verified_at}")

print("\n" + "=" * 80)
