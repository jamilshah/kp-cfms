"""
Script to fix Bill #14 - Auto-fix version (no prompts)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill, BillStatus
from apps.finance.models import Voucher
from django.db import transaction

print("=" * 80)
print("Fixing Bill #14 - Auto-Fix Mode")
print("=" * 80)

try:
    bill = Bill.objects.get(id=14)
    print(f"\nFound Bill #14: {bill.bill_number}")
    print(f"  Current Status: {bill.status}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    
    if not bill.liability_voucher:
        print("\n[!] Bill has no liability voucher - nothing to fix.")
    else:
        voucher = bill.liability_voucher
        entry_count = voucher.entries.count()
        print(f"\n  Liability Voucher: {voucher.voucher_no}")
        print(f"  Posted: {voucher.is_posted}")
        print(f"  Journal Entries: {entry_count}")
        
        if entry_count == 0:
            print(f"\n[!] Voucher has NO entries - fixing now...")
            
            with transaction.atomic():
                # Store voucher number for logging
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
                
                print(f"  ✓ Reset Bill #14 to VERIFIED status")
                print(f"\n{'='*80}")
                print("SUCCESS!")
                print("  Bill #14 has been reset to VERIFIED status.")
                print("  You can now re-approve it to create proper journal entries.")
                print("=" * 80)
        else:
            print(f"\n[OK] Voucher has {entry_count} entries - no fix needed.")
            
except Bill.DoesNotExist:
    print("\n[ERROR] Bill #14 not found!")
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
