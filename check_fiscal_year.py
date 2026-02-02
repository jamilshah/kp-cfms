#!/usr/bin/env python
"""
Check fiscal year configuration for user and organization
"""
import os
import sys
import django

# Django setup
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import CustomUser
from apps.budgeting.models import FiscalYear
from datetime import date

print("=" * 80)
print("FISCAL YEAR CONFIGURATION CHECK")
print("=" * 80)

# Get first user (typically superuser/admin)
user = CustomUser.objects.first()
print(f"\n1. USER INFORMATION")
print(f"   Username: {user.username}")
print(f"   Organization: {user.organization}")

if not user.organization:
    print("\n   ⚠️  WARNING: User has no organization assigned!")
    print("   This is why fiscal year is not found.")
    print("\n   FIX: Assign organization to user:")
    print("   python manage.py shell")
    print("   >>> user = CustomUser.objects.get(username='your_username')")
    print("   >>> from apps.system_admin.models import Organization")
    print("   >>> org = Organization.objects.first()")
    print("   >>> user.organization = org")
    print("   >>> user.save()")
    sys.exit(1)

org = user.organization
print(f"   Organization ID: {org.id}")
print(f"   Organization Name: {org.name}")

# Check fiscal years for this organization
print(f"\n2. FISCAL YEARS FOR ORGANIZATION")
fys = FiscalYear.objects.filter(organization=org).order_by('-start_date')
print(f"   Total Fiscal Years: {fys.count()}")

if fys.count() == 0:
    print("\n   ⚠️  WARNING: No fiscal years found for this organization!")
    print("\n   FIX: Create fiscal year:")
    print("   python manage.py shell")
    print("   >>> from apps.budgeting.models import FiscalYear")
    print("   >>> from apps.system_admin.models import Organization")
    print("   >>> from datetime import date")
    print("   >>> org = Organization.objects.first()")
    print("   >>> fy = FiscalYear.objects.create(")
    print("   ...     organization=org,")
    print("   ...     year_name='2024-2025',")
    print("   ...     start_date=date(2024, 7, 1),")
    print("   ...     end_date=date(2025, 6, 30),")
    print("   ...     is_active=True,")
    print("   ...     is_locked=False")
    print("   ... )")
    sys.exit(1)

for fy in fys:
    print(f"\n   Fiscal Year: {fy.year_name}")
    print(f"   - Period: {fy.start_date} to {fy.end_date}")
    print(f"   - Active: {fy.is_active}")
    print(f"   - Locked: {fy.is_locked}")

# Check current operating fiscal year
print(f"\n3. CURRENT OPERATING FISCAL YEAR")
print(f"   Today's Date: {date.today()}")

current_fy = FiscalYear.get_current_operating_year(org)

if current_fy:
    print(f"   ✓ Current FY: {current_fy.year_name}")
    print(f"   - Period: {current_fy.start_date} to {current_fy.end_date}")
    print(f"   - Active: {current_fy.is_active}")
    
    # Check if today is within the fiscal year range
    today = date.today()
    if current_fy.start_date <= today <= current_fy.end_date:
        print(f"   ✓ Today is within fiscal year range")
    else:
        print(f"   ⚠️  Today ({today}) is OUTSIDE fiscal year range!")
        print(f"       FY Range: {current_fy.start_date} to {current_fy.end_date}")
else:
    print(f"   ⚠️  WARNING: No current operating fiscal year found!")
    print(f"\n   This happens when:")
    print(f"   1. No fiscal year covers today's date ({date.today()})")
    print(f"   2. Fiscal year exists but is_active=False")
    print(f"\n   DIAGNOSIS:")
    
    # Check if any fiscal year covers today
    today = date.today()
    matching_fys = FiscalYear.objects.filter(
        organization=org,
        start_date__lte=today,
        end_date__gte=today
    )
    
    if matching_fys.exists():
        print(f"   Found {matching_fys.count()} fiscal year(s) covering today:")
        for fy in matching_fys:
            print(f"   - {fy.year_name}: Active={fy.is_active}")
            if not fy.is_active:
                print(f"     ⚠️  This fiscal year is INACTIVE!")
                print(f"     FIX: Activate it:")
                print(f"     python manage.py shell")
                print(f"     >>> from apps.budgeting.models import FiscalYear")
                print(f"     >>> fy = FiscalYear.objects.get(id={fy.id})")
                print(f"     >>> fy.is_active = True")
                print(f"     >>> fy.save()")
    else:
        print(f"   No fiscal year covers today's date ({today})")
        print(f"\n   Available fiscal years:")
        for fy in fys:
            print(f"   - {fy.year_name}: {fy.start_date} to {fy.end_date}")
        
        print(f"\n   FIX: Either:")
        print(f"   a) Adjust existing fiscal year dates to include today")
        print(f"   b) Create new fiscal year covering current period")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)
