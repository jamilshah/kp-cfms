#!/usr/bin/env python
"""Check BudgetHead department/function data integrity."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead

print('=== Budget Heads with Department/Function ===')
print(f'Total Budget Heads: {BudgetHead.objects.count()}')
print(f'With Department: {BudgetHead.objects.filter(department__isnull=False).count()}')
print(f'With Function: {BudgetHead.objects.filter(function__isnull=False).count()}')
print(f'With Both: {BudgetHead.objects.filter(department__isnull=False, function__isnull=False).count()}')
print(f'Active & Posting Allowed: {BudgetHead.objects.filter(posting_allowed=True, is_active=True).count()}')

print('\n=== Sample Active Budget Heads ===')
for bh in BudgetHead.objects.select_related('department', 'function', 'global_head').filter(posting_allowed=True, is_active=True)[:10]:
    dept_name = bh.department.name if bh.department else 'None'
    func_code = bh.function.code if bh.function else 'None'
    print(f'{bh.id}: Dept={bh.department_id} ({dept_name}), Func={bh.function_id} ({func_code}), Head={bh.global_head.code}')

print('\n=== Budget Heads by Department (Active only) ===')
from django.db.models import Count
dept_counts = BudgetHead.objects.filter(
    posting_allowed=True, 
    is_active=True,
    department__isnull=False
).values('department__name').annotate(count=Count('id')).order_by('-count')[:10]
for item in dept_counts:
    print(f"  {item['department__name']}: {item['count']} budget heads")

print('\n=== Budget Heads by Function (Active only) ===')
func_counts = BudgetHead.objects.filter(
    posting_allowed=True, 
    is_active=True,
    function__isnull=False
).values('function__code', 'function__name').annotate(count=Count('id')).order_by('-count')[:10]
for item in func_counts:
    print(f"  {item['function__code']} - {item['function__name']}: {item['count']} budget heads")

print('\n=== Test Filter: Department=1, Function=13 ===')
test_bhs = BudgetHead.objects.filter(
    posting_allowed=True,
    is_active=True,
    department_id=1,
    function_id=13
).select_related('global_head')[:20]
print(f'Found {test_bhs.count()} budget heads')
for bh in test_bhs:
    print(f'  {bh.global_head.code} - {bh.global_head.name}')
