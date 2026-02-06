from apps.finance.models import GlobalHead, BudgetHead, SystemCode

print("--- DEBUGGING TAX CONFIGURATION ---")
try:
    gh = GlobalHead.objects.get(code='G01204')
    print(f"GlobalHead: {gh.code} - {gh.name}")
    print(f"SystemCode: {gh.system_code} (Expected: TAX_IT)")
    
    bhs = BudgetHead.objects.filter(global_head=gh)
    print(f"Total BudgetHeads for G01204: {bhs.count()}")
    
    for bh in bhs:
        print(f"  - ID: {bh.id} | Active: {bh.is_active} | Fund: {bh.fund.code} | Func: {bh.function.code}")

    print("\nAttempting the failing query:")
    try:
        res = BudgetHead.objects.get(global_head__system_code='TAX_IT', is_active=True)
        print(f"SUCCESS: Found {res}")
    except Exception as e:
        print(f"FAILED: {e}")

except Exception as e:
    print(f"Global Check Failed: {e}")
