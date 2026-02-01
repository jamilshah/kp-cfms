import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Organization
from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.finance.models import BudgetHead

def fix():
    org = Organization.objects.first()
    if not org:
        print("No Organization found in DB!")
        return

    print(f"Target Organization: {org.name} (ID: {org.id})")

    # 1. Fix FiscalYear
    fy = FiscalYear.objects.filter(is_active=True).first()
    if not fy:
        print("No active Fiscal Year found!")
        return
    
    if fy.organization != org:
        fy.organization = org
        fy.save()
        print(f"Linked Fiscal Year {fy.year_name} to {org.name}")
    else:
        print(f"Fiscal Year {fy.year_name} already correctly linked.")

    # 2. Fix BudgetAllocations
    allocations = BudgetAllocation.objects.filter(organization=None)
    count = allocations.count()
    if count > 0:
        allocations.update(organization=org)
        print(f"Transferred {count} allocations from 'None' to '{org.name}'")
    else:
        print("No orphaned allocations found.")

    # 3. Final Verification
    actual_count = BudgetAllocation.objects.filter(organization=org, fiscal_year=fy).count()
    total_heads = BudgetHead.objects.filter(is_active=True).count()
    print(f"Total Budget Heads: {total_heads}")
    print(f"Allocations for {org.name} in {fy.year_name}: {actual_count}")

if __name__ == "__main__":
    fix()
