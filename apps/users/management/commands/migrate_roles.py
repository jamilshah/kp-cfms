"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to migrate users from old role CharField
             to new roles ManyToMany field.
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import CustomUser, Role


# Mapping from old role codes to new role codes
ROLE_MAPPING = {
    'DA': 'DEALING_ASSISTANT',
    'AC': 'ACCOUNTANT',
    'TMO': 'TMO',
    'TOF': 'FINANCE_OFFICER',
    'LCB': 'LCB_OFFICER',
    'CSH': 'CASHIER',
    'ADM': 'SUPER_ADMIN',
}


class Command(BaseCommand):
    help = 'Migrates users from old role field to new roles ManyToMany'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes'
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        self.stdout.write('Migrating user roles...')
        
        # First, ensure roles exist
        roles = {role.code: role for role in Role.objects.all()}
        
        if not roles:
            self.stdout.write(
                self.style.ERROR(
                    'No roles found! Run "python manage.py seed_roles" first.'
                )
            )
            return
        
        # Get users who haven't been migrated yet (have old role but no new roles)
        users_to_migrate = CustomUser.objects.filter(
            role__isnull=False
        ).exclude(role='')
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for user in users_to_migrate:
            old_role = user.role
            
            # Check if user already has roles assigned
            if user.roles.exists():
                self.stdout.write(f'  Skipping {user.cnic}: Already has roles assigned')
                skipped_count += 1
                continue
            
            # Get new role code
            new_role_code = ROLE_MAPPING.get(old_role)
            
            if not new_role_code:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Warning: Unknown role "{old_role}" for user {user.cnic}'
                    )
                )
                error_count += 1
                continue
            
            # Get role object
            role = roles.get(new_role_code)
            
            if not role:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Warning: Role "{new_role_code}" not found for user {user.cnic}'
                    )
                )
                error_count += 1
                continue
            
            if not dry_run:
                user.roles.add(role)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Migrated {user.cnic}: {old_role} -> {new_role_code}'
                    )
                )
            else:
                self.stdout.write(f'  Would migrate {user.cnic}: {old_role} -> {new_role_code}')
            
            migrated_count += 1
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(f'Total users processed: {users_to_migrate.count()}')
        self.stdout.write(f'Migrated: {migrated_count}')
        self.stdout.write(f'Skipped (already migrated): {skipped_count}')
        self.stdout.write(f'Errors: {error_count}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a dry run. Run without --dry-run to apply changes.')
            )
        else:
            self.stdout.write(self.style.SUCCESS('\nMigration complete!'))
