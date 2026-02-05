"""
Script to fix Bill #14 by resetting it to VERIFIED status and deleting the empty voucher
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill, BillStatus
from apps.finance.models import Voucher
from django.db import transaction

print("=" * 80)
print("Fixing Bill #14 - Resetting to VERIFIED Status")
print("=" * 80)

# Get Bill #14
try:
    bill = Bill.objects.get(id=14)
    print(f"\nFound Bill #14: {bill.bill_number}")
    print(f"  Current Status: {bill.status}")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Gross: {bill.gross_amount}, Tax: {bill.tax_amount}, Net: {bill.net_amount}")
    
    if bill.liability_voucher:
        voucher = bill.liability_voucher
        entry_count = voucher.entries.count()
        print(f"\n  Liability Voucher: {voucher.voucher_no}")
        print(f"  Posted: {voucher.is_posted}")
        print(f"  Journal Entries: {entry_count}")
        
        if entry_count == 0:
            print(f"\n  [!] Voucher has NO entries - this needs to be fixed!")
            
            # Confirm action
            print("\n" + "=" * 80)
            print("PROPOSED FIX:")
            print("  1. Delete empty voucher JV-2025-26-0002")
            print("  2. Reset Bill #14 status from APPROVED to VERIFIED")
            print("  3. Clear approval timestamp and user")
            print("  4. Bill can then be re-approved properly")
            print("=" * 80)
            
            response = input("\nProceed with fix? (yes/no): ").strip().lower()
            
            if response == 'yes':
                with transaction.atomic():
                    # Delete the empty voucher
                    voucher_no = voucher.voucher_no
                    voucher.delete()
                    print(f"\n✓ Deleted empty voucher {voucher_no}")
                    
                    # Reset bill status
                    bill.status = BillStatus.VERIFIED
                    bill.approved_at = None
                    bill.approved_by = None
                    bill.liability_voucher = None
                    bill.save(update_fields=['status', 'approved_at', 'approved_by', 'liability_voucher', 'updated_at'])
                    
                    print(f"✓ Reset Bill #14 to VERIFIED status")
                    print(f"\n{'='*80}")
                    print("SUCCESS!")
                    print("  Bill #14 is now ready to be re-approved.")
                    print("  The bill will create proper journal entries on approval.")
                    print("=" * 80)
            else:
                print("\nOperation cancelled.")
        else:
            print(f"\n  Voucher has {entry_count} entries - no fix needed.")
    else:
        print(f"\n  No liability voucher - bill may not be approved yet.")
        
except Bill.DoesNotExist:
    print("\nBill #14 not found!")
except Exception as e:
    print(f"\nError: {str(e)}")
    import traceback
    traceback.print_exc()
