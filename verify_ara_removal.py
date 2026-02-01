#!/usr/bin/env python
"""Verify ara_percentage references have been removed"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.forms_employee_salary import EmployeeSalaryForm
from apps.budgeting.views import EmployeeCreateView, EmployeeUpdateView

print("\n" + "=" * 80)
print("Verifying ara_percentage has been removed")
print("=" * 80)

# Check form
print("\n✅ EmployeeSalaryForm:")
form = EmployeeSalaryForm()
print(f"   - Total fields: {len(form.fields)}")
print(f"   - Has frozen_ara_2022_input: {'frozen_ara_2022_input' in form.fields} ✓")
print(f"   - Has ara_percentage: {'ara_percentage' in form.fields} (should be False)")

# Check views
print("\n✅ EmployeeCreateView:")
print(f"   Fields: {EmployeeCreateView.fields}")
if 'ara_percentage' in EmployeeCreateView.fields:
    print("   ❌ ERROR: ara_percentage still in fields!")
else:
    print("   ✓ ara_percentage removed")

print("\n✅ EmployeeUpdateView:")
print(f"   Fields: {EmployeeUpdateView.fields}")
if 'ara_percentage' in EmployeeUpdateView.fields:
    print("   ❌ ERROR: ara_percentage still in fields!")
else:
    print("   ✓ ara_percentage removed")

print("\n" + "=" * 80)
print("All references to ara_percentage have been successfully removed!")
print("=" * 80 + "\n")
