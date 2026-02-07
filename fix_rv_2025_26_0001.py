"""
Fix the incorrect Receipt Voucher entry RV-2025-26-0001

The voucher currently credits C03880 (Revenue) instead of F01603 (AR).
This script corrects the journal entry to credit Accounts Receivable.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import Voucher, JournalEntry, BudgetHead
from decimal import Decimal

print("=" * 80)
print("Fixing Receipt Voucher RV-2025-26-0001")
print("=" * 80)

# Find the voucher(s)
vouchers = Voucher.objects.filter(voucher_no='RV-2025-26-0001')
print(f"\n✓ Found {vouchers.count()} voucher(s) with number RV-2025-26-0001")

if vouchers.count() == 0:
    print("\n✗ ERROR: Voucher RV-2025-26-0001 not found!")
    exit(1)

# If multiple vouchers, show them all
if vouchers.count() > 1:
    print("\n⚠ Multiple vouchers found with the same number:")
    for i, v in enumerate(vouchers, 1):
        print(f"\n  {i}. ID: {v.id}, Date: {v.date}, Posted: {v.is_posted}")
        print(f"     Description: {v.description}")
        entries = v.entries.all()
        for entry in entries:
            print(f"       {entry.budget_head.global_head.code}: Dr {entry.debit}, Cr {entry.credit}")

# Get the correct AR budget head
ar_head = BudgetHead.objects.filter(
    global_head__system_code='AR'
).first()

if not ar_head:
    print("\n✗ ERROR: Accounts Receivable (AR) system head not configured!")
    print("  Run: python manage.py seed_revenue")
    exit(1)

print(f"\n✓ Found correct AR head: {ar_head.code}")
print(f"  Name: {ar_head.name}")

# Find all incorrect entries across all RV vouchers
print("\n" + "=" * 80)
print("ANALYZING ALL RV-2025-26-0001 VOUCHERS:")
print("=" * 80)

vouchers_to_fix = []
for v in vouchers:
    print(f"\nVoucher ID {v.id} (Date: {v.date}):")
    entries = v.entries.all()
    incorrect_entry = None
    
    for entry in entries:
        if entry.credit > 0 and entry.budget_head.global_head.code == 'C03880':
            incorrect_entry = entry
            print(f"  ✗ HAS INCORRECT ENTRY: Cr {entry.budget_head.code} (C03880) = {entry.credit}")
            break
    
    if incorrect_entry:
        vouchers_to_fix.append((v, incorrect_entry))
    else:
        print(f"  ✓ Already correct or no C03880 credit found")

if not vouchers_to_fix:
    print("\n✓ No vouchers need fixing. All are correct!")
    exit(0)

print(f"\n{'=' * 80}")
print(f"SUMMARY: {len(vouchers_to_fix)} voucher(s) need fixing")
print("=" * 80)

response = input(f"\nProceed with fixing {len(vouchers_to_fix)} voucher(s)? (yes/no): ")
if response.lower() != 'yes':
    print("\n✗ Cancelled by user.")
    exit(0)

# Apply the fixes
print(f"\nApplying fixes...")
fixed_count = 0

for voucher, incorrect_entry in vouchers_to_fix:
    print(f"\nFixing Voucher ID {voucher.id} ({voucher.voucher_no}, Date: {voucher.date})...")
    
    # Get payer name from description for updated AR description
    payer_name = voucher.description.split(' - ')[-1] if ' - ' in voucher.description else 'Customer'
    
    incorrect_entry.budget_head = ar_head
    incorrect_entry.description = f"AR - {payer_name}"
    incorrect_entry.save()
    
    print(f"  ✓ Fixed! Credit entry now uses {ar_head.code} (Accounts Receivable)")
    fixed_count += 1

print(f"\n{'=' * 80}")
print(f"✓ Fixed {fixed_count} voucher(s) successfully!")
print("=" * 80)

# Verification
print("\nVERIFICATION:")
print("=" * 80)
for voucher, _ in vouchers_to_fix:
    print(f"\nVoucher ID {voucher.id} ({voucher.voucher_no}, Date: {voucher.date}):")
    entries = voucher.entries.all().select_related('budget_head', 'budget_head__global_head')
    for entry in entries:
        print(f"  {entry.budget_head.code} ({entry.budget_head.global_head.code}): Dr {entry.debit}, Cr {entry.credit}")
        print(f"    Description: {entry.description}")

print("\n✓ Fix completed successfully!")
print("\nIMPACT:")
print("  - Revenue (C03880) will no longer be double-counted")
print("  - Accounts Receivable (F01603/AR) will be properly cleared")
print("  - General Ledger balances should now be correct")
print("=" * 80)
