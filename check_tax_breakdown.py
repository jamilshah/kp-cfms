"""
Check all tax entries for TMA ID 2 to explain the 5185 total
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, JournalEntry
from apps.core.models import Organization

print("=" * 80)
print("Tax Entries Breakdown for TMA ID 2")
print("=" * 80)

org = Organization.objects.get(id=2)
print(f"\nOrganization: {org.name}")

# Get the FDEV G01204 BudgetHead
bh = BudgetHead.objects.get(id=4633)  # FDEV-011101-G01204

print(f"\nBudgetHead: {bh.get_full_code()}")

# Get all posted journal entries
entries = JournalEntry.objects.filter(
    budget_head=bh,
    voucher__is_posted=True,
    voucher__organization=org
).select_related('voucher').order_by('voucher__date', 'id')

print(f"\nTotal Posted Entries: {entries.count()}")

total_dr = 0
total_cr = 0

print(f"\nAll Entries:")
for entry in entries:
    total_dr += entry.debit
    total_cr += entry.credit
    print(f"\n  {entry.voucher.voucher_no} - {entry.voucher.date}")
    print(f"    Dr: {entry.debit}, Cr: {entry.credit}")
    print(f"    Description: {entry.description}")

print(f"\n{'='*80}")
print(f"TOTALS:")
print(f"  Total Debit: {total_dr}")
print(f"  Total Credit: {total_cr}")
print(f"  Net Balance: {total_cr - total_dr}")
print("=" * 80)

# Breakdown by amount
from collections import defaultdict
by_amount = defaultdict(list)

for entry in entries:
    if entry.credit > 0:
        by_amount[entry.credit].append(entry)

print(f"\nBreakdown by Tax Amount:")
for amount, ents in sorted(by_amount.items()):
    print(f"  {amount}: {len(ents)} entries = {amount * len(ents)}")

print("\n" + "=" * 80)
