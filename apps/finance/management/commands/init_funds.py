from django.core.management.base import BaseCommand
from apps.finance.models import Fund

class Command(BaseCommand):
    help = 'Initialize default funds (General, Development, Pension)'

    def handle(self, *args, **options):
        funds_data = [
            {
                'name': 'General Fund',
                'code': 'GEN',
                'description': 'Current/Operating expenses',
                'id': 1  # Try to force ID 1 if possible
            },
            {
                'name': 'Development Fund',
                'code': 'DEV',
                'description': 'Capital/ADP projects',
                'id': 2
            },
            {
                'name': 'Pension Fund',
                'code': 'PEN',
                'description': 'Pension payments',
                'id': 5
            }
        ]

        for fund_data in funds_data:
            fund, created = Fund.objects.get_or_create(
                code=fund_data['code'],
                defaults={
                    'name': fund_data['name'],
                    'description': fund_data['description']
                }
            )
            
            # If we want to align IDs exactly with legacy fund_ids (1, 2, 5)
            # We might need to handle ID assignment if table is empty.
            # But usually standard creation order is enough if table is empty.
            # Since user specifically mentioned fund_id=1 for Current, 2 for Dev.
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created fund: {fund.name} (ID: {fund.id})"))
            else:
                self.stdout.write(f"Fund already exists: {fund.name} (ID: {fund.id})")
