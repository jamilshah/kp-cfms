"""
Check all C03880 variations in the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import GlobalHead, BudgetHead

print("=" * 80)
print("Searching for C03880 and all sub-heads")
print("=" * 80)

# Search in GlobalHead
print("\n[1] GLOBAL HEADS (CoA)")
print("-" * 80)
global_codes = GlobalHead.objects.filter(
    code__startswith='C03880'
).order_by('code')

print(f"Found {global_codes.count()} global CoA codes starting with C03880:\n")
for gc in global_codes:
    print(f"  {gc.code}: {gc.name}")

# Search in BudgetHead
print("\n[2] BUDGET HEADS")
print("-" * 80)
budget_heads = BudgetHead.objects.filter(
    global_head__code__startswith='C03880'
).select_related('global_head', 'function').order_by('global_head__code')

print(f"Found {budget_heads.count()} budget heads with C03880:\n")
for bh in budget_heads:
    print(f"  {bh.code}: {bh.name}")
    print(f"    Global: {bh.global_head.code}")
    print(f"    Function: {bh.function}")
    print(f"    Posting: {bh.posting_allowed} | Active: {bh.is_active}")
    print()

if budget_heads.count() == 0:
    print("⚠️  NO BUDGET HEADS FOUND!")
    print("\nThis means the sub-heads were created in GlobalChartOfAccounts")
    print("but NOT converted to BudgetHeads for the functions.")
    print("\nYou need to create BudgetHead entries for each sub-head + function combination")

print("=" * 80)
