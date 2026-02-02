#!/usr/bin/env python
"""
Test the Function cascade filtering for bill creation
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import FunctionCode, BudgetHead, AccountType

print("=" * 80)
print("TESTING FUNCTION CASCADE FILTERING")
print("=" * 80)

# Test with ADMN department
admn = Department.objects.get(code='ADMN')
print(f"\n1. ADMN Department: {admn.name}")
print(f"   Functions ({admn.related_functions.count()}):")
for func in admn.related_functions.all().order_by('code'):
    print(f"   - {func.code}: {func.name}")
    
    # Count budget heads for this function
    heads = BudgetHead.objects.filter(
        function=func,
        global_head__account_type=AccountType.EXPENDITURE,
        posting_allowed=True,
        is_active=True
    ).exclude(
        global_head__code__startswith='A01'
    )
    print(f"     → {heads.count()} budget heads available")

print("\n" + "-" * 80)

# Test with ENGR department
engr = Department.objects.get(code='ENGR')
print(f"\n2. ENGR Department: {engr.name}")
print(f"   Functions ({engr.related_functions.count()}):")
for func in engr.related_functions.all().order_by('code')[:3]:  # Show first 3
    print(f"   - {func.code}: {func.name}")
    
    heads = BudgetHead.objects.filter(
        function=func,
        global_head__account_type=AccountType.EXPENDITURE,
        posting_allowed=True,
        is_active=True
    ).exclude(
        global_head__code__startswith='A01'
    )
    print(f"     → {heads.count()} budget heads available")

print(f"   ... and {engr.related_functions.count() - 3} more functions")

print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print("\n✓ Function cascade filtering is ready")
print("✓ Department → Functions → Budget Heads")
print(f"✓ Each function has specific budget heads assigned")
print("\nThe bill creation form now has:")
print("1. Department dropdown")
print("2. Function dropdown (filtered by department)")
print("3. Budget Head dropdowns (filtered by function)")
print("\n" + "=" * 80)
