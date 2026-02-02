#!/usr/bin/env python
"""Check why function 011101 is in ADMN department"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import FunctionCode
from apps.budgeting.models import Department

print("=" * 80)
print("CHECKING FUNCTION 011101 ASSIGNMENT")
print("=" * 80)

# Check what function 011101 is
fc = FunctionCode.objects.filter(code='011101').first()
if fc:
    print(f"\nFunction Code: {fc.code}")
    print(f"Name: {fc.name}")
    print(f"Description: {fc.description or 'N/A'}")
else:
    print("\n⚠️  Function 011101 not found!")

print("\n" + "-" * 80)

# Check ADMN department's functions
admn = Department.objects.filter(code='ADMN').first()
if admn:
    print(f"\nADMN Department: {admn.name}")
    print(f"\nAssigned Functions ({admn.related_functions.count()}):")
    for f in admn.related_functions.all().order_by('code'):
        print(f"  - {f.code}: {f.name}")
    
    if fc and fc in admn.related_functions.all():
        print(f"\n✓ Function {fc.code} IS assigned to ADMN department")
        print("\nThis seems incorrect if 011101 is not an administrative function.")
    else:
        print(f"\n✗ Function {fc.code if fc else '011101'} is NOT assigned to ADMN")
else:
    print("\n⚠️  ADMN Department not found!")

print("\n" + "-" * 80)

# Check which departments SHOULD have 011101
if fc:
    print(f"\nDepartments that have function {fc.code}:")
    depts = Department.objects.filter(related_functions=fc)
    if depts.exists():
        for dept in depts:
            print(f"  - {dept.code}: {dept.name}")
    else:
        print("  None - function not assigned to any department")

print("\n" + "=" * 80)
