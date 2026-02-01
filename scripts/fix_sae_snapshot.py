
import os
import django
import sys
from decimal import Decimal
from datetime import date
from django.db.models import Sum
from django.utils import timezone

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import FiscalYear, BudgetAllocation, SAERecord, BudgetStatus, QuarterlyRelease, ReleaseQuarter
from apps.finance.models import AccountType
from apps.users.models import CustomUser

def fix_sae_snapshot():
    print("--- Fixing SAE Snapshot & Releasing Funds ---")
    
    # 1. Find FY with allocations
    target_fy = None
    fys = FiscalYear.objects.filter(is_active=True)
    
    for fy in fys:
        if BudgetAllocation.objects.filter(fiscal_year=fy).exists():
            target_fy = fy
            break
            
    if not target_fy:
        print("No active FY with allocations found. Checking inactive ones...")
        fys = FiscalYear.objects.all().order_by('-id')
        for fy in fys:
            if BudgetAllocation.objects.filter(fiscal_year=fy).exists():
                target_fy = fy
                break
    
    if not target_fy:
        print("ERROR: No Fiscal Year with allocations found. Aborting.")
        return

    print(f"Targeting FY: {target_fy.year_name} (ID: {target_fy.id})")
    
    # 2. Calculate Totals
    allocations = BudgetAllocation.objects.filter(fiscal_year=target_fy)
    
    total_receipts = allocations.filter(
        budget_head__global_head__account_type=AccountType.REVENUE
    ).aggregate(t=Sum('original_allocation'))['t'] or Decimal('0.00')
    
    total_expenditure = allocations.filter(
        budget_head__global_head__account_type=AccountType.EXPENDITURE
    ).aggregate(t=Sum('original_allocation'))['t'] or Decimal('0.00')
    
    contingency = allocations.filter(
        budget_head__global_head__code__startswith='A09'
    ).aggregate(t=Sum('original_allocation'))['t'] or Decimal('0.00')
    
    print(f"Receipts: {total_receipts}")
    print(f"Expenditure: {total_expenditure}")
    print(f"Contingency: {contingency}")
    
    # 3. Create/Update SAE Record
    admin_user = CustomUser.objects.filter(is_superuser=True).first() or CustomUser.objects.first()
    
    sae, created = SAERecord.objects.get_or_create(
        fiscal_year=target_fy,
        defaults={
            'sae_number': f"SAE-{target_fy.year_name}-FIXED",
            'total_receipts': total_receipts,
            'total_expenditure': total_expenditure,
            'contingency_reserve': contingency,
            'approved_by': admin_user
        }
    )
    
    if not created:
        print("Updating existing SAE record...")
        sae.total_receipts = total_receipts
        sae.total_expenditure = total_expenditure
        sae.contingency_reserve = contingency
        sae.save()
    else:
        print(f"Created new SAE record: {sae.sae_number}")

    # 4. Lock Budget & Set Status
    target_fy.sae_number = sae.sae_number
    target_fy.status = BudgetStatus.LOCKED
    target_fy.is_locked = True
    target_fy.is_active = False # Budget entry is closed
    target_fy.save()
    print("Locked Fiscal Year.")
    
    # 5. Create Quarterly Releases
    releases = [
        (ReleaseQuarter.Q1, date(target_fy.start_date.year, 7, 1)),
        (ReleaseQuarter.Q2, date(target_fy.start_date.year, 10, 1)),
        (ReleaseQuarter.Q3, date(target_fy.start_date.year + 1, 1, 1)),
        (ReleaseQuarter.Q4, date(target_fy.start_date.year + 1, 4, 1)),
    ]
    
    for q, d in releases:
        QuarterlyRelease.objects.get_or_create(
            fiscal_year=target_fy,
            quarter=q,
            defaults={
                'organization': target_fy.organization,
                'release_date': d,
                'created_by': admin_user,
                'updated_by': admin_user
            }
        )

    # 6. Release Funds (Simulate Q1 Release)
    # 25% for Non-Salary, 100% for Salary
    print("Releasing funds for Q1...")
    
    salary_allocs = allocations.filter(budget_head__global_head__code__startswith='A01')
    non_salary_allocs = allocations.exclude(budget_head__global_head__code__startswith='A01')
    
    # Salary - 100% released
    updated_sal = salary_allocs.update(released_amount=django.db.models.F('revised_allocation'))
    print(f"Released full budget for {updated_sal} salary heads.")
    
    # Non-Salary - 25% released (Simulating Q1)
    # Note: Using python loop for percent calc to be safe with decimals
    count_ns = 0
    for alloc in non_salary_allocs:
        # Assuming Q1 release only for now to enable testing
        release_amount = alloc.revised_allocation * Decimal('0.25')
        # Check if already released to avoid double counting if run multiple times
        if alloc.released_amount < release_amount:
             alloc.released_amount = release_amount
             alloc.save()
             count_ns += 1
             
    print(f"Released 25% budget for {count_ns} non-salary heads.")
    
    # Mark Q1 as released
    q1_rel = QuarterlyRelease.objects.get(fiscal_year=target_fy, quarter=ReleaseQuarter.Q1)
    q1_rel.is_released = True
    q1_rel.total_amount = Decimal('0') # TODO: Calculate actual sum if needed, but not critical for this fix
    q1_rel.save()
    
    print("Done! Budget is finalized and funds are released.")

if __name__ == '__main__':
    fix_sae_snapshot()
