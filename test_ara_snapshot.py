#!/usr/bin/env python
"""Test the new Opening Balance snapshot ARA calculation"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.models import BPSSalaryScale
from decimal import Decimal

print("=" * 80)
print("Testing Opening Balance Snapshot ARA Calculation")
print("=" * 80)

# Get BPS 7 salary scale
scale = BPSSalaryScale.objects.filter(bps_grade=7).first()
if not scale:
    print("ERROR: BPS 7 scale not found! Please run populate_bps_grades.py first.")
    exit(1)

print(f"\nBPS 7 Salary Scale (Reference):")
print(f"  Min Basic: {scale.basic_pay_min}")
print(f"  Max Basic: {scale.basic_pay_max}")
print(f"  Annual Increment: {scale.annual_increment}")

# Test Case 1: With Frozen ARA 2022
print("\n" + "-" * 80)
print("TEST CASE 1: Employee with Frozen ARA 2022 (from last pay slip)")
print("-" * 80)

running_basic = Decimal('30773.00')
frozen_ara_2022 = Decimal('1000.00')

emp = BudgetEmployee(
    name="Test Employee 1",
    father_name="Father",
    bps=7,
    running_basic=running_basic,
    frozen_ara_2022_input=frozen_ara_2022,
    city_category='OTHER'
)

print(f"\nInput Data:")
print(f"  Name: {emp.name}")
print(f"  BPS: {emp.bps}")
print(f"  Running Basic (from pay slip): {emp.running_basic}")
print(f"  Frozen ARA 2022 (from pay slip): {emp.frozen_ara_2022_input}")

ara_2022 = emp.get_ara_2022()
ara_2023 = emp.get_ara_2023()
ara_2024 = emp.get_ara_2024()
ara_2025 = emp.get_ara_2025()
ara_total = emp.get_ara_total()

print(f"\nARA Calculations:")
print(f"  ARA 2022: {ara_2022} (from frozen input)")
print(f"  ARA 2023: {ara_2023} (35% of {running_basic} for BPS 1-16)")
print(f"  ARA 2024: {ara_2024} (25% of {running_basic} for BPS 1-16)")
print(f"  ARA 2025: {ara_2025} (10% of {running_basic} for all BPS)")
print(f"  Total ARA (2022-2025): {ara_total}")

# Test Case 2: Without Frozen ARA 2022 (new entrant - should auto-calculate)
print("\n" + "-" * 80)
print("TEST CASE 2: New Entrant (No Frozen ARA 2022 - Auto-Calculate)")
print("-" * 80)

emp2 = BudgetEmployee(
    name="Test Employee 2 (New Entrant)",
    father_name="Father",
    bps=7,
    running_basic=Decimal('20000.00'),
    frozen_ara_2022_input=None,  # Not provided
    city_category='LARGE'
)

print(f"\nInput Data:")
print(f"  Name: {emp2.name}")
print(f"  BPS: {emp2.bps}")
print(f"  Running Basic: {emp2.running_basic}")
print(f"  Frozen ARA 2022: {emp2.frozen_ara_2022_input} (NULL - will auto-calculate)")

ara_2022_auto = emp2.get_ara_2022()
ara_2023_auto = emp2.get_ara_2023()
ara_2024_auto = emp2.get_ara_2024()
ara_2025_auto = emp2.get_ara_2025()
ara_total_auto = emp2.get_ara_total()

print(f"\nARA Calculations (Auto-Calculated):")
print(f"  ARA 2022: {ara_2022_auto} (auto-calc as 15% of {scale.basic_pay_min})")
print(f"  ARA 2023: {ara_2023_auto} (35% of {Decimal('20000.00')} for BPS 1-16)")
print(f"  ARA 2024: {ara_2024_auto} (25% of {Decimal('20000.00')} for BPS 1-16)")
print(f"  ARA 2025: {ara_2025_auto} (10% of {Decimal('20000.00')} for all BPS)")
print(f"  Total ARA (2022-2025): {ara_total_auto}")

# Test Case 3: BPS 20 (Higher BPS with different percentages)
print("\n" + "-" * 80)
print("TEST CASE 3: Higher BPS (BPS 20 - Different ARA Percentages)")
print("-" * 80)

scale_20 = BPSSalaryScale.objects.filter(bps_grade=20).first()
if scale_20:
    emp3 = BudgetEmployee(
        name="Senior Officer BPS 20",
        father_name="Father",
        bps=20,
        running_basic=Decimal('80000.00'),
        frozen_ara_2022_input=Decimal('5000.00'),
        city_category='LARGE'
    )

    print(f"\nInput Data:")
    print(f"  Name: {emp3.name}")
    print(f"  BPS: {emp3.bps}")
    print(f"  Running Basic: {emp3.running_basic}")
    print(f"  Frozen ARA 2022: {emp3.frozen_ara_2022_input}")

    ara_2022_20 = emp3.get_ara_2022()
    ara_2023_20 = emp3.get_ara_2023()  # Should be 30% (not 35%) for BPS 17-22
    ara_2024_20 = emp3.get_ara_2024()  # Should be 20% (not 25%) for BPS 17-22
    ara_2025_20 = emp3.get_ara_2025()  # Should be 10% for all
    ara_total_20 = emp3.get_ara_total()

    print(f"\nARA Calculations (BPS 17-22 Rates):")
    print(f"  ARA 2022: {ara_2022_20} (frozen)")
    print(f"  ARA 2023: {ara_2023_20} (30% of {Decimal('80000.00')} for BPS 17-22)")
    print(f"  ARA 2024: {ara_2024_20} (20% of {Decimal('80000.00')} for BPS 17-22)")
    print(f"  ARA 2025: {ara_2025_20} (10% of {Decimal('80000.00')} for all BPS)")
    print(f"  Total ARA (2022-2025): {ara_total_20}")

    # Verify correct percentages
    expected_2023_20 = Decimal('80000.00') * Decimal('0.30')
    expected_2024_20 = Decimal('80000.00') * Decimal('0.20')
    print(f"\nVerification:")
    print(f"  2023 Expected: {expected_2023_20}, Got: {ara_2023_20}, ✓ MATCH" if ara_2023_20 == expected_2023_20 else f"  2023 Expected: {expected_2023_20}, Got: {ara_2023_20}, ✗ MISMATCH")
    print(f"  2024 Expected: {expected_2024_20}, Got: {ara_2024_20}, ✓ MATCH" if ara_2024_20 == expected_2024_20 else f"  2024 Expected: {expected_2024_20}, Got: {ara_2024_20}, ✗ MISMATCH")

print("\n" + "=" * 80)
print("Opening Balance Snapshot ARA Tests Complete!")
print("=" * 80)
