#!/usr/bin/env python
"""Test the budget head search API with function filtering"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, FunctionCode

# Get a sample function
function = FunctionCode.objects.filter(code='015101').first()

if not function:
    print("Function 015101 not found")
    function = FunctionCode.objects.first()
    
print(f"Testing with function: {function}")
print(f"Function ID: {function.id}")

# Count budget heads for this function
budget_heads = BudgetHead.objects.filter(
    function=function,
    posting_allowed=True,
    is_active=True
).select_related('global_head')

print(f"\nBudget heads for this function: {budget_heads.count()}")

# Show H01105 for this function
h01105 = budget_heads.filter(global_head__code='H01105').first()
if h01105:
    print(f"\n✓ H01105 found for this function: {h01105}")
else:
    print("\n✗ H01105 NOT found for this function")
    
# Show a few examples
print(f"\nFirst 10 budget heads for function {function.code}:")
for bh in budget_heads[:10]:
    print(f"  - {bh.global_head.code} - {bh.global_head.name} ({bh.global_head.account_type})")
