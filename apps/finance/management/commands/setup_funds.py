"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to populate standard Funds
             (General, Development, Pension)
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import Fund


class Command(BaseCommand):
    help = 'Populate standard Funds (General, Development, Pension)'

    def handle(self, *args, **options):
        """Create standard funds if they don't exist."""
        
        funds_data = [
            {
                'code': 'GEN',
                'name': 'General',
                'description': 'General Fund for current/operating expenses'
            },
            {
                'code': 'DEV',
                'name': 'Development',
                'description': 'Development Fund for capital/ADP projects'
            },
            {
                'code': 'PEN',
                'name': 'Pension',
                'description': 'Pension Fund for pension payments'
            },
        ]
        
        created_count = 0
        existing_count = 0
        
        with transaction.atomic():
            for fund_data in funds_data:
                fund, created = Fund.objects.get_or_create(
                    code=fund_data['code'],
                    defaults={
                        'name': fund_data['name'],
                        'description': fund_data['description'],
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[+] Created fund: {fund.code} - {fund.name}'
                        )
                    )
                else:
                    existing_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'[*] Fund already exists: {fund.code} - {fund.name}'
                        )
                    )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Setup complete! Created {created_count} new fund(s), '
                f'{existing_count} already existed.'
            )
        )
