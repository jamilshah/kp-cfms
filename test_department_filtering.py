#!/usr/bin/env python
"""
Test department-based budget head filtering.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, AccountType
from apps.budgeting.models import Department

def main():
    print("=" * 100)
    print("TESTING DEPARTMENT-BASED BUDGET HEAD FILTERING")
    print("=" * 100)
    
    departments = Department.objects.all()
    
    for dept in departments:
        print(f"\n{dept.code} - {dept.name}")
        print("-" * 100)
        
        # Get assigned functions
        functions = dept.related_functions.all()
        print(f"Assigned Functions: {functions.count()}")
        for func in functions:
            print(f"   • {func.code} - {func.name}")
        
        # Get expenditure budget heads for this department
        expenditure_heads = BudgetHead.objects.filter(
            global_head__account_type=AccountType.EXPENDITURE,
            posting_allowed=True,
            is_active=True,
            function__in=functions
        )
        
        print(f"\nExpenditure Budget Heads: {expenditure_heads.count()}")
        
        # Show sample heads
        sample_heads = expenditure_heads.select_related('global_head', 'function')[:5]
        for head in sample_heads:
            print(f"   {head.global_head.code:<10} {head.function.code:<10} {head.global_head.name[:40]}")
        
        # Count by function
        print(f"\nHeads per Function:")
        for func in functions:
            count = expenditure_heads.filter(function=func).count()
            print(f"   {func.code:<10} : {count:>3} heads")
    
    print("\n" + "=" * 100)
    print("TEST COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()
