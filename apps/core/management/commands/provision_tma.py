"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to provision a new TMA (Organization).
             Creates the Organization and an initial admin user.
-------------------------------------------------------------------------
"""
from typing import Optional
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.core.models import Organization, OrganizationType, Tehsil
from apps.users.models import CustomUser, UserRole


class Command(BaseCommand):
    """
    Management command to provision a new TMA organization.
    
    Creates an Organization record and optionally creates an initial
    admin user (TMO) for that organization.
    
    Usage:
        python manage.py provision_tma "TMA Town-1 Peshawar" --ddo-code=TMA-PSH-001
        python manage.py provision_tma "TMA Mardan" --tehsil=Mardan --create-admin
    """
    
    help = 'Provision a new TMA organization with optional admin user'
    
    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            'name',
            type=str,
            help='Name of the organization (e.g., "TMA Town-1 Peshawar")'
        )
        parser.add_argument(
            '--ddo-code',
            type=str,
            default=None,
            help='Drawing & Disbursing Officer Code (unique identifier)'
        )
        parser.add_argument(
            '--tehsil',
            type=str,
            default=None,
            help='Name of the tehsil to link to (must exist in database)'
        )
        parser.add_argument(
            '--org-type',
            type=str,
            choices=['TMA', 'TOWN', 'LCB', 'LGD'],
            default='TMA',
            help='Type of organization (default: TMA)'
        )
        parser.add_argument(
            '--pla-account',
            type=str,
            default='',
            help='Personal Ledger Account number'
        )
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Create an initial TMO admin user for this organization'
        )
        parser.add_argument(
            '--admin-cnic',
            type=str,
            default=None,
            help='CNIC for the admin user (required if --create-admin is set)'
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default=None,
            help='Email for the admin user (required if --create-admin is set)'
        )
        parser.add_argument(
            '--admin-name',
            type=str,
            default='TMO Admin',
            help='Full name for the admin user'
        )
    
    def handle(self, *args, **options) -> str:
        """Execute the command."""
        name = options['name']
        ddo_code = options['ddo_code']
        tehsil_name = options['tehsil']
        org_type = options['org_type']
        pla_account = options['pla_account']
        create_admin = options['create_admin']
        admin_cnic = options['admin_cnic']
        admin_email = options['admin_email']
        admin_name = options['admin_name']
        
        # Validate admin user requirements
        if create_admin:
            if not admin_cnic:
                raise CommandError('--admin-cnic is required when --create-admin is set')
            if not admin_email:
                raise CommandError('--admin-email is required when --create-admin is set')
        
        # Look up tehsil if specified
        tehsil: Optional[Tehsil] = None
        if tehsil_name:
            try:
                tehsil = Tehsil.objects.get(name__iexact=tehsil_name)
            except Tehsil.DoesNotExist:
                raise CommandError(f'Tehsil "{tehsil_name}" not found in database')
            except Tehsil.MultipleObjectsReturned:
                raise CommandError(
                    f'Multiple tehsils found with name "{tehsil_name}". '
                    'Please be more specific.'
                )
        
        # Check for existing organization with same name or DDO code
        if Organization.objects.filter(name=name).exists():
            raise CommandError(f'Organization "{name}" already exists')
        
        if ddo_code and Organization.objects.filter(ddo_code=ddo_code).exists():
            raise CommandError(f'DDO Code "{ddo_code}" is already assigned')
        
        # Map org_type string to enum
        org_type_enum = getattr(OrganizationType, org_type)
        
        try:
            with transaction.atomic():
                # Create the organization
                org = Organization.objects.create(
                    name=name,
                    tehsil=tehsil,
                    org_type=org_type_enum,
                    ddo_code=ddo_code,
                    pla_account_no=pla_account,
                    is_active=True
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created organization: {org.name}')
                )
                
                # Create admin user if requested
                if create_admin:
                    # Parse admin name
                    name_parts = admin_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    user = CustomUser.objects.create_user(
                        cnic=admin_cnic,
                        email=admin_email,
                        first_name=first_name,
                        last_name=last_name,
                        role=UserRole.TMO,
                        organization=org,
                        designation='Tehsil Municipal Officer',
                        department='Administration'
                    )
                    # Set a default password (should be changed on first login)
                    user.set_password('changeme123')
                    user.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created admin user: {user.get_full_name()} ({user.cnic})'
                        )
                    )
                    self.stdout.write(
                        self.style.WARNING('Default password is: changeme123')
                    )
        
        except Exception as e:
            raise CommandError(f'Error creating organization: {str(e)}')
        
        return f'Successfully provisioned {org.name}'
