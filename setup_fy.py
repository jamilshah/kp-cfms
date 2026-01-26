"""
Script to setup a Fiscal Year for testing/verification.
"""
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Organization, OrganizationType, District, Division, Tehsil
from apps.budgeting.models import FiscalYear, BudgetStatus

def setup():
    # 1. Ensure Organization Exists
    org = Organization.objects.filter(org_type__in=['TMA', 'TOWN'], is_active=True).first()
    
    if not org:
        print("No active TMA found. Creating seed data...")
        
        # Try to find existing division or create one with explicit code
        div = Division.objects.filter(code='PES').first()
        if not div:
            div = Division.objects.filter(name__icontains='Peshawar').first()
            if not div:
                # Create with unique code
                div, _ = Division.objects.get_or_create(
                    name='Peshawar Division Debug',
                    defaults={'code': 'PDD'}
                )
        print(f"Using Division: {div}")
        
        dist, _ = District.objects.get_or_create(name='Peshawar', division=div)
        tehsil, _ = Tehsil.objects.get_or_create(name='City Tehsil', district=dist)
        
        org, created = Organization.objects.get_or_create(
            name='TMA Town-1 Peshawar',
            defaults={
                'tehsil': tehsil,
                'org_type': OrganizationType.TMA,
                'ddo_code': 'PR1234',
                'is_active': True
            }
        )
        print(f"Created/Found Organization: {org}")
    else:
        print(f"Using Organization: {org}")
        
    # 2. Create Fiscal Year 2026-27
    fy_name = "2026-27"
    start_date = date(2026, 7, 1)
    end_date = date(2027, 6, 30)
    
    # Get or create
    fy, created = FiscalYear.objects.get_or_create(
        year_name=fy_name,
        organization=org,
        defaults={
            'start_date': start_date,
            'end_date': end_date,
            'is_active': True,
            'is_locked': False,
            'status': BudgetStatus.DRAFT
        }
    )
    
    if created:
        print(f"Created Fiscal Year: {fy}")
    else:
        # Activate it if inactive
        if not fy.is_active:
            fy.is_active = True
            fy.save()
            print(f"Activated Fiscal Year: {fy}")
        else:
            print(f"Fiscal Year {fy} already exists and active.")

if __name__ == '__main__':
    setup()
