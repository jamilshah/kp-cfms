#!/usr/bin/env python
"""Check budget heads with posting_allowed=True"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead
from django.db.models import Count

print("Total budget heads with posting_allowed=True:", 
      BudgetHead.objects.filter(posting_allowed=True, is_active=True).count())

print("\nBy account_type (via global_head):")
for item in BudgetHead.objects.filter(posting_allowed=True, is_active=True).values('global_head__account_type').annotate(count=Count('id')).order_by('global_head__account_type'):
    print(f"  {item['global_head__account_type']}: {item['count']}")

# Check if H01105 exists
h01105 = BudgetHead.objects.filter(global_head__code='H01105').first()
if h01105:
    print(f"\nH01105 found: {h01105}")
    print(f"  posting_allowed: {h01105.posting_allowed}")
    print(f"  is_active: {h01105.is_active}")
    print(f"  account_type: {h01105.global_head.account_type}")
else:
    print("\nH01105 NOT FOUND in database")
    
# Search for Retained Earnings
retained = BudgetHead.objects.filter(global_head__name__icontains='retained').first()
if retained:
    print(f"\nRetained Earnings found: {retained}")
    print(f"  Code: {retained.global_head.code}")
    print(f"  posting_allowed: {retained.posting_allowed}")
    print(f"  is_active: {retained.is_active}")
else:
    print("\nRetained Earnings NOT FOUND")
