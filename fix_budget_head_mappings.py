#!/usr/bin/env python
"""
Fix redundant and incorrect budget head to function mappings.

Issues to fix:
1. Change A01* (salary) heads from DEPARTMENTAL to UNIVERSAL scope
2. Add missing function mappings for universal heads to new functions
3. Remove redundant departmental mappings (if any are truly departmental, keep only relevant ones)
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
    print("FIXING BUDGET HEAD TO FUNCTION MAPPINGS")
    print("=" * 100)
    
    # Get current counts
    total_budget_heads = BudgetHead.objects.count()
    print(f"\nTotal BudgetHeads before fix: {total_budget_heads}")
    
    # 1. FIX SALARY HEADS SCOPE (A01* should be UNIVERSAL, not DEPARTMENTAL)
    print("\n1. FIXING SALARY HEADS SCOPE (A01* -> UNIVERSAL):")
    print("-" * 100)
    
    salary_heads = GlobalHead.objects.filter(
        code__startswith='A01',
        scope='DEPARTMENTAL'
    )
    
    print(f"   Found {salary_heads.count()} A01* heads marked as DEPARTMENTAL")
    print(f"   Changing them to UNIVERSAL...")
    
    updated_count = salary_heads.update(scope='UNIVERSAL')
    print(f"   ✓ Updated {updated_count} global heads to UNIVERSAL scope")
    
    # 2. ADD MISSING MAPPINGS FOR UNIVERSAL HEADS TO NEW FUNCTIONS
    print("\n2. ADDING MISSING UNIVERSAL HEAD MAPPINGS TO NEW FUNCTIONS:")
    print("-" * 100)
    
    # Get all active functions
    all_functions = FunctionCode.objects.filter(is_active=True).order_by('code')
    universal_heads = GlobalHead.objects.filter(scope='UNIVERSAL')
    fund = Fund.objects.get(code='GEN')  # General Fund
    
    print(f"   Active functions: {all_functions.count()}")
    print(f"   Universal global heads: {universal_heads.count()}")
    print(f"   Using fund: {fund.code} - {fund.name}")
    
    created_count = 0
    skipped_count = 0
    
    for gh in universal_heads:
        # Check which functions are missing this universal head
        existing_funcs = set(
            BudgetHead.objects.filter(
                global_head=gh,
                fund=fund
            ).values_list('function__code', flat=True)
        )
        
        missing_funcs = [f for f in all_functions if f.code not in existing_funcs]
        
        if missing_funcs:
            print(f"\n   {gh.code} - {gh.name[:50]}")
            print(f"      Missing in {len(missing_funcs)} functions: {', '.join([f.code for f in missing_funcs])}")
            
            for func in missing_funcs:
                # Create missing budget head
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
                        print(f"         ✓ Created: {func.code}")
                    else:
                        skipped_count += 1
                except Exception as e:
                    print(f"         ✗ Error for {func.code}: {e}")
    
    print(f"\n   SUMMARY:")
    print(f"      Created: {created_count} new budget head mappings")
    print(f"      Skipped: {skipped_count} (already existed)")
    
    # 3. VERIFY NO TRULY DEPARTMENTAL HEADS ARE OVER-MAPPED
    print("\n3. CHECKING DEPARTMENTAL HEADS FOR OVER-MAPPING:")
    print("-" * 100)
    
    # After changing A01* to universal, check what's left as departmental
    remaining_dept_heads = GlobalHead.objects.filter(scope='DEPARTMENTAL')
    print(f"   Remaining DEPARTMENTAL global heads: {remaining_dept_heads.count()}")
    
    over_mapped = []
    for gh in remaining_dept_heads:
        func_count = BudgetHead.objects.filter(global_head=gh).values('function').distinct().count()
        if func_count > 15:  # If mapped to more than 15 functions, it's probably over-mapped
            over_mapped.append((gh.code, gh.name, func_count))
    
    if over_mapped:
        print("\n   ⚠️  POTENTIALLY OVER-MAPPED DEPARTMENTAL HEADS:")
        for code, name, count in over_mapped:
            print(f"      {code:<10} {name[:45]:<47} : {count} functions")
        print("\n   These should be reviewed manually.")
    else:
        print("   ✓ No over-mapped departmental heads found")
    
    # 4. FINAL SUMMARY
    print("\n" + "=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)
    
    total_after = BudgetHead.objects.count()
    universal_count = GlobalHead.objects.filter(scope='UNIVERSAL').count()
    dept_count = GlobalHead.objects.filter(scope='DEPARTMENTAL').count()
    
    print(f"\nTotal BudgetHeads:")
    print(f"   Before: {total_budget_heads}")
    print(f"   After:  {total_after}")
    print(f"   Change: +{total_after - total_budget_heads}")
    
    print(f"\nGlobalHead Scope Distribution:")
    print(f"   UNIVERSAL:    {universal_count} heads")
    print(f"   DEPARTMENTAL: {dept_count} heads")
    
    print(f"\nFunction Coverage Check:")
    for func in all_functions[:5]:
        head_count = BudgetHead.objects.filter(function=func).count()
        print(f"   {func.code:<10} : {head_count} budget heads")
    
    print("\n" + "=" * 100)
    print("MAPPING FIX COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    with transaction.atomic():
        try:
            main()
            print("\n✓ All changes committed successfully!")
        except Exception as e:
            print(f"\n✗ Error occurred: {e}")
            print("   Transaction rolled back")
            raise
