"""
Script to deactivate unused G01204 BudgetHead (FGEN-015101-G01204)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead
from decimal import Decimal

print("=" * 80)
print("Deactivating Unused G01204 BudgetHead")
print("=" * 80)

# Find the unused BudgetHead
try:
    unused_bh = BudgetHead.objects.get(id=4640)  # FGEN-015101-G01204
    
    print(f"\nFound BudgetHead:")
    print(f"  ID: {unused_bh.id}")
    print(f"  Code: {unused_bh.get_full_code()}")
    print(f"  Name: {unused_bh.global_head.name}")
    print(f"  Active: {unused_bh.is_active}")
    
    # Check if it has any transactions
    from django.db.models import Sum, Q
    from django.db.models.functions import Coalesce
    from apps.core.models import Organization
    
    org = Organization.objects.first()
    
    totals = unused_bh.entries.filter(
        voucher__is_posted=True,
        voucher__organization=org
    ).aggregate(
        total_dr=Coalesce(Sum('debit'), Decimal('0.00')),
        total_cr=Coalesce(Sum('credit'), Decimal('0.00'))
    )
    
    print(f"  Transactions: Dr {totals['total_dr']}, Cr {totals['total_cr']}")
    
    if totals['total_dr'] == Decimal('0.00') and totals['total_cr'] == Decimal('0.00'):
        print(f"\n  ✓ BudgetHead has no transactions - safe to deactivate")
        
        unused_bh.is_active = False
        unused_bh.save(update_fields=['is_active', 'updated_at'])
        
        print(f"\n{'='*80}")
        print("SUCCESS!")
        print(f"  Deactivated {unused_bh.get_full_code()}")
        print(f"  This BudgetHead will no longer appear in reports.")
        print("=" * 80)
    else:
        print(f"\n  [!] BudgetHead has transactions - cannot deactivate!")
        
except BudgetHead.DoesNotExist:
    print("\n[ERROR] BudgetHead #4640 not found!")
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
