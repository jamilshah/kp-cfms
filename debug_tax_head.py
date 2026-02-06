import os
import django
import sys

# Setup Django environment
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cfms.settings')
django.setup()

from apps.finance.models import GlobalHead, BudgetHead, SystemCode

def debug_tax_configuration():
    print("--- Debugging Tax Configuration ---")
    
    # 1. Check GlobalHead
    try:
        gh = GlobalHead.objects.get(code='G01204')
        print(f"Global Head Found: {gh}")
        print(f"  System Code: {gh.system_code}")
        print(f"  Expected: {SystemCode.TAX_IT}")
        
        if gh.system_code != SystemCode.TAX_IT:
            print("  [ERROR] System code mismatch!")
    except GlobalHead.DoesNotExist:
        print("[ERROR] GlobalHead G01204 NOT FOUND")
        return

    # 2. Check BudgetHeads
    bhs = BudgetHead.objects.filter(global_head=gh)
    print(f"\nBudgetHeads linked to {gh.code}: {bhs.count()}")
    
    if bhs.count() == 0:
        print("  [ERROR] No BudgetHeads found for this GlobalHead!")
    
    for bh in bhs:
        print(f"  - BudgetHead ID: {bh.id}")
        print(f"    Name: {bh.name} (via logic)")
        print(f"    Fund: {bh.fund.code}")
        print(f"    Function: {bh.function.code}")
        print(f"    Is Active: {bh.is_active}")
        
    # 3. Simulate Query from View
    print("\nSimulating View Query:")
    try:
        res = BudgetHead.objects.get(
            global_head__system_code='TAX_IT',
            is_active=True
        )
        print("  [SUCCESS] Query returned 1 result:", res)
    except BudgetHead.DoesNotExist:
        print("  [FAILED] Query returned DoesNotExist")
    except BudgetHead.MultipleObjectsReturned:
        print("  [FAILED] Query returned MultipleObjectsReturned (This is handled in view, but interesting)")
        res = BudgetHead.objects.filter(
             global_head__system_code='TAX_IT',
             is_active=True
        ).first()
        print("    -> First result would be:", res)

if __name__ == "__main__":
    debug_tax_configuration()
