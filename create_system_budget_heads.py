"""
Script to create BudgetHeads for system accounts (AP, TAX_IT, etc.)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import GlobalHead, BudgetHead, Fund, FunctionCode, SystemCode
from apps.core.models import Organization

print("=" * 80)
print("Creating BudgetHeads for System Accounts")
print("=" * 80)

# Get first organization, fund, and function
org = Organization.objects.first()
fund = Fund.objects.first()
func = FunctionCode.objects.first()

print(f"\nUsing:")
print(f"  Organization: {org}")
print(f"  Fund: {fund}")
print(f"  Function: {func}")

# System codes that need BudgetHeads
SYSTEM_CODES_NEEDED = [
    SystemCode.AP,      # Accounts Payable
    SystemCode.TAX_IT,  # Income Tax Payable
    SystemCode.TAX_GST, # GST/Sales Tax Payable
]

created_count = 0
existing_count = 0

for sys_code in SYSTEM_CODES_NEEDED:
    # Get the GlobalHead for this system code
    global_head = GlobalHead.objects.filter(system_code=sys_code).first()
    
    if not global_head:
        print(f"\n[ERROR] GlobalHead for {sys_code} not found!")
        print(f"  Run: python manage.py assign_system_codes")
        continue
    
    print(f"\n{sys_code}:")
    print(f"  GlobalHead: {global_head.code} - {global_head.name}")
    
    # Check if BudgetHead already exists
    existing = BudgetHead.objects.filter(
        global_head=global_head,
        fund=fund,
        function=func
    ).first()
    
    if existing:
        print(f"  [OK] BudgetHead already exists: {existing.get_full_code()} (Active: {existing.is_active})")
        if not existing.is_active:
            existing.is_active = True
            existing.save()
            print(f"  [!!] Activated BudgetHead")
        existing_count += 1
    else:
        # Create BudgetHead
        budget_head = BudgetHead.objects.create(
            global_head=global_head,
            fund=fund,
            function=func,
            is_active=True,
            posting_allowed=True
        )
        print(f"  [OK] Created BudgetHead: {budget_head.get_full_code()}")
        created_count += 1

print("\n" + "=" * 80)
print(f"SUMMARY:")
print(f"  Created: {created_count}")
print(f"  Existing: {existing_count}")
print("=" * 80)
