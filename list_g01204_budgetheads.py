"""
Find all BudgetHeads with GlobalHead code G01204
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead

print("=" * 80)
print("All BudgetHeads with GlobalHead G01204")
print("=" * 80)

# Find the GlobalHead
try:
    global_head = GlobalHead.objects.get(code='G01204')
    print(f"\nGlobalHead: {global_head.code} - {global_head.name}")
    
    # Find all BudgetHeads using this GlobalHead
    budget_heads = BudgetHead.objects.filter(
        global_head=global_head
    ).select_related('fund', 'function')
    
    print(f"\nTotal BudgetHeads: {budget_heads.count()}")
    
    for bh in budget_heads:
        print(f"\n  ID {bh.id}: {bh.get_full_code()}")
        print(f"    Fund: {bh.fund.code} - {bh.fund.name}")
        print(f"    Function: {bh.function.code} - {bh.function.name}")
        print(f"    Active: {bh.is_active}")
        print(f"    Sub-code: {bh.sub_code}")
        
except GlobalHead.DoesNotExist:
    print("\nGlobalHead G01204 not found!")

print("\n" + "=" * 80)
