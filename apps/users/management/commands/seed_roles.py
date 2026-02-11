"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to seed standard system roles.
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.db import transaction

from apps.users.models import Role, RoleCode


# Standard role definitions
# Standard role definitions
STANDARD_ROLES = [
    {
        'code': 'SUPER_ADMIN',
        'name': 'Super Administrator',
        'description': 'Full System Access. Can manage entire system, including organizations, users, and configuration.',
        'is_system_role': True,
    },
    {
        'code': 'LCB_OFFICER',
        'name': 'LCB Finance Officer',
        'description': 'Provincial Oversight. APPROVER for PUGF Budgets and Posts. Viewer for all TMA data.',
        'is_system_role': True,
    },
    {
        'code': 'TMO',
        'name': 'Tehsil Municipal Officer',
        'description': 'TMA Administrator. APPROVER for Local Budgets, Bills, and Vouchers. Signing Authority.',
        'is_system_role': True,
    },
    {
        'code': 'TMA_ADMIN',
        'name': 'TMA Administrator',
        'description': 'TMA System Administrator. Can configure TMA settings, manage users, and system setup. Cannot approve transactions.',
        'is_system_role': True,
    },
    {
        'code': 'FINANCE_OFFICER',
        'name': 'Finance Officer (Pre-Audit)',
        'description': 'Pre-Audit. CHECKER for Bills and Vouchers. Verifies financial transactions before TMO approval.',
        'is_system_role': True,
    },
    {
        'code': 'TOF',
        'name': 'Tehsil Officer Finance (Verifier)',
        'description': 'Finance Branch Head. VERIFIER for Bills and Vouchers after Pre-Audit. Reviews budget compliance before TMO approval.',
        'is_system_role': True,
    },
    {
        'code': 'ACCOUNTANT',
        'name': 'Accountant (Verifier)',
        'description': 'Accounts Branch. CHECKER for transactions. Reconciles bank accounts and verifies ledger entries.',
        'is_system_role': True,
    },
    {
        'code': 'CASHIER',
        'name': 'Cashier',
        'description': 'Cash Branch. MAKER for Cash Book entries, Receipts, and Daily Collections.',
        'is_system_role': True,
    },
    {
        'code': 'BUDGET_OFFICER',
        'name': 'Budget Officer',
        'description': 'Budget Branch. MAKER for Budget Estimates, Allocations, and Re-appropriations.',
        'is_system_role': True,
    },
    {
        'code': 'DEALING_ASSISTANT',
        'name': 'Dealing Assistant (Maker)',
        'description': 'General Maker. MAKER for Bills, Vouchers, and general data entry duties.',
        'is_system_role': True,
    },
    {
        'code': 'PROPERTY_MANAGER',
        'name': 'Property Manager',
        'description': 'Property Management. Full access to Property (GIS) module for managing immoveable property assets.',
        'is_system_role': True,
    },
]


class Command(BaseCommand):
    help = 'Seeds standard system roles into the database'
    
    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Seeding system roles...')
        from django.contrib.auth.models import Permission
        
        created_count = 0
        updated_count = 0
        
        for role_data in STANDARD_ROLES:
            code = role_data['code']
            
            # Check if role exists
            role = Role.objects.filter(code=code).first()
            
            if role:
                # Update existing role
                role.name = role_data['name']
                role.description = role_data['description']
                role.is_system_role = role_data['is_system_role']
                
                # Update group name if changed
                if role.group.name != role_data['name']:
                    role.group.name = role_data['name']
                    role.group.save()
                
                role.save()
                updated_count += 1
                self.stdout.write(f'  Updated: {role.name}')
            else:
                # Create Django Group first
                group, _ = Group.objects.get_or_create(name=role_data['name'])
                
                # Create Role
                role = Role.objects.create(
                    code=code,
                    name=role_data['name'],
                    description=role_data['description'],
                    group=group,
                    is_system_role=role_data['is_system_role'],
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {role.name}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone! Created: {created_count}, Updated: {updated_count}'
            )
        )
