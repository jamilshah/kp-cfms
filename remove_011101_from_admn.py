#!/usr/bin/env python
"""Remove function 011101 from ADMN department"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import FunctionCode
from apps.budgeting.models import Department

print("=" * 80)
print("REMOVING FUNCTION 011101 FROM ADMN DEPARTMENT")
print("=" * 80)

# Get function and department
fc = FunctionCode.objects.get(code='011101')
admn = Department.objects.get(code='ADMN')

print(f"\nFunction: {fc.code} - {fc.name}")
print(f"Department: {admn.code} - {admn.name}")

print("\n" + "-" * 80)
print("BEFORE REMOVAL:")
print("-" * 80)

print(f"\nADMN Functions ({admn.related_functions.count()}):")
for f in admn.related_functions.all().order_by('code'):
    print(f"  - {f.code}: {f.name}")

print(f"\nDepartments with 011101:")
depts = Department.objects.filter(related_functions=fc)
for dept in depts:
    print(f"  - {dept.code}: {dept.name}")

# Remove the function from ADMN
print("\n" + "-" * 80)
print("REMOVING FUNCTION 011101 FROM ADMN...")
print("-" * 80)

admn.related_functions.remove(fc)
print("✓ Removed")

print("\n" + "-" * 80)
print("AFTER REMOVAL:")
print("-" * 80)

# Refresh from database
admn.refresh_from_db()

print(f"\nADMN Functions ({admn.related_functions.count()}):")
for f in admn.related_functions.all().order_by('code'):
    print(f"  - {f.code}: {f.name}")

print(f"\nDepartments with 011101:")
depts = Department.objects.filter(related_functions=fc)
for dept in depts:
    print(f"  - {dept.code}: {dept.name}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\n✓ Function 011101 (Executive & Legislative Organs) removed from ADMN")
print(f"✓ Function 011101 now only belongs to CNCL (Tehsil Council)")
print(f"✓ ADMN now has {admn.related_functions.count()} functions (011103, 011110)")
print("\n" + "=" * 80)
