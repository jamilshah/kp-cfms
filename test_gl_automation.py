import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead
from apps.budgeting.models import FiscalYear
from apps.core.models import TMA
from apps.users.models import CustomUser

print("=" * 80)
print("TESTING GL AUTOMATION - SYSTEM CODE LOOKUP")
print("=" * 80)

# Test 1: Can we find AP head?
print("\n[TEST 1] Looking up Accounts Payable (AP)...")
ap_head = BudgetHead.objects.filter(
    global_head__system_code='AP',
    is_active=True
).first()

if ap_head:
    print(f"  [OK] Found AP: {ap_head.global_head.code} - {ap_head.global_head.name}")
    print(f"       Fund: {ap_head.fund.code}, Function: {ap_head.function.code}")
else:
    print("  [FAIL] AP head not found!")

# Test 2: Can we find AR head?
print("\n[TEST 2] Looking up Accounts Receivable (AR)...")
ar_head = BudgetHead.objects.filter(
    global_head__system_code='AR',
    is_active=True
).first()

if ar_head:
    print(f"  [OK] Found AR: {ar_head.global_head.code} - {ar_head.global_head.name}")
    print(f"       Fund: {ar_head.fund.code}, Function: {ar_head.function.code}")
else:
    print("  [FAIL] AR head not found!")

# Test 3: Can we find TAX_IT head?
print("\n[TEST 3] Looking up Income Tax (TAX_IT)...")
tax_it_head = BudgetHead.objects.filter(
    global_head__system_code='TAX_IT',
    is_active=True
).first()

if tax_it_head:
    print(f"  [OK] Found TAX_IT: {tax_it_head.global_head.code} - {tax_it_head.global_head.name}")
    print(f"       Fund: {tax_it_head.fund.code}, Function: {tax_it_head.function.code}")
else:
    print("  [FAIL] TAX_IT head not found!")

# Test 4: Can we find TAX_GST head?
print("\n[TEST 4] Looking up Sales Tax (TAX_GST)...")
tax_gst_head = BudgetHead.objects.filter(
    global_head__system_code='TAX_GST',
    is_active=True
).first()

if tax_gst_head:
    print(f"  [OK] Found TAX_GST: {tax_gst_head.global_head.code} - {tax_gst_head.global_head.name}")
    print(f"       Fund: {tax_gst_head.fund.code}, Function: {tax_gst_head.function.code}")
else:
    print("  [FAIL] TAX_GST head not found!")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

all_passed = all([ap_head, ar_head, tax_it_head, tax_gst_head])

if all_passed:
    print("[OK] All critical system codes are configured!")
    print("\nGL Automation is ready for:")
    print("  - Bill.approve() will use AP and TAX_IT/TAX_GST")
    print("  - RevenueDemand.post() will use AR")
    print("  - Payment.post() will use AP")
    print("  - RevenueCollection.post() will use AR")
else:
    print("[FAIL] Some system codes are missing!")

print("=" * 80)
