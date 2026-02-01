"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Interim Pilot Budget Loader
             Loads lump-sum budget appropriations for key heads to allow 
             expenditure processing during the pilot phase, bypassing the 
             incomplete Budget UI.
-------------------------------------------------------------------------
"""
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings

# Setup Django Environment if running as standalone script
# (Not needed if running via manage.py shell, but good for portability)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.core.models import Organization
from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.finance.models import BudgetHead, Fund, FunctionCode, GlobalHead

def run():
    print("----------------------------------------------------------------")
    print(" KP-CFMS Pilot Budget Loader (Interim)")
    print("----------------------------------------------------------------")

    # 1. Configuration
    # ----------------
    # Set the target Organization and Fiscal Year
    TARGET_ORG_NAME = "TMA Pilot Site" # UPDATE THIS TO ACTUAL ORG NAME IF KNOWN, OR USE FIRST
    FISCAL_YEAR = "2025-26"
    
    # Define Pilot Budget Entries (Function, Object, Amount)
    PILOT_ENTRIES = [
        # Contingency & Operational
        {"func": "063102", "obj": "A03303", "amount": 500000, "desc": "Electricity Charges (Water Supply)"},
        {"func": "063102", "obj": "A03304", "amount": 200000, "desc": "POL charges"},
        {"func": "011108", "obj": "A03805", "amount": 100000, "desc": "Travelling Allowance"},
        
        # Salary (Sanitation)
        {"func": "055101", "obj": "A01101", "amount": 5000000, "desc": "Basic Pay Officers (Sanitation)"},
        {"func": "055101", "obj": "A01151", "amount": 15000000, "desc": "Basic Pay Staff (Sanitation)"},
        {"func": "055101", "obj": "A01202", "amount": 2000000, "desc": "House Rent Allowance"},
        
        # Development Projects
        {"func": "045101", "obj": "A12403", "amount": 10000000, "desc": "Construction of Roads/Streets"},
    ]

    try:
        with transaction.atomic():
            # 2. Get Organization
            # -------------------
            # For pilot, we might just pick the first active TMA if specific name not found
            org = Organization.objects.filter(name__icontains=TARGET_ORG_NAME).first()
            if not org:
                org = Organization.objects.filter(is_active=True).first()
                if not org:
                    print("ERROR: No active Organization found.")
                    return
                print(f"WARNING: Target '{TARGET_ORG_NAME}' not found. Using '{org.name}' instead.")
            else:
                print(f"Target Organization: {org.name}")

            # 3. Get/Create Fiscal Year
            # -------------------------
            fy, created = FiscalYear.objects.get_or_create(
                organization=org,
                year_name=FISCAL_YEAR,
                defaults={
                    'start_date': '2025-07-01',
                    'end_date': '2026-06-30',
                    'is_active': True,
                    'is_locked': True, # Lock it so we can execute directly
                    'status': 'LOCKED',
                    'sae_number': 'PILOT-SAE-001'
                }
            )
            print(f"Fiscal Year: {fy.year_name} (Created: {created})")

            # 4. Process Entries
            # ------------------
            print("\nProcessing Allocations...")
            for entry in PILOT_ENTRIES:
                # Resolve IDs
                try:
                    # Resolve Function Code (e.g., 063102)
                    function_code = FunctionCode.objects.get(code=entry['func'])
                    
                    # Resolve Global Head (Object, e.g., A03303)
                    global_head = GlobalHead.objects.get(code=entry['obj'])
                    
                    # Determine Fund (Simple logic for pilot: A* = GEN/DEV)
                    # Use Development Fund for A12* (Capital Assets), General for others
                    if entry['obj'].startswith('A12'):
                        fund_code = Fund.CODE_DEVELOPMENT
                    else:
                        fund_code = Fund.CODE_GENERAL
                        
                    fund = Fund.objects.get(code=fund_code)

                    # Get/Create Budget Head (The Matrix Intersection)
                    budget_head, bh_created = BudgetHead.objects.get_or_create(
                        fund=fund,
                        function=function_code,
                        global_head=global_head,
                        sub_code='00', # Default
                        defaults={
                            'head_type': 'REGULAR',
                            'posting_allowed': True
                        }
                    )
                    
                    # Create/Update Allocation
                    # CRITICAL: We set released_amount = original_allocation to bypass quarterly releases
                    amount = Decimal(entry['amount'])
                    
                    allocation, alloc_created = BudgetAllocation.objects.update_or_create(
                        organization=org,
                        fiscal_year=fy,
                        budget_head=budget_head,
                        defaults={
                            'original_allocation': amount,
                            'revised_allocation': amount,
                            'released_amount': amount, # FULL RELEASE FOR PILOT
                            'remarks': f"Interim Pilot Load: {entry['desc']}"
                        }
                    )
                    
                    status = "Created" if alloc_created else "Updated"
                    print(f" {status}: {budget_head.code} - {entry['desc']} : PKR {amount:,.2f}")

                except FunctionCode.DoesNotExist:
                    print(f" ERROR: Function Code {entry['func']} not found.")
                except GlobalHead.DoesNotExist:
                    print(f" ERROR: Object Code {entry['obj']} not found.")
                except Fund.DoesNotExist:
                    print(f" ERROR: Fund {fund_code} not found.")
                except Exception as e:
                    print(f" ERROR: {str(e)}")

            print("\n----------------------------------------------------------------")
            print(" SUCCESS: Pilot Budget Loaded.")
            print("----------------------------------------------------------------")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    run()
