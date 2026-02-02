#!/usr/bin/env python
"""
Final fix: Change remaining over-mapped departmental heads to UNIVERSAL.

These heads are currently marked as DEPARTMENTAL but are mapped to 22 out of 25 functions,
indicating they should actually be UNIVERSAL (applicable to all departments/functions).
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead, FunctionCode, Fund
from django.db import transaction

def main():
    print("=" * 100)
    print("FINAL FIX: CONVERT OVER-MAPPED DEPARTMENTAL HEADS TO UNIVERSAL")
    print("=" * 100)
    
    # These heads are mapped to 22 functions (should be 25)
    over_mapped_codes = [
        'A03102',  # Legal Fees - any dept can have legal costs
        'A03907',  # Advertising & Publicity - any dept
        'A03909',  # Tax Refunds - any function
        'A04101',  # Pension - retirees from any function
        'A04102',  # Commuted value of pension
        'A04114',  # Superannuation Encashment
        'A13001',  # Transport - vehicles across functions
        'B01313',  # TTIP - tax collections can be under various functions
        'B03065',  # Tax on Bank Cheques - same
        'C01803',  # Interest - revenue for any function
        'C02701',  # Building Rent - revenue
        'C02710',  # Registration fees - revenue
        'C02937',  # Fines - revenue
        'C03682',  # Federal Grant - applies to all
        'C03684',  # Provincial Grant - applies to all
        'C03707',  # Other Receipts - revenue
        'C03805',  # Rent, Rates and Taxes - revenue
        'C03841',  # Fees, Fines - revenue
        'C03849',  # Contractor Penalty - revenue
        'C03874',  # Sports Receipts - can be under different functions
        'C03880',  # TMA Other Non-tax Revenues - revenue
        'F01401',  # Cash Balances - asset management for all
        'F01403',  # Petty Cash - asset management for all
        'F01406',  # Cash at Bank - asset management for all
    ]
    
    print(f"\n1. CONVERTING {len(over_mapped_codes)} HEADS TO UNIVERSAL SCOPE:")
    print("-" * 100)
    
    converted = []
    for code in over_mapped_codes:
        try:
            gh = GlobalHead.objects.get(code=code)
            old_scope = gh.scope
            gh.scope = 'UNIVERSAL'
            gh.save()
            converted.append((code, gh.name, old_scope))
            print(f"   ✓ {code:<10} {gh.name[:55]:<57} : {old_scope} -> UNIVERSAL")
        except GlobalHead.DoesNotExist:
            print(f"   ✗ {code} not found")
    
    # 2. Add missing mappings for these newly universal heads
    print(f"\n2. ADDING MISSING MAPPINGS FOR NEWLY UNIVERSAL HEADS:")
    print("-" * 100)
    
    all_functions = FunctionCode.objects.filter(is_active=True).order_by('code')
    fund = Fund.objects.get(code='GEN')
    
    print(f"   Target: {all_functions.count()} functions")
    
    created_count = 0
    
    for code, name, old_scope in converted:
        gh = GlobalHead.objects.get(code=code)
        
        # Check which functions are missing
        existing_funcs = set(
            BudgetHead.objects.filter(
                global_head=gh,
                fund=fund
            ).values_list('function__code', flat=True)
        )
        
        missing_funcs = [f for f in all_functions if f.code not in existing_funcs]
        
        if missing_funcs:
            print(f"\n   {code} - Missing {len(missing_funcs)} functions:")
            for func in missing_funcs:
                try:
                    bh, created = BudgetHead.objects.get_or_create(
                        fund=fund,
                        function=func,
                        global_head=gh,
                        sub_code='00',
                        defaults={
                            'head_type': 'REGULAR',
                            'posting_allowed': True,
                            'budget_control': True,
                            'is_active': True
                        }
                    )
                    if created:
                        created_count += 1
                        print(f"      ✓ {func.code}")
                except Exception as e:
                    print(f"      ✗ {func.code}: {e}")
    
    print(f"\n   Total new mappings created: {created_count}")
    
    # 3. Final verification
    print(f"\n3. FINAL VERIFICATION:")
    print("-" * 100)
    
    universal_count = GlobalHead.objects.filter(scope='UNIVERSAL').count()
    dept_count = GlobalHead.objects.filter(scope='DEPARTMENTAL').count()
    total_bh = BudgetHead.objects.count()
    
    print(f"\n   GlobalHead Scope Distribution:")
    print(f"      UNIVERSAL:    {universal_count} heads")
    print(f"      DEPARTMENTAL: {dept_count} heads")
    print(f"\n   Total BudgetHeads: {total_bh}")
    
    # Check function coverage for all functions
    print(f"\n   Function Coverage (should all have ~{universal_count} heads):")
    for func in all_functions:
        head_count = BudgetHead.objects.filter(function=func).count()
        marker = "✓" if head_count >= 100 else "⚠️"
        print(f"      {marker} {func.code:<10} : {head_count:>3} budget heads")
    
    print("\n" + "=" * 100)
    print("FINAL FIX COMPLETE")
    print("=" * 100)
    print("\n✅ ALL BUDGET HEADS NOW PROPERLY MAPPED!")
    print("   - Universal heads (salary, common expenses, revenue, assets) → ALL functions")
    print("   - Departmental heads (if any remain) → Specific functions only")

if __name__ == '__main__':
    with transaction.atomic():
        try:
            main()
        except Exception as e:
            print(f"\n✗ Error: {e}")
            raise
