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
STANDARD_ROLES = [
    {
        'code': 'SUPER_ADMIN',
        'name': 'Super Administrator',
        'description': 'Full system access. Can manage all organizations, users, and system settings.',
        'is_system_role': True,
    },
    {
        'code': 'LCB_OFFICER',
        'name': 'LCB Finance Officer',
        'description': 'Provincial oversight role. Can view all TMAs and approve PUGF posts.',
        'is_system_role': True,
    },
    {
        'code': 'TMO',
        'name': 'Tehsil Municipal Officer',
        'description': 'TMA Approver. Final approval authority for local posts, bills, and payments.',
        'is_system_role': True,
    },
    {
        'code': 'FINANCE_OFFICER',
        'name': 'Finance Officer (Pre-Audit)',
        'description': 'Pre-audit and financial verification. Reviews bills before approval.',
        'is_system_role': True,
    },
    {
        'code': 'ACCOUNTANT',
        'name': 'Accountant (Verifier)',
        'description': 'Checker role. Verifies transactions and budget entries.',
        'is_system_role': True,
    },
    {
        'code': 'CASHIER',
        'name': 'Cashier',
        'description': 'Records payments and collections. Manages cash book entries.',
        'is_system_role': True,
    },
    {
        'code': 'BUDGET_OFFICER',
        'name': 'Budget Officer',
        'description': 'Prepares budget estimates and manages budget allocations.',
        'is_system_role': True,
    },
    {
        'code': 'DEALING_ASSISTANT',
        'name': 'Dealing Assistant (Maker)',
        'description': 'Maker role. Creates bills, budget entries, and transaction records.',
        'is_system_role': True,
    },
]


class Command(BaseCommand):
    help = 'Seeds standard system roles into the database'
    
    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Seeding system roles...')
        
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
