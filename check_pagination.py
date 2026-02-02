#!/usr/bin/env python
"""Check pagination issue with CoA list"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead

heads = BudgetHead.objects.select_related('function', 'global_head').order_by('function__code', 'global_head__code')[:51]

print('First 51 budget heads:')
for i, h in enumerate(heads):
    func_code = h.function.code if h.function else "None"
    print(f'{i+1}. Func: {func_code}, Type: {h.global_head.account_type}, Code: {h.global_head.code}')

print(f'\nTotal count: {BudgetHead.objects.count()}')
print(f'Count by type:')
print(f'  EXP: {BudgetHead.objects.filter(global_head__account_type="EXP").count()}')
print(f'  REV: {BudgetHead.objects.filter(global_head__account_type="REV").count()}')
