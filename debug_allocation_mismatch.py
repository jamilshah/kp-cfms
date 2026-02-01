
import os
import django
import sys
from django.db.models import Q

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill
from apps.budgeting.models import BudgetAllocation, FiscalYear
from apps.finance.models import BudgetHead

def debug_mismatch():
    print("--- Debugging Bill vs Allocation Mismatch ---")
    
    # 1. Get the specific Bill
    try:
        bill = Bill.objects.get(bill_number='OS-26-01-001')
    except Bill.DoesNotExist:
        print("Bill 'OS-26-01-001' not found. Listing all bills:")
        for b in Bill.objects.all():
             print(f" - ID: {b.id} | No: {b.bill_number} | Org: {b.organization}")
        return

    print(f"Found Bill ID: {bill.id} | No: {bill.bill_number}")
    print(f"Bill Organization: {bill.organization} (ID: {bill.organization_id if bill.organization else 'None'})")
    print(f"Bill Fiscal Year: {bill.fiscal_year.year_name} (ID: {bill.fiscal_year.id})")
    print(f"Bill FY Organization: {bill.fiscal_year.organization} (ID: {bill.fiscal_year.organization_id if bill.fiscal_year.organization else 'None'})")

    # 2. Check Bill Lines
    print("\nBill Lines:")
    for line in bill.lines.all():
        bh = line.budget_head
        print(f" - Head: {bh.code} ({bh.name})")
        print(f"   Line Amount: {line.amount}")
        
        # 3. Simulate View Lookup
        print(f"   [Lookup Probe] BudgetHead ID: {bh.id}")
        
        try:
            alloc = BudgetAllocation.objects.get(
                organization=bill.organization,
                fiscal_year=bill.fiscal_year,
                budget_head=bh
            )
            print(f"   >>> FOUND MATCHING ALLOCATION! Orig: {alloc.original_allocation}")
        except BudgetAllocation.DoesNotExist:
            print("   >>> NO EXACT MATCH FOUND (as per View logic).")
            
            # 4. Search for 'Nearby' Allocations
            candidates = BudgetAllocation.objects.filter(
                budget_head=bh,
                fiscal_year=bill.fiscal_year
            )
            if candidates.exists():
                print(f"   [Hints] Found {candidates.count()} candidates for this FY/Head but with different Org:")
                for c in candidates:
                    print(f"     - Alloc ID: {c.id} | Org: {c.organization} (ID: {c.organization_id}) | Orig: {c.original_allocation}")
            else:
                print("   [Hints] No allocations found for this FY/Head at all.")

            # Check for Allocations with None Organization
            none_org = BudgetAllocation.objects.filter(
                budget_head=bh,
                fiscal_year=bill.fiscal_year,
                organization__isnull=True
            )
            if none_org.exists():
                print(f"   [Hints] Found allocations with NO Organization: {none_org.count()}")

    print("\n--- Comparative Analysis of Budget Heads ---")
    try:
        h1 = BudgetHead.objects.get(id=948)
        print(f"Head ID 948 (Used in Bill):")
        print(f" - Code: {h1.code}")
        print(f" - Global: {h1.global_head.code} - {h1.global_head.name}")
        print(f" - Function: {h1.function.code} - {h1.function.name}")
        print(f" - Fund: {h1.fund.code} - {h1.fund.name}")
        
        h2 = BudgetHead.objects.get(id=1326)
        print(f"Head ID 1326 (Has Allocation):")
        print(f" - Code: {h2.code}")
        print(f" - Global: {h2.global_head.code} - {h2.global_head.name}")
        print(f" - Function: {h2.function.code} - {h2.function.name}")
        print(f" - Fund: {h2.fund.code} - {h2.fund.name}")
    except BudgetHead.DoesNotExist:
        print("Could not find one of the heads.")

if __name__ == '__main__':
    debug_mismatch()
