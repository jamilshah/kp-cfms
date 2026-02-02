#!/usr/bin/env python
"""
Simulate the AJAX request to load_budget_heads endpoint.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, AccountType
from apps.budgeting.models import Department

def simulate_load_budget_heads(department_code):
    """Simulate what the load_budget_heads AJAX endpoint returns."""
    
    print(f"\n{'=' * 100}")
    print(f"SIMULATING: GET /expenditure/ajax/load-budget-heads/?department=<{department_code}_id>")
    print(f"{'=' * 100}")
    
    try:
        dept = Department.objects.get(code=department_code)
        print(f"\nDepartment: {dept.code} - {dept.name}")
        print(f"ID: {dept.id}")
        
        # This is what the endpoint does
        budget_heads = BudgetHead.objects.filter(
            global_head__account_type=AccountType.EXPENDITURE,
            posting_allowed=True,
            is_active=True,
            function__in=dept.related_functions.all()
        ).exclude(
            global_head__code__startswith='A01'
        ).select_related('global_head', 'function').order_by('global_head__code', 'function__code')
        
        print(f"\nTotal Budget Heads Returned: {budget_heads.count()}")
        print(f"\nFunctions Included:")
        for func in dept.related_functions.all():
            count = budget_heads.filter(function=func).count()
            print(f"   {func.code} - {func.name}: {count} heads")
        
        print(f"\nSample Budget Heads (first 10):")
        for bh in budget_heads[:10]:
            print(f"   <option value=\"{bh.id}\">{bh.code} - {bh.name}</option>")
        
        print(f"\n{'=' * 100}\n")
        
    except Department.DoesNotExist:
        print(f"✗ Department with code '{department_code}' not found")

if __name__ == '__main__':
    # Test all departments
    departments = ['ADMN', 'FIN', 'REG', 'ENGR', 'CNCL']
    
    for dept_code in departments:
        simulate_load_budget_heads(dept_code)
