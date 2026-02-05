"""
Script to investigate duplicate G01204 entries and failed bill approval
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import GlobalHead, BudgetHead, JournalEntry, Voucher, SystemCode
from apps.core.models import Organization
from decimal import Decimal

print("=" * 80)
print("Investigating G01204 Duplicate Entries")
print("=" * 80)

org = Organization.objects.first()
print(f"\nOrganization: {org}")

# Find all BudgetHeads with G01204
g01204_heads = BudgetHead.objects.filter(
    global_head__code='G01204'
).select_related('global_head', 'fund', 'function')

print(f"\n[1] BudgetHeads with code G01204: {g01204_heads.count()}")
for bh in g01204_heads:
    print(f"  - ID {bh.id}: {bh.get_full_code()} - {bh.global_head.name}")
    print(f"    Fund: {bh.fund}, Function: {bh.function}, Active: {bh.is_active}")
    
    # Get balance for this budget head
    from django.db.models import Sum, Q
    from django.db.models.functions import Coalesce
    
    entries = JournalEntry.objects.filter(
        budget_head=bh,
        voucher__is_posted=True,
        voucher__organization=org
    ).aggregate(
        total_debit=Coalesce(Sum('debit'), Decimal('0.00')),
        total_credit=Coalesce(Sum('credit'), Decimal('0.00'))
    )
    
    balance = entries['total_credit'] - entries['total_debit']
    print(f"    Balance: Dr {entries['total_debit']}, Cr {entries['total_credit']}, Net: {balance}")

# Find recent vouchers with G01204 entries
print(f"\n[2] Recent Journal Entries for G01204:")
recent_entries = JournalEntry.objects.filter(
    budget_head__global_head__code='G01204',
    voucher__organization=org
).select_related('voucher', 'budget_head').order_by('-voucher__date', '-id')[:10]

for entry in recent_entries:
    print(f"  - Voucher: {entry.voucher.voucher_no} (Posted: {entry.voucher.is_posted})")
    print(f"    Date: {entry.voucher.date}, Amount: Dr {entry.debit}, Cr {entry.credit}")
    print(f"    BudgetHead: {entry.budget_head.get_full_code()}")
    print(f"    Description: {entry.description}")

# Check for unposted vouchers (failed approvals)
print(f"\n[3] Unposted Vouchers (Failed Approvals):")
unposted = Voucher.objects.filter(
    organization=org,
    is_posted=False
).order_by('-created_at')[:5]

for v in unposted:
    print(f"  - {v.voucher_no}: {v.description[:60]}")
    print(f"    Created: {v.created_at}, Entries: {v.journal_entries.count()}")
    
    # Show entries
    for entry in v.journal_entries.all():
        print(f"      {entry.budget_head.get_full_code()}: Dr {entry.debit}, Cr {entry.credit}")

print("\n" + "=" * 80)
print("ANALYSIS:")
print("  If there are unposted vouchers with journal entries, these are orphaned")
print("  from failed approval attempts and should be deleted.")
print("  If there are multiple BudgetHeads with G01204, you may need to consolidate.")
print("=" * 80)
