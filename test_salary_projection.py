#!/usr/bin/env python
"""Test the new salary increase projection feature"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.models import BPSSalaryScale
from decimal import Decimal

print("\n" + "=" * 80)
print("Testing Salary Increase Projection Feature")
print("=" * 80)

# Get BPS 7 salary scale
scale = BPSSalaryScale.objects.filter(bps_grade=7).first()
if not scale:
    print("ERROR: BPS 7 scale not found!")
    exit(1)

# Test Case 1: Without increase percentage
print("\n[TEST 1] Current Year (No Increase)")
print("-" * 80)

emp = BudgetEmployee(
    name="Ali Ahmed",
    bps=7,
    running_basic=Decimal('35000.00'),
    frozen_ara_2022_input=Decimal('1500.00'),
    city_category='LARGE',
    dra_amount=Decimal('500.00'),
    expected_salary_increase_percentage=Decimal('0.00')
)

current_monthly = emp.monthly_gross
current_annual = emp.annual_cost
projected_monthly = emp.get_projected_monthly_gross()
projected_annual = emp.get_projected_annual_cost()

print(f"\nCurrent Monthly Gross:     {current_monthly}")
print(f"Current Annual Cost:       {current_annual}")
print(f"Projected Monthly Gross:   {projected_monthly}")
print(f"Projected Annual Cost:     {projected_annual}")
print(f"\nDifference: {projected_monthly - current_monthly}")

if current_monthly == projected_monthly:
    print("[PASS] Projection matches current (0% increase)")
else:
    print("[FAIL] ERROR: Projection should match current when increase is 0%")

# Test Case 2: With 10% increase
print("\n[TEST 2] Next Year (10% Increase)")
print("-" * 80)

emp2 = BudgetEmployee(
    name="Fatima Khan",
    bps=10,
    running_basic=Decimal('40000.00'),
    frozen_ara_2022_input=Decimal('2000.00'),
    city_category='OTHER',
    dra_amount=Decimal('600.00'),
    expected_salary_increase_percentage=Decimal('10.00')
)

current_monthly_2 = emp2.monthly_gross
current_annual_2 = emp2.annual_cost
projected_monthly_2 = emp2.get_projected_monthly_gross()
projected_annual_2 = emp2.get_projected_annual_cost()

print(f"\nCurrent Monthly Gross:     {current_monthly_2}")
print(f"Current Annual Cost:       {current_annual_2}")
print(f"Projected Monthly Gross:   {projected_monthly_2}")
print(f"Projected Annual Cost:     {projected_annual_2}")

# The increase should be on running basic × 10%, which affects ARA components
# Fixed components (HRA, Conv, Medical, DRA, ARA 2022) stay the same
running_basic_increase = emp2.running_basic * Decimal('0.10')
print(f"\nRunning Basic Increase:    {running_basic_increase}")
print(f"This affects ARA 2023-2025 calculations")

# ARA components that change based on running basic
current_ara_2023 = emp2.get_ara_2023()
current_ara_2024 = emp2.get_ara_2024()
current_ara_2025 = emp2.get_ara_2025()
current_ara_2023_2024_2025 = current_ara_2023 + current_ara_2024 + current_ara_2025

# Projected ARA components
projected_basic = emp2.running_basic * Decimal('1.10')
projected_ara_2023 = projected_basic * (Decimal('0.35') if emp2.bps <= 16 else Decimal('0.30'))
projected_ara_2024 = projected_basic * (Decimal('0.25') if emp2.bps <= 16 else Decimal('0.20'))
projected_ara_2025 = projected_basic * Decimal('0.10')
projected_ara_2023_2024_2025 = projected_ara_2023 + projected_ara_2024 + projected_ara_2025

ara_increase = projected_ara_2023_2024_2025 - current_ara_2023_2024_2025
print(f"ARA 2023-2025 increase:    {ara_increase:.2f}")
print(f"Total increase (ARA only): {ara_increase:.2f}")

increase_amount = projected_monthly_2 - current_monthly_2
# Total increase = running basic increase + ARA increase
# Running basic: 4000, ARA: 2800 = Total: 6800
expected_total_increase = running_basic_increase + ara_increase
print(f"Expected total increase:   {expected_total_increase}")
if abs(increase_amount - expected_total_increase) < Decimal('1'):
    print("[PASS] Projection correctly applies salary increase (running basic + ARA recalc)")
else:
    print(f"[FAIL] Mismatch: {increase_amount} vs {expected_total_increase}")

# Test Case 3: Higher increase (25%)
print("\n[TEST 3] Senior Officer (25% Increase)")
print("-" * 80)

emp3 = BudgetEmployee(
    name="Muhammad Hassan",
    bps=20,
    running_basic=Decimal('75000.00'),
    frozen_ara_2022_input=Decimal('5000.00'),
    city_category='LARGE',
    dra_amount=Decimal('1000.00'),
    expected_salary_increase_percentage=Decimal('25.00')
)

current_monthly_3 = emp3.monthly_gross
current_annual_3 = emp3.annual_cost
projected_monthly_3 = emp3.get_projected_monthly_gross()
projected_annual_3 = emp3.get_projected_annual_cost()

print(f"\nCurrent Monthly Gross:     {current_monthly_3}")
print(f"Current Annual Cost:       {current_annual_3}")
print(f"Projected Monthly Gross:   {projected_monthly_3}")
print(f"Projected Annual Cost:     {projected_annual_3}")

# Similar to Test 2: increase affects running basic and thus ARA components
running_basic_increase_3 = emp3.running_basic * Decimal('0.25')
print(f"\nRunning Basic Increase:    {running_basic_increase_3}")

# Current ARA 2023-2025
current_ara_2023_3 = emp3.get_ara_2023()
current_ara_2024_3 = emp3.get_ara_2024()
current_ara_2025_3 = emp3.get_ara_2025()
current_ara_total_3 = current_ara_2023_3 + current_ara_2024_3 + current_ara_2025_3

# Projected ARA 2023-2025 (with 25% increase to running basic)
proj_basic_3 = emp3.running_basic * Decimal('1.25')
proj_ara_2023_3 = proj_basic_3 * (Decimal('0.35') if emp3.bps <= 16 else Decimal('0.30'))
proj_ara_2024_3 = proj_basic_3 * (Decimal('0.25') if emp3.bps <= 16 else Decimal('0.20'))
proj_ara_2025_3 = proj_basic_3 * Decimal('0.10')
proj_ara_total_3 = proj_ara_2023_3 + proj_ara_2024_3 + proj_ara_2025_3

ara_increase_3 = proj_ara_total_3 - current_ara_total_3
print(f"ARA 2023-2025 increase:    {ara_increase_3:.2f}")

increase_3 = projected_monthly_3 - current_monthly_3
# Total increase = running basic increase + ARA increase
expected_increase_3 = running_basic_increase_3 + ara_increase_3
if abs(increase_3 - expected_increase_3) < Decimal('1'):
    print("[PASS] Projection correctly applies salary increase (running basic + ARA recalc)")

# Verify annual projections
if abs(projected_annual_2 - (projected_monthly_2 * 12)) < Decimal('1'):
    print("\n[PASS] Annual projections correctly calculated (monthly × 12)")
else:
    print("\n[FAIL] ERROR: Annual projection calculation mismatch")

print("\n" + "=" * 80)
print("Salary Increase Projection Tests Complete!")
print("=" * 80 + "\n")
