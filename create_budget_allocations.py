"""
Script to create budget allocations for bill creation
Run this after setting up your budget heads and fiscal year
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Organization
from apps.budgeting.models import BudgetAllocation, FiscalYear
from apps.finance.models import BudgetHead, AccountType

print("=" * 80)
print("Budget Allocation Generator")
print("=" * 80)

# 1. Get current organization
org = Organization.objects.filter(is_active=True).first()
if not org:
    print("ERROR: No active organization found!")
    print("Please create an organization first.")
    exit(1)

print(f"\nOrganization: {org.name}")

# 2. Get current operating fiscal year
current_fy = FiscalYear.get_current_operating_year(org)
if not current_fy:
    print(f"ERROR: No current operating fiscal year for {org.name}")
    print("Please set up a fiscal year as 'current operating'")
    exit(1)

print(f"Fiscal Year: {current_fy.year_name}")

# 3. Get all expenditure budget heads
exp_heads = BudgetHead.objects.filter(
    global_head__account_type=AccountType.EXPENDITURE,
    posting_allowed=True,
    is_active=True
).select_related('global_head', 'function')

print(f"\nFound {exp_heads.count()} expenditure budget heads")

if exp_heads.count() == 0:
    print("ERROR: No expenditure budget heads found!")
    print("Please create budget heads first.")
    exit(1)

# 4. Create allocations
created_count = 0
skipped_count = 0
default_amount = Decimal('500000.00')  # Default allocation amount

print(f"\nCreating allocations (Default: Rs. {default_amount:,.2f} per head)...\n")

for head in exp_heads:
    # Check if allocation already exists
    exists = BudgetAllocation.objects.filter(
        organization=org,
        fiscal_year=current_fy,
        budget_head=head
    ).exists()
    
    if exists:
        print(f"  [SKIP] {head.code} - {head.name} (already exists)")
        skipped_count += 1
        continue
    
    # Create new allocation
    allocation = BudgetAllocation.objects.create(
        organization=org,
        fiscal_year=current_fy,
        budget_head=head,
        original_allocation=default_amount,
        revised_allocation=default_amount,
        released_amount=default_amount
    )
    print(f"  [OK]   {head.code} - {head.name} -> Rs. {default_amount:,.2f}")
    created_count += 1

print(f"\n{'=' * 80}")
print(f"SUMMARY")
print(f"{'=' * 80}")
print(f"Created: {created_count} allocations")
print(f"Skipped: {skipped_count} allocations (already exist)")
print(f"Total: {created_count + skipped_count} allocations")
print(f"\nBill creation should now work!")
print(f"Log in as Dealing Assistant and try creating a bill.")
print(f"{'=' * 80}")
