#!/usr/bin/env python
"""Check DepartmentFunctionConfiguration for dept=1, func=13."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import DepartmentFunctionConfiguration, BudgetHead

dept_id = 1
func_id = 13

try:
    config = DepartmentFunctionConfiguration.objects.get(
        department_id=dept_id,
        function_id=func_id
    )
    
    print(f"=== Configuration for Department {dept_id}, Function {func_id} ===")
    print(f"Department: {config.department.name}")
    print(f"Function: {config.function.code} - {config.function.name}")
    print(f"Allowed Global Heads: {config.allowed_global_heads.count()}")
    
    print("\n=== Allowed Global Heads (first 20) ===")
    for gh in config.allowed_global_heads.all().order_by('code')[:20]:
        print(f"  {gh.code} - {gh.name}")
    
    print("\n=== Resulting Budget Heads ===")
    budget_heads = BudgetHead.objects.filter(
        posting_allowed=True,
        is_active=True,
        department_id=dept_id,
        function_id=func_id,
        global_head__in=config.allowed_global_heads.all()
    ).select_related('global_head', 'fund')
    
    print(f"Total: {budget_heads.count()} budget heads")
    
    print("\n=== Sample Budget Heads (first 30) ===")
    for bh in budget_heads.order_by('global_head__code')[:30]:
        fund_name = bh.fund.name if bh.fund else 'No Fund'
        print(f"  {bh.global_head.code} - {bh.global_head.name} (Fund: {fund_name}, Sub: {bh.sub_code})")
    
    print("\n=== Budget Heads by Global Head (duplicates?) ===")
    from django.db.models import Count
    duplicates = budget_heads.values('global_head__code', 'global_head__name').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')[:10]
    
    if duplicates:
        print("Global heads with multiple budget head entries:")
        for item in duplicates:
            print(f"  {item['global_head__code']} - {item['global_head__name']}: {item['count']} entries")
            
            # Show what makes them different
            bhs = budget_heads.filter(global_head__code=item['global_head__code'])
            for bh in bhs:
                print(f"    - Fund: {bh.fund.name}, Sub: {bh.sub_code}, ID: {bh.id}")
    else:
        print("No duplicates found - each global head has only one budget head entry")
        
except DepartmentFunctionConfiguration.DoesNotExist:
    print(f"No configuration found for dept={dept_id}, func={func_id}")
