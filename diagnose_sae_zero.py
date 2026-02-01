
import os
import django
from decimal import Decimal
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import FiscalYear, BudgetAllocation, SAERecord
from apps.finance.models import AccountType

def diagnose():
    print("--- Diagnosing SAE Zero Issue ---")
    
    # Find any FY with allocations
    fys = FiscalYear.objects.all().order_by('-id')
    print(f"Found {fys.count()} Fiscal Years.")
    
    for fy in fys:
        print(f"\nChecking FY: {fy.year_name} (ID: {fy.id})")
        count = BudgetAllocation.objects.filter(fiscal_year=fy).count()
        print(f"  Allocations: {count}")
        
        sae = getattr(fy, 'sae_record', None)
        if sae:
            print(f"  SAE Record: {sae.sae_number} | Exp: {sae.total_expenditure}")
        else:
            print("  SAE Record: None")
            
        if count > 0:
            total_orig = BudgetAllocation.objects.filter(
                fiscal_year=fy
            ).aggregate(t=Sum('original_allocation'))['t'] or Decimal(0)
            print(f"  Actual Allocation Sum: {total_orig}")

if __name__ == '__main__':
    diagnose()
