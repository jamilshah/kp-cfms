#!/usr/bin/env python
"""Create H01105-Retained Earnings budget head for opening balances"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead, FunctionCode, Fund, MinorHead, MajorHead
from django.db import transaction

print("="*70)
print("Creating H01105 - Retained Earnings")
print("="*70)

# First, check what MinorHeads exist
print("\nExisting MinorHeads:")
minors = MinorHead.objects.all().order_by('code')[:10]
for m in minors:
    print(f"  {m.code} - {m.name}")

# Find a suitable MinorHead for H-series (Liabilities)
# Typically H01 would be Capital/Equity
minor_h01 = MinorHead.objects.filter(code='H01').first()

if not minor_h01:
    print("\n✗ MinorHead H01 not found. Searching for H-series minor heads...")
    # Try to find any H-series minor head
    h_minors = MinorHead.objects.filter(code__startswith='H').order_by('code')
    if h_minors.exists():
        minor_h01 = h_minors.first()
        print(f"✓ Using existing MinorHead: {minor_h01}")
    else:
        # Need to create it - but first we need the MajorHead
        major_h = MajorHead.objects.filter(code='H').first()
        if not major_h:
            print("✗ MajorHead H not found. Creating it...")
            major_h = MajorHead.objects.create(
                code='H',
                name='Liabilities'
            )
            print(f"✓ Created MajorHead: {major_h}")
        
        minor_h01 = MinorHead.objects.create(
            code='H01',
            name='Capital Account',
            major=major_h
        )
        print(f"✓ Created MinorHead: {minor_h01}")
else:
    print(f"✓ Found MinorHead: {minor_h01}")

# Create GlobalHead H01105
with transaction.atomic():
    global_head, created = GlobalHead.objects.get_or_create(
        code='H01105',
        defaults={
            'name': 'Retained Earnings',
            'account_type': 'LIA',
            'minor': minor_h01,
            'scope': 'UNIVERSAL'
        }
    )
    
    if created:
        print(f"\n✓ Created GlobalHead: {global_head}")
    else:
        print(f"\n✓ GlobalHead already exists: {global_head}")
    
    # Now create BudgetHead for each function
    functions = FunctionCode.objects.filter(is_active=True)
    fund = Fund.objects.first()  # Use the first fund
    
    if not fund:
        print("✗ No fund found. Please create a fund first.")
        exit(1)
    
    print(f"\n✓ Using Fund: {fund}")
    print(f"\nCreating BudgetHeads for {functions.count()} functions...")
    
    created_count = 0
    existing_count = 0
    
    for function in functions:
        budget_head, bh_created = BudgetHead.objects.get_or_create(
            global_head=global_head,
            function=function,
            fund=fund,
            defaults={
                'posting_allowed': True,
                'is_active': True,
                'head_type': 'universal'
            }
        )
        
        if bh_created:
            created_count += 1
            if created_count <= 5:  # Show first 5
                print(f"  ✓ Created: {budget_head}")
        else:
            existing_count += 1
    
    print(f"\n✓ Created {created_count} new BudgetHeads")
    print(f"✓ Found {existing_count} existing BudgetHeads")
    print(f"\nTotal H01105 BudgetHeads: {BudgetHead.objects.filter(global_head=global_head).count()}")

print("\n" + "="*70)
print("DONE! H01105-Retained Earnings is now available for voucher creation.")
print("="*70)
print("\nYou can now:")
print("1. Go to the voucher creation form")
print("2. Search for 'H01105' or 'Retained Earnings' in the budget head dropdown")
print("3. Create your opening balance journal entry")
