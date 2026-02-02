#!/usr/bin/env python
"""Check and optionally create H01105-Retained Earnings budget head"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead, Fund, FunctionCode

# Check if H01105 exists in GlobalHead
h01105_global = GlobalHead.objects.filter(code='H01105').first()

if h01105_global:
    print(f"✓ GlobalHead H01105 found: {h01105_global}")
    print(f"  Account Type: {h01105_global.account_type}")
    print(f"  Name: {h01105_global.name}")
    
    # Check if there are BudgetHeads for this GlobalHead
    budget_heads = BudgetHead.objects.filter(global_head=h01105_global)
    print(f"\n  Budget Heads: {budget_heads.count()}")
    for bh in budget_heads:
        print(f"    - {bh} (Function: {bh.function}, Posting: {bh.posting_allowed})")
else:
    print("✗ GlobalHead H01105 NOT FOUND")
    print("\nSearching for similar codes...")
    similar = GlobalHead.objects.filter(code__startswith='H011').order_by('code')[:10]
    for gh in similar:
        print(f"  {gh.code} - {gh.name} ({gh.account_type})")
    
    print("\nSearching for 'Retained Earnings'...")
    retained = GlobalHead.objects.filter(name__icontains='retained').first()
    if retained:
        print(f"  Found: {retained.code} - {retained.name}")
    else:
        print("  NOT FOUND")
        
    print("\n" + "="*60)
    print("RECOMMENDATION:")
    print("="*60)
    print("H01105-Retained Earnings should be created in the GlobalHead table.")
    print("This is a Liability account used for opening balance adjustments.")
    print("\nTo create it, you need to:")
    print("1. Insert into GlobalHead table with:")
    print("   - code: H01105")
    print("   - name: Retained Earnings")
    print("   - account_type: LIA (Liability)")
    print("   - minor_head: (appropriate minor head for equity/liability)")
    print("\n2. Then create BudgetHead entries for each function that needs it")
    print("   - posting_allowed: True")
    print("   - is_active: True")

# List all Liability accounts for reference
print("\n" + "="*60)
print("EXISTING LIABILITY ACCOUNTS:")
print("="*60)
liability_heads = GlobalHead.objects.filter(account_type='LIA').order_by('code')
for gh in liability_heads:
    print(f"{gh.code} - {gh.name}")
    budget_count = BudgetHead.objects.filter(global_head=gh, posting_allowed=True).count()
    print(f"  (Budget heads with posting: {budget_count})")
