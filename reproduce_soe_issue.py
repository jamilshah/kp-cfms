
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.finance.models import BudgetHead, AccountType, GlobalHead
from django.db.models import Sum

def reproduce():
    print("Checking SAE calculation logic...")
    
    # 1. Get Active Fiscal Year
    fy = FiscalYear.objects.filter(is_active=True).first()
    if not fy:
        print("No active Fiscal Year found. Checking ANY fiscal year...")
        fy = FiscalYear.objects.last()
        if not fy:
            print("No Fiscal Year found at all.")
            return

    print(f"Using Fiscal Year: {fy.year_name} (ID: {fy.id})")
    print(f"Organization: {fy.organization}")

    # 2. Check Allocations for this FY
    allocations = BudgetAllocation.objects.filter(fiscal_year=fy)
    count = allocations.count()
    print(f"Total Allocations: {count}")

    if count == 0:
        print("No allocations found. Cannot reproduce issue.")
        return

    # 3. Check Account Types
    exp_allocations = allocations.filter(
        budget_head__global_head__account_type=AccountType.EXPENDITURE
    )
    print(f"Expenditure Allocations: {exp_allocations.count()}")

    # 4. Sum them up manually
    total_manual = Decimal('0.00')
    for alloc in exp_allocations:
        print(f"  - {alloc.budget_head.code}: {alloc.original_allocation} (AccountType: {alloc.budget_head.global_head.account_type})")
        total_manual += alloc.original_allocation
    
    print(f"Manual Sum: {total_manual}")

    # 5. Use the method
    total_method = fy.get_total_expenditure()
    print(f"Method get_total_expenditure(): {total_method}")

    if total_method == 0 and total_manual > 0:
        print("ISSUE REPRODUCED: Method returns 0 but allocations exist.")
    elif total_manual == 0:
        print("Allocations have 0 original_allocation or AccountType is wrong.")

    # 6. Check SAE Record if exists
    if hasattr(fy, 'sae_record'):
         print(f"Existing SAE Record: {fy.sae_record.total_expenditure}")
    else:
        print("No SAE Record for this FY.")

if __name__ == '__main__':
    reproduce()
