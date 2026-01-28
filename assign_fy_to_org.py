"""
Script to assign existing fiscal years to organizations.
Run this after creating organizations to make FYs visible to TMA users.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.budgeting.models import FiscalYear
from apps.core.models import Organization

# Get fiscal years without organization
fys_without_org = FiscalYear.objects.filter(organization=None)
print(f"Found {fys_without_org.count()} fiscal year(s) without organization\n")

if fys_without_org.count() == 0:
    print("No fiscal years to assign. Exiting.")
    exit(0)

# Get all organizations
orgs = Organization.objects.all()
print(f"Found {orgs.count()} organization(s):\n")
for org in orgs:
    print(f"  {org.id}: {org.name}")

print("\n" + "="*50)
print("ASSIGNING FISCAL YEARS TO ORGANIZATIONS")
print("="*50 + "\n")

# Assign each FY to each organization
for fy in fys_without_org:
    print(f"\nProcessing FY: {fy.year_name}")
    
    for org in orgs:
        # Check if FY already exists for this org
        existing = FiscalYear.objects.filter(
            organization=org,
            year_name=fy.year_name
        ).first()
        
        if existing:
            print(f"  ⚠ Already exists for {org.name} - skipping")
            continue
        
        # Create a copy for this organization
        new_fy = FiscalYear.objects.create(
            organization=org,
            year_name=fy.year_name,
            start_date=fy.start_date,
            end_date=fy.end_date,
            is_active=fy.is_active,
            is_locked=fy.is_locked,
            status=fy.status,
            created_by=fy.created_by,
            updated_by=fy.updated_by
        )
        print(f"  ✓ Created for {org.name} (ID: {new_fy.id})")

print("\n" + "="*50)
print("SUMMARY")
print("="*50)
print(f"Original FYs without org: {fys_without_org.count()}")
print(f"Organizations: {orgs.count()}")
print(f"Total FYs now: {FiscalYear.objects.count()}")
print("\n✓ Done! Now you can delete the original FYs with organization=NULL if needed.")
