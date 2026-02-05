"""
Script to check and fix Bill #20
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill, BillStatus
from apps.finance.models import Voucher
from django.db import transaction

print("=" * 80)
print("Checking and Fixing Bill #20")
print("=" * 80)

try:
    bill = Bill.objects.get(id=20)
    print(f"\nFound Bill #20: {bill.bill_number}")
    print(f"  Current Status: {bill.status}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    print(f"  Approved: {bill.approved_at}")
    
    if not bill.liability_voucher:
        print("\n[!] Bill has no liability voucher.")
        if bill.status == BillStatus.APPROVED:
            print("[!] WARNING: Bill is APPROVED but has no voucher - this is corrupted!")
    else:
        voucher = bill.liability_voucher
        entry_count = voucher.entries.count()
        print(f"\n  Liability Voucher: {voucher.voucher_no}")
        print(f"  Posted: {voucher.is_posted}")
        print(f"  Journal Entries: {entry_count}")
        
        if entry_count > 0:
            print(f"\n  Journal Entries:")
            for entry in voucher.entries.all():
                print(f"    {entry.budget_head.get_full_code()}: Dr {entry.debit}, Cr {entry.credit}")
                print(f"      {entry.description}")
        
        if entry_count == 0:
            print(f"\n[!] Voucher has NO entries - fixing now...")
            
            with transaction.atomic():
                voucher_no = voucher.voucher_no
                
                # Delete the empty voucher
                voucher.delete()
                print(f"  ✓ Deleted empty voucher {voucher_no}")
                
                # Reset bill status
                bill.status = BillStatus.VERIFIED
                bill.approved_at = None
                bill.approved_by = None
                bill.liability_voucher = None
                bill.save(update_fields=['status', 'approved_at', 'approved_by', 'liability_voucher', 'updated_at'])
                
                print(f"  ✓ Reset Bill #20 to VERIFIED status")
                print(f"\n{'='*80}")
                print("SUCCESS!")
                print("  Bill #20 has been reset to VERIFIED status.")
                print("  You can now re-approve it to create proper journal entries.")
                print("=" * 80)
        else:
            print(f"\n[OK] Voucher has {entry_count} entries - looks good!")
            
except Bill.DoesNotExist:
    print("\n[ERROR] Bill #20 not found!")
    print("\nLet me list all bills to find it:")
    
    from apps.core.models import Organization
    org = Organization.objects.first()
    
    all_bills = Bill.objects.filter(organization=org).order_by('-id')[:10]
    print(f"\nMost recent bills:")
    for b in all_bills:
        print(f"  Bill #{b.id}: {b.bill_number} - Status: {b.status}, Tax: {b.tax_amount}")
        
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
